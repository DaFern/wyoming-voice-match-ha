"""Synthetic score/transport tests; no real audio, model or biometric fixtures."""

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "voice_match/rootfs/opt/voice_match"
sys.path.insert(0, str(SCRIPTS))
from identity_assessment import IDENTITY_MODE, assess_identity, score_metadata


class Verifier:
    threshold = .3
    extraction_threshold = .25
    max_verify_seconds = 5
    window_seconds = 3
    step_seconds = 1.5

    def __init__(self, candidates=None):
        self.voiceprints = {"alice": object(), "bob": object()}
        self.classifier = object()
        self.candidates = candidates if candidates is not None else [
            (b"a\0", 0, 1), (b"b\0", 1, 2),
        ]
        self.scores = {b"a\0": {"alice": .35, "bob": .1},
                       b"b\0": {"alice": .8, "bob": .2}}
        self.calls = []

    def _extract_speech_candidates(self, audio, rate):
        return self.candidates

    def _verify_chunk(self, chunk, rate):
        self.calls.append((chunk, rate, self.threshold, self.extraction_threshold, self.classifier))
        scores = self.scores.get(chunk, {"alice": .4, "bob": .1})
        name = max(scores, key=scores.get)
        return SimpleNamespace(all_scores=dict(scores), similarity=scores[name],
                               is_match=scores[name] >= self.threshold,
                               matched_speaker=name if scores[name] >= self.threshold else None)

    def verify(self, audio, rate):
        # Reproduce the pinned engine's early-accept contract, not its ML model.
        for chunk, _start, _end in self.candidates:
            result = self._verify_chunk(chunk, rate)
            if result.is_match:
                return result
        return self._verify_chunk(audio, rate)


class IdentityAssessmentTests(unittest.TestCase):
    audio = b"\x01\x00" * (16000 * 8)

    def test_identity_finds_stronger_segment_without_changing_filter_result(self):
        verifier = Verifier()
        filtered = verifier.verify(self.audio, 16000)
        self.assertEqual(filtered.similarity, .35)
        result = assess_identity(verifier, self.audio, 16000, "alice")
        self.assertEqual(result["speaker"], "alice")
        self.assertEqual(result["similarity"], .8)
        self.assertAlmostEqual(result["margin"], .6)
        self.assertEqual(filtered.similarity, .35)
        self.assertTrue(filtered.is_match)
        self.assertEqual(verifier.threshold, .3)
        self.assertEqual(verifier.extraction_threshold, .25)
        self.assertTrue(all(call[2:4] == (.3, .25) for call in verifier.calls))
        self.assertTrue(all(call[4] is verifier.classifier for call in verifier.calls))

    def test_first_n_and_later_sliding_windows_are_scored(self):
        verifier = Verifier(candidates=[])
        result = assess_identity(verifier, self.audio, 16000, "alice")
        self.assertIsNotNone(result)
        self.assertEqual(len(verifier.calls[0][0]), 5 * 32000)
        self.assertGreater(len(verifier.calls), 1)
        self.assertTrue(all(len(call[0]) == 3 * 32000 for call in verifier.calls[1:]))

    def test_margins_use_the_same_complete_window_not_scores_from_other_windows(self):
        verifier = Verifier()
        verifier.scores[b"b\0"] = {"alice": .8, "bob": .78}
        result = assess_identity(verifier, self.audio, 16000, "alice")
        self.assertAlmostEqual(result["margin"], .02)

    def test_different_filter_and_identity_winners_remain_neutral(self):
        verifier = Verifier()
        verifier.scores[b"b\0"] = {"alice": .4, "bob": .9}
        self.assertIsNone(assess_identity(verifier, self.audio, 16000, "alice"))

    def test_budget_expiry_discards_already_scored_candidates(self):
        verifier = Verifier()
        clock = iter([0, 0, 6]).__next__
        self.assertIsNone(assess_identity(verifier, self.audio, 16000, "alice", clock=clock))
        self.assertEqual(len(verifier.calls), 1)

    def test_chunk_capacity_discards_partial_result(self):
        verifier = Verifier()
        with patch("identity_assessment.MAX_CHUNKS", 1):
            self.assertIsNone(assess_identity(verifier, self.audio, 16000, "alice"))
        self.assertEqual(len(verifier.calls), 1)

    def test_scoring_exception_has_no_partial_identity_or_exception_payload(self):
        verifier = Verifier()
        with patch.object(Verifier, "_verify_chunk", side_effect=RuntimeError("private marker")):
            self.assertIsNone(assess_identity(verifier, self.audio, 16000, "alice"))

    def test_malformed_audio_and_timing_are_neutral(self):
        verifier = Verifier()
        for audio, rate, speaker in ((b"", 16000, "alice"), (b"x", 16000, "alice"),
                                     (self.audio, 8000, "alice"), (self.audio, 16000, None),
                                     (b"\0" * (60 * 32000 + 2), 16000, "alice")):
            with self.subTest(rate=rate, speaker=speaker):
                self.assertIsNone(assess_identity(verifier, audio, rate, speaker))
        for step in (0, -1, float("nan"), float("inf"), "1", .000001):
            with self.subTest(step=step):
                verifier.step_seconds = step
                self.assertIsNone(assess_identity(verifier, self.audio, 16000, "alice"))

    def test_nonfinite_and_malformed_scores_are_neutral(self):
        for scores in ({}, {"alice": float("nan")}, {"alice": float("inf")},
                       {"alice": True}, {"alice": 1.2}, {"alice": "0.8"}, {"": .8}):
            with self.subTest(scores=scores):
                verifier = Verifier()
                verifier.scores[b"a\0"] = scores
                self.assertIsNone(assess_identity(verifier, self.audio, 16000, "alice"))

    def test_only_one_profile_keeps_existing_margin_convention(self):
        self.assertEqual(score_metadata(SimpleNamespace(all_scores={"alice": .8})),
                         {"speaker": "alice", "similarity": .8, "margin": 1.0})

    def test_identity_assessment_is_not_an_acceptance_decision(self):
        verifier = Verifier()
        verifier.scores[b"b\0"] = {"alice": .44, "bob": .1}
        result = assess_identity(verifier, self.audio, 16000, "alice")
        self.assertEqual(result["similarity"], .44)
        # The unchanged Connector still decides whether this reaches 0.50.
        self.assertEqual(verifier.threshold, .3)

    def test_partial_score_vectors_cannot_hide_a_competing_voice(self):
        verifier = Verifier()
        verifier.scores[b"b\0"] = {"alice": .9}
        self.assertIsNone(assess_identity(verifier, self.audio, 16000, "alice"))

    def test_equal_best_windows_with_different_winners_are_neutral(self):
        verifier = Verifier()
        verifier.scores[b"a\0"] = {"alice": .8, "bob": .1}
        verifier.scores[b"b\0"] = {"alice": .1, "bob": .8}
        self.assertIsNone(assess_identity(verifier, self.audio, 16000, "alice"))

    def test_equal_best_same_speaker_keeps_the_more_conservative_margin(self):
        verifier = Verifier()
        verifier.scores[b"a\0"] = {"alice": .8, "bob": .1}
        verifier.scores[b"b\0"] = {"alice": .8, "bob": .78}
        result = assess_identity(verifier, self.audio, 16000, "alice")
        self.assertAlmostEqual(result["margin"], .02)

    def test_connector_thresholds_still_reject_low_or_ambiguous_assessments(self):
        import tempfile
        from cryptography.fernet import Fernet
        from personalization import Connector
        from speaker_packet import decode

        with tempfile.TemporaryDirectory() as folder:
            connector = Connector(Path(folder))
            connector.config.update(enabled=True, key=Fernet.generate_key().decode())
            profiles = {"alice": {"name": "Alice", "owner": "test-account",
                                  "context_version": "a" * 32, "personal_instructions": ""}}
            for score, other, recognised in ((.8, .2, True), (.44, .1, False), (.8, .78, False)):
                with self.subTest(score=score, other=other):
                    verifier = Verifier()
                    verifier.scores[b"b\0"] = {"alice": score, "bob": other}
                    match = assess_identity(verifier, self.audio, 16000, "alice")
                    packet = decode(connector.config["key"],
                                    connector.wrap("spoken words", match, profiles))[1]
                    self.assertEqual(packet["voice"], "alice" if recognised else None)
                    self.assertEqual(packet.get("speaker_name"), "Alice" if recognised else None)
            self.assertEqual(connector.config["min_similarity"], .5)
            self.assertEqual(connector.config["min_margin"], .1)


HAS_GATEWAY = all(importlib.util.find_spec(name) is not None
                  for name in ("wyoming", "aiohttp", "numpy"))


@unittest.skipUnless(HAS_GATEWAY, "Requires Wyoming/aiohttp/numpy for gateway transport")
class IdentityGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def transcribe(self, *, personalized=True, enabled=True, mode=IDENTITY_MODE):
        from guided import Gateway
        from wyoming.asr import Transcript
        from wyoming.info import Info

        reply = Transcript(text="spoken words").event()
        reply.data["voice_match"] = {"speaker": "alice", "similarity": .8, "margin": .5}
        if mode is not None:
            reply.data["voice_match_identity"] = mode
        sent = []

        class Client:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def write_event(self, event):
                sent.append(event)
            async def read_event(self):
                return reply

        runtime = SimpleNamespace(connector=SimpleNamespace(config={"enabled": enabled}))
        handler = Gateway(runtime, Info(), None, None, personalized=personalized)
        handler.audio.extend(b"\x01\x00" * 160)
        handler.match = {"speaker": "stale"}
        with patch("guided.AsyncClient.from_uri", return_value=Client()):
            self.assertEqual(await handler.transcribe(), "spoken words")
        return handler, sent

    async def test_personal_gateway_requests_independent_assessment(self):
        handler, sent = await self.transcribe()
        start = next(event for event in sent if event.type == "audio-start")
        self.assertEqual(start.data["voice_match_identity"], IDENTITY_MODE)
        self.assertEqual(handler.match["speaker"], "alice")

    async def test_old_or_unknown_worker_cannot_fall_back_to_filter_identity(self):
        for mode in (None, "unknown", True, 1):
            with self.subTest(mode=mode):
                handler, _sent = await self.transcribe(mode=mode)
                self.assertIsNone(handler.match)

    async def test_normal_and_disabled_endpoints_do_not_request_extra_inference(self):
        for personalized, enabled in ((False, True), (False, False), (True, False)):
            with self.subTest(personalized=personalized, enabled=enabled):
                _handler, sent = await self.transcribe(personalized=personalized, enabled=enabled)
                start = next(event for event in sent if event.type == "audio-start")
                self.assertNotIn("voice_match_identity", start.data)

    async def test_independent_requests_do_not_share_transcript_or_profile_state(self):
        results = await asyncio.gather(self.transcribe(), self.transcribe(mode=None))
        self.assertEqual(results[0][0].match["speaker"], "alice")
        self.assertIsNone(results[1][0].match)


@unittest.skipUnless(HAS_GATEWAY, "Requires Wyoming for proxy protocol")
class IdentityProxyTests(unittest.IsolatedAsyncioTestCase):
    def handler(self, *, accepted=True):
        from proxy import bounded_handler
        from wyoming.asr import Transcript
        from wyoming.audio import AudioStart, AudioStop

        class Base:
            def __init__(self):
                self._audio_buffer = b""
                self.events = []
                self.forwarded = []
                self.forward_audio = b"\x02\x00" * 16000
                self.filter_result = SimpleNamespace(is_match=accepted, matched_speaker="alice",
                                                     similarity=.35, all_scores={"alice": .35})
                self.verifier = SimpleNamespace(verify=lambda audio, rate: self.filter_result)

            async def write_event(self, event):
                self.events.append(event)

            async def handle_event(self, event):
                if AudioStart.is_type(event.type):
                    self._audio_buffer = b""
                elif AudioStop.is_type(event.type):
                    result = self.verifier.verify(self._audio_buffer, 16000)
                    text = await self._forward_to_upstream(self.forward_audio) if result.is_match else ""
                    await self.write_event(Transcript(text=text).event())
                return True

            async def _forward_to_upstream(self, audio):
                self.forwarded.append(audio)
                return "spoken words"

        return bounded_handler(Base)()

    async def stream(self, handler, mode=IDENTITY_MODE):
        from wyoming.audio import AudioStart, AudioChunk, AudioStop

        start = AudioStart(rate=16000, width=2, channels=1).event()
        if mode is not None:
            start.data["voice_match_identity"] = mode
        await handler.handle_event(start)
        await handler.handle_event(AudioChunk(audio=b"\x01\x00" * 32000,
                                             rate=16000, width=2, channels=1).event())
        await handler.handle_event(AudioStop().event())
        return handler.events[-1]

    async def test_identity_scores_exact_forwarded_audio_without_changing_filter_or_asr(self):
        handler = self.handler()
        original = handler.filter_result
        metadata = {"speaker": "alice", "similarity": .8, "margin": .5}
        with patch("proxy.assess_identity", return_value=metadata) as assess:
            event = await self.stream(handler)
        self.assertIs(handler._speaker_tap.result, original)
        self.assertEqual(original.similarity, .35)
        self.assertEqual(handler.forwarded, [handler.forward_audio])
        assess.assert_called_once_with(handler._speaker_tap.base, handler.forward_audio, 16000, "alice")
        self.assertEqual(event.data["text"], "spoken words")
        self.assertEqual(event.data["voice_match"], metadata)
        self.assertEqual(event.data["voice_match_identity"], IDENTITY_MODE)

    async def test_rejected_audio_never_requests_identity_or_asr(self):
        handler = self.handler(accepted=False)
        with patch("proxy.assess_identity") as assess:
            event = await self.stream(handler)
        assess.assert_not_called()
        self.assertEqual(handler.forwarded, [])
        self.assertEqual(event.data["text"], "")
        self.assertNotIn("voice_match", event.data)

    async def test_normal_endpoint_preserves_legacy_filter_without_extra_inference(self):
        handler = self.handler()
        with patch("proxy.assess_identity") as assess:
            event = await self.stream(handler, mode=None)
        assess.assert_not_called()
        self.assertEqual(event.data["text"], "spoken words")
        self.assertEqual(event.data["voice_match"]["similarity"], .35)
        self.assertNotIn("voice_match_identity", event.data)

    async def test_failed_identity_never_falls_back_to_accepted_filter_score(self):
        handler = self.handler()
        with patch("proxy.assess_identity", return_value=None) as assess:
            event = await self.stream(handler)
        assess.assert_called_once()
        self.assertEqual(event.data["text"], "spoken words")
        self.assertEqual(handler.forwarded, [handler.forward_audio])
        self.assertNotIn("voice_match", event.data)

    async def test_request_reset_does_not_restore_previous_identity_metadata(self):
        handler = self.handler()
        with patch("proxy.assess_identity", side_effect=[
            {"speaker": "alice", "similarity": .8, "margin": .5}, None,
        ]):
            first = await self.stream(handler)
            second = await self.stream(handler)
        self.assertIn("voice_match", first.data)
        self.assertNotIn("voice_match", second.data)
        self.assertEqual(len(handler.forwarded), 2)

    async def test_overlapping_handlers_do_not_share_identity_results(self):
        first, second = self.handler(), self.handler()
        second.forward_audio = b"\x03\x00" * 16000

        def identity(_verifier, audio, _rate, _speaker):
            return {"speaker": "alice", "similarity": .8 if audio == first.forward_audio else .6,
                    "margin": .5}

        with patch("proxy.assess_identity", side_effect=identity):
            events = await asyncio.gather(self.stream(first), self.stream(second))
        self.assertEqual(events[0].data["voice_match"]["similarity"], .8)
        self.assertEqual(events[1].data["voice_match"]["similarity"], .6)
