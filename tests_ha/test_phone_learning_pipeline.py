"""Actual phone WebSocket pipeline with synthetic Whisper/backend boundaries."""

import base64
from dataclasses import dataclass, field
from typing import ClassVar
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from homeassistant.components import conversation, stt
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Reuse only the isolated pipeline/DSP fixture, never its fake learning entities
# as the implementation under test. Production learning entities are loaded below.
from test_learning_pipeline_feasibility import phone_probe  # noqa: F401 - pytest fixture

from custom_components.voice_match_enrollment import DOMAIN
from custom_components.voice_match_enrollment.phone_flow import MARKER, NOTICE


@dataclass
class Backend:
    user_id: str
    count: int = 0
    active: bool = False
    calls: list = field(default_factory=list)
    notice: bool = False

    async def call(self, operation, user_id, data):
        self.calls.append((operation, user_id, data))
        if operation == "hello":
            return {"ready": True}
        if operation == "own_profile":
            return {"id": "assigned-profile" if user_id == self.user_id else None}
        assert user_id == self.user_id
        if operation == "begin":
            assert data["own_only"] is True
            self.active = True
            return {"session_token": "synthetic-session", "expires_in": 900}
        if operation == "cancel":
            self.active = False
            return {"outcome": "paused"}
        assert data["session_token"] == "synthetic-session"
        if operation == "permit":
            return {"permit": f"synthetic-{self.count}", "count": self.count,
                    "prompt": "The bright morning sun is shining through the kitchen window while I make breakfast."}
        if operation == "sample":
            audio = base64.b64decode(data["audio"])
            self.notice = len(audio) < 32000
            if not self.notice:
                self.count += 1
            return {"queued": True}
        if operation == "state":
            return {"id": "assigned-profile", "outcome": "complete" if self.count == 2 else "active",
                    "processing": False, "count": self.count, "target": 2, "error": False, "notice": self.notice}
        raise AssertionError("Unexpected operation")


@pytest.fixture
async def phone(hass, hass_ws_client, hass_admin_user, phone_probe):  # noqa: F811 - imported pytest fixture
    source_calls = []

    class Whisper(stt.SpeechToTextEntity):
        _attr_name = "Synthetic ordinary Whisper"
        _attr_unique_id = "ordinary-whisper-source"
        supported_languages: ClassVar[list[str]] = ["en"]
        supported_formats: ClassVar[list[stt.AudioFormats]] = [stt.AudioFormats.WAV]
        supported_codecs: ClassVar[list[stt.AudioCodecs]] = [stt.AudioCodecs.PCM]
        supported_bit_rates: ClassVar[list[stt.AudioBitRates]] = [stt.AudioBitRates.BITRATE_16]
        supported_sample_rates: ClassVar[list[stt.AudioSampleRates]] = [stt.AudioSampleRates.SAMPLERATE_16000]
        supported_channels: ClassVar[list[stt.AudioChannels]] = [stt.AudioChannels.CHANNEL_MONO]
        audio_processing = stt.SpeechAudioProcessing(False, False, False)

        async def async_process_audio_stream(self, metadata, stream):
            clip = b"".join([chunk async for chunk in stream])
            source_calls.append(clip)
            text = {1: "start", 2: "Yes.", 3: "A varied natural reading phrase", 4: "Pause",
                    5: "No", 6: "status", 7: "No,", 8: NOTICE}[clip[0]]
            return stt.SpeechResult(text, stt.SpeechResultState.SUCCESS)

    source = Whisper()
    await hass.data[stt.DOMAIN].async_add_entities([source])
    class WyomingProviderPlatform:
        platform_name = "wyoming"
        def __init__(self, original):
            self.original = original
        def __getattr__(self, name):
            return getattr(self.original, name)
    source.platform = WyomingProviderPlatform(source.platform)  # Provider metadata stand-in; no real Wyoming I/O.
    assert await async_setup_component(hass, DOMAIN, {})
    backend = Backend(hass_admin_user.id)
    async def call(client, operation, user_id, data):
        return await backend.call(operation, user_id, data)
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://addon:8099", "key": Fernet.generate_key().decode()},
        options={"phone_test_enabled": True, "control_stt_engine": source.entity_id})
    entry.add_to_hass(hass)
    with patch("custom_components.voice_match_enrollment.bridge_client.BridgeClient.call", call):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        from custom_components.voice_match_enrollment.conversation import (
            PhoneLearningAgent,
        )
        from custom_components.voice_match_enrollment.stt import PhoneLearningStt
        engine = next(entity for entity in hass.data[stt.DOMAIN].entities if isinstance(entity, PhoneLearningStt))
        agent = next(entity for entity in hass.data[conversation.DOMAIN].entities if isinstance(entity, PhoneLearningAgent))
        client = await hass_ws_client(hass)
        await client.send_json({"id": 1, "type": "assist_pipeline/pipeline/create", "name": "Voice Learning test",
            "language": "en", "conversation_engine": agent.entity_id, "conversation_language": "en",
            "stt_engine": engine.entity_id, "stt_language": "en", "tts_engine": None,
            "tts_language": None, "tts_voice": None, "wake_word_entity": None, "wake_word_id": None,
            "prefer_local_intents": False})
        created = await client.receive_json()
        assert created["success"], created
        pipeline_id = created["result"]["id"]
        sequence = 10
        async def run(marker, *, selected_client=None, end_stage="intent", chat="phone-chat", expect_error=False):
            nonlocal sequence
            current = selected_client or client
            sequence += 1
            await current.send_json({"id": sequence, "type": "assist_pipeline/run", "pipeline": pipeline_id,
                "start_stage": "stt", "end_stage": end_stage, "conversation_id": chat, "input": {"sample_rate": 16000}})
            events = []
            while True:
                result = await current.receive_json()
                assert result.get("success", True), result
                if "event" not in result:
                    continue
                event = result["event"]
                events.append(event)
                if event["type"] == "run-start":
                    handler = event["data"]["runner_data"]["stt_binary_handler_id"]
                    await current.send_bytes(bytes([handler]) + bytes([marker, 0]) * 16000)
                    await current.send_bytes(bytes([handler]))
                if event["type"] == "run-end":
                    errors = [item for item in events if item["type"] == "error"]
                    assert bool(errors) == expect_error, events
                    return events
        yield {"run": run, "client": client, "entry": entry, "backend": backend, "agent": agent,
               "engine": engine, "source": source, "source_calls": source_calls,
               "runtime": hass.data[DOMAIN][entry.entry_id]["phone"]}
        assert await hass.config_entries.async_unload(entry.entry_id)


def speech(events):
    return next(event["data"]["intent_output"]["response"]["speech"]["plain"]["speech"]
                for event in events if event["type"] == "intent-end")


async def test_phone_uses_real_learning_entities_and_only_post_consent_audio_is_submitted(phone):
    assert "biometric voiceprint" in speech(await phone["run"](1))
    assert not phone["backend"].active
    assert "Sample 1 of 2" in speech(await phone["run"](2))
    assert phone["backend"].count == 0
    assert "Sample 2 of 2" in speech(await phone["run"](3))
    assert phone["backend"].count == 1
    assert "complete" in speech(await phone["run"](3))
    assert phone["backend"].count == 2
    assert len([call for call in phone["backend"].calls if call[0] == "sample"]) == 2


async def test_native_pause_is_not_submitted_as_a_sample(phone):
    await phone["run"](1)
    await phone["run"](2)
    assert "paused" in speech(await phone["run"](4))
    assert phone["backend"].count == 0
    assert not phone["backend"].active


async def test_other_connection_cannot_train_even_with_the_same_user_and_chat(hass, hass_ws_client, phone):
    await phone["run"](1)
    await phone["run"](2)
    second = await hass_ws_client(hass)
    assert "biometric voiceprint" in speech(await phone["run"](3, selected_client=second))
    assert phone["backend"].count == 0


async def test_native_trigger_interception_never_submits_or_creates_a_session(hass, phone):
    from homeassistant.components.conversation.agent_manager import get_agent_manager
    async def intercept(user_input, result):
        return "Synthetic trigger intercepted the marker"
    remove = get_agent_manager(hass).register_trigger(sentences=[MARKER], trigger_callback=intercept)
    try:
        await phone["run"](1)
        assert not phone["runtime"].frames.pending
        assert not phone["backend"].active
        assert not [call for call in phone["backend"].calls if call[0] == "begin"]
    finally:
        remove()


async def test_stt_only_and_typed_marker_never_train(phone):
    await phone["run"](3, end_stage="stt")
    assert not phone["runtime"].frames.pending
    await phone["client"].send_json({"id": 100, "type": "conversation/process", "text": MARKER,
        "agent_id": phone["agent"].entity_id, "conversation_id": "phone-chat", "language": "en"})
    result = await phone["client"].receive_json()
    assert result["success"]
    assert phone["backend"].count == 0
    assert not phone["backend"].active


async def test_phone_options_reject_no_source_and_the_learning_engine(hass, phone):
    entry = MockConfigEntry(domain=DOMAIN, data=phone["entry"].data)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    for source in (None, phone["engine"].entity_id):
        data = {"phone_test_enabled": True}
        if source:
            data["control_stt_engine"] = source
        result = await hass.config_entries.options.async_configure(result["flow_id"], user_input=data)
        assert result["errors"] == {"base": "invalid_stt_source"}


async def test_phone_options_retain_existing_source_when_omitted(hass, phone):
    result = await hass.config_entries.options.async_init(phone["entry"].entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"],
        user_input={"phone_test_enabled": True})
    assert result["type"] == "create_entry"
    assert result["data"]["control_stt_engine"] == phone["source"].entity_id
    await hass.async_block_till_done()


async def test_native_connection_close_pauses_its_learning_session(hass, phone):
    await phone["run"](1)
    await phone["run"](2)
    assert phone["backend"].active
    await phone["client"].close()
    await hass.async_block_till_done()
    tasks = list(phone["runtime"].cleanup_tasks)
    if tasks:
        import asyncio
        await asyncio.gather(*tasks)
    assert not phone["runtime"].connections
    assert not phone["runtime"].frames.pending
    assert not phone["runtime"].controller.flows
    assert not phone["backend"].active


async def test_native_diagnostics_distinguish_repeated_notice_from_recognised_no(phone, caplog):
    import logging
    logger = "custom_components.voice_match_enrollment.phone_diagnostics"
    with caplog.at_level(logging.INFO, logger=logger):
        await phone["run"](1)
        assert "biometric voiceprint" in speech(await phone["run"](7))
        assert "biometric voiceprint" in speech(await phone["run"](8))
        assert "paused" in speech(await phone["run"](5))
    records = [entry for entry in caplog.records if entry.name == logger]
    output = "\n".join(entry.getMessage() for entry in records)
    assert "control=stop_punctuation continuity=same_scope phase=consent" in output
    assert "control=notice_like continuity=same_scope phase=consent" in output
    assert "control=stop continuity=same_scope phase=consent" in output
    assert "result=notice_repeat" in output
    assert "result=stop_paused" in output
    assert "stage=stt result=ready" in output
    assert "audio_ms=1000" in output
    for private in (phone["entry"].data["key"], phone["backend"].user_id, "phone-chat", NOTICE, "No,"):
        assert private not in repr([entry.__dict__ for entry in records])
    assert not [call for call in phone["backend"].calls if call[0] in {"begin", "sample"}]


async def test_native_diagnostics_report_stt_only_discard_and_typed_marker_missing(phone, caplog):
    import logging
    logger = "custom_components.voice_match_enrollment.phone_diagnostics"
    with caplog.at_level(logging.INFO, logger=logger):
        await phone["run"](3, end_stage="stt")
        await phone["client"].send_json({"id": 100, "type": "conversation/process", "text": MARKER,
            "agent_id": phone["agent"].entity_id, "conversation_id": "phone-chat", "language": "en"})
        result = await phone["client"].receive_json()
        assert result["success"]
    output = "\n".join(entry.getMessage() for entry in caplog.records if entry.name == logger)
    assert "stage=handoff result=discarded" in output
    assert "stage=handoff result=missing" in output
    assert "stage=agent result=missing" in output
    assert not phone["backend"].active


async def test_native_diagnostics_report_transcription_failure_without_peer_error_or_clip(phone, caplog):
    import logging
    logger = "custom_components.voice_match_enrollment.phone_diagnostics"
    private = "PRIVATE-peer-transcript-and-credentials"
    with (caplog.at_level(logging.INFO, logger=logger),
          patch.object(phone["source"], "async_process_audio_stream", side_effect=RuntimeError(private))):
        await phone["run"](1, expect_error=True)
    output = "\n".join(entry.getMessage() for entry in caplog.records if entry.name == logger)
    assert "stage=stt result=transcription" in output
    assert "audio_ms=1000" in output
    assert private not in caplog.text
    assert not phone["runtime"].frames.pending
    assert not phone["backend"].active
