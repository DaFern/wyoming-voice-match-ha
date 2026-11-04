"""Dependency-light checks; no model downloads, biometric fixtures or HA access."""

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "voice_match/rootfs/opt/voice_match"
sys.path.insert(0, str(SCRIPTS))
import launcher

HAS_WYOMING = importlib.util.find_spec("wyoming") is not None
if HAS_WYOMING:
    import enrollment
    import proxy
    from wyoming.asr import Transcript
    from wyoming.audio import AudioStart, AudioChunk, AudioStop
    from wyoming.info import Describe


def options(**changes):
    result = {
        "upstream_uri": "tcp://core-whisper:10300", "mode": "enroll",
        "verify_threshold": 0.30, "extraction_threshold": 0.25, "debug": False,
        "enrollment_consent": True, "enrollment_speaker": "test-person",
        "enrollment_session": "test-session", "enrollment_samples": 2,
    }
    result.update(changes)
    return result


class OptionsTests(unittest.TestCase):
    def test_valid_options(self):
        self.assertEqual(launcher.validate(options())["mode"], "enroll")

    def test_consent_must_be_explicit_boolean(self):
        for consent in (False, "true", 1, None):
            with self.subTest(consent=consent), self.assertRaises(ValueError):
                launcher.validate(options(enrollment_consent=consent))

    def test_identifiers_reject_paths_and_shell_fragments(self):
        for value in ("../person", "/root", "person/name", ".", "name;cmd", "", "A", "a" * 41):
            with self.subTest(value=value), self.assertRaises(ValueError):
                launcher.validate(options(enrollment_speaker=value))

    def test_session_rejects_paths(self):
        with self.assertRaises(ValueError):
            launcher.validate(options(enrollment_session="../first"))

    def test_invalid_endpoints(self):
        for uri in ("http://host:10300", "tcp://host", "tcp://user:secret@host:10300",
                    "tcp://host:10300/path", "tcp://host:10300?query=secret", "tcp://host:70000"):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                launcher.validate(options(upstream_uri=uri))

    def test_thresholds(self):
        for value in (-1, 2, float("nan"), float("inf"), "0.3", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                launcher.validate(options(verify_threshold=value))
        with self.assertRaises(ValueError):
            launcher.validate(options(extraction_threshold=0.5))

    def test_sample_limits(self):
        for value in (0, 101, True, 2.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                launcher.validate(options(enrollment_samples=value))

    def test_proxy_does_not_require_enrolment_consent(self):
        launcher.validate(options(mode="proxy", enrollment_consent=False, enrollment_speaker=""))

    def test_sensitive_log_filter(self):
        from logging import LogRecord
        for name, expected in (("handler", False), ("verify", False), ("main", True)):
            record = LogRecord(name, 20, "", 0, "private", (), None)
            self.assertEqual(launcher.PrivateLogs().filter(record), expected)

    def test_python_sources_parse(self):
        import ast
        for path in SCRIPTS.glob("*.py"):
            ast.parse(path.read_text(), filename=str(path))

    def test_source_pins_and_no_public_port_default(self):
        dockerfile = (ROOT / "voice_match/Dockerfile").read_text()
        self.assertIn("39bb5e48a19bf2cb95c1aadb00b3b7f7df7e5416", dockerfile)
        self.assertIn("sha256sum -c", dockerfile)
        self.assertNotIn("latest", dockerfile)
        config = (ROOT / "voice_match/config.yaml").read_text()
        self.assertIn("  10350/tcp:\n", config)
        self.assertNotIn("host_network: true", config)
        self.assertNotIn("homeassistant_api: true", config)


@unittest.skipUnless(HAS_WYOMING, "Install wyoming==1.8.0 to run protocol tests")
class EnrollmentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.recording = enrollment.Recording(options(), self.root)

    async def asyncTearDown(self):
        self.temporary.cleanup()

    def handler(self):
        # Construct only state used by our adapter; transport is replaced below.
        handler = object.__new__(enrollment.Handler)
        handler.recording = self.recording
        handler.audio = bytearray()
        handler.valid = False
        handler.write_event = AsyncMock()
        return handler

    async def stream(self, handler, audio=b"\x00\x00" * 16000, rate=16000, channels=1):
        await handler.handle_event(AudioStart(rate=rate, width=2, channels=channels).event())
        await handler.handle_event(AudioChunk(audio=audio, rate=rate, width=2, channels=channels).event())
        await handler.handle_event(AudioStop().event())

    async def test_saves_mono_wave_and_empty_transcript(self):
        import wave
        handler = self.handler()
        await self.stream(handler)
        self.assertEqual(self.recording.count, 1)
        event = handler.write_event.call_args.args[0]
        self.assertEqual(Transcript.from_event(event).text, "")
        with wave.open(str(next(self.recording.directory.glob("*.wav")))) as audio:
            self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()), (16000, 1, 2))

    async def test_rejects_short_stereo_and_overlong_samples(self):
        for audio, channels in ((b"\x00" * 10, 1), (b"\x00" * 32000, 2),
                                (b"\x00" * (enrollment.MAX_BYTES + 2), 1)):
            await self.stream(self.handler(), audio=audio, channels=channels)
        self.assertEqual(self.recording.count, 0)

    async def test_completion_is_persistent_and_no_rerecord(self):
        process = AsyncMock()
        async def generate():
            (self.recording.directory / "generated/test-person.npy").write_bytes(b"stub voiceprint")
            return 0
        process.wait.side_effect = generate
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)) as spawn:
            await self.recording.save(b"\x00" * 32000)
            await self.recording.save(b"\x00" * 32000)
            await self.recording.save(b"\x00" * 32000)
            self.assertEqual(spawn.await_count, 1)
        resumed = enrollment.Recording(options(), self.root)
        self.assertTrue(resumed.complete.exists())
        self.assertEqual(resumed.count, 2)
        await resumed.save(b"\x00" * 32000)
        self.assertEqual(resumed.count, 2)

    async def test_failed_enrolment_can_retry_without_more_recordings(self):
        process = AsyncMock()
        process.wait.return_value = 1
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)):
            await self.recording.save(b"\x00" * 32000)
            await self.recording.save(b"\x00" * 32000)
            self.assertFalse(self.recording.complete.exists())
            async def generate():
                (self.recording.directory / "generated/test-person.npy").write_bytes(b"stub voiceprint")
                return 0
            process.wait.side_effect = generate
            await self.recording.save(b"")
        self.assertTrue(self.recording.complete.exists())
        self.assertEqual(self.recording.count, 2)

    async def test_failed_generation_preserves_previous_voiceprint(self):
        voiceprints = self.root / "voiceprints"
        voiceprints.mkdir()
        previous = voiceprints / "test-person.npy"
        previous.write_bytes(b"previous voiceprint")
        process = AsyncMock()
        process.wait.return_value = 1
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)):
            await self.recording.save(b"\x00" * 32000)
            await self.recording.save(b"\x00" * 32000)
        self.assertEqual(previous.read_bytes(), b"previous voiceprint")

    async def test_new_session_is_separate(self):
        await self.recording.save(b"\x00" * 32000)
        other = enrollment.Recording(options(enrollment_session="next"), self.root)
        self.assertEqual(other.count, 0)

    async def test_actual_wyoming_discovery_and_empty_response(self):
        from functools import partial
        from wyoming.client import AsyncClient
        from wyoming.info import Info, AsrProgram, AsrModel, Attribution
        from wyoming.server import AsyncTcpServer
        import healthcheck
        attribution = Attribution(name="test", url="https://example.com")
        info = Info(asr=[AsrProgram(
            name="test", description="test", version="test", attribution=attribution, installed=True,
            models=[AsrModel(name="test", description="test", version="test", languages=["en"], attribution=attribution, installed=True)],
        )])
        server = AsyncTcpServer("127.0.0.1", 0)
        await server.start(partial(enrollment.Handler, info, self.recording))
        port = server._server.sockets[0].getsockname()[1]
        uri = f"tcp://127.0.0.1:{port}"
        try:
            await asyncio.wait_for(healthcheck.check(uri), timeout=2)
            async with AsyncClient.from_uri(uri) as client:
                await client.write_event(AudioStart(rate=16000, width=2, channels=1).event())
                await client.write_event(AudioChunk(audio=b"\x00" * 32000, rate=16000, width=2, channels=1).event())
                await client.write_event(AudioStop().event())
                event = await asyncio.wait_for(client.read_event(), timeout=2)
                self.assertEqual(Transcript.from_event(event).text, "")
            self.assertEqual(self.recording.count, 1)
        finally:
            await server.stop()


@unittest.skipUnless(HAS_WYOMING, "Install wyoming==1.8.0 to run protocol tests")
class ProxyTests(unittest.IsolatedAsyncioTestCase):
    def handler(self):
        class Base:
            def __init__(self):
                self._audio_buffer = b""
                self.events = []
                self.write_event = AsyncMock()

            async def handle_event(self, event):
                self.events.append(event.type)
                if AudioStart.is_type(event.type):
                    self._audio_buffer = b""
                return True

            async def _forward_to_upstream(self, audio):
                return "test transcript"

        return proxy.bounded_handler(Base)()

    async def test_single_buffer_no_early_task_and_stop_delegates(self):
        handler = self.handler()
        await handler.handle_event(AudioStart(rate=16000, width=2, channels=1).event())
        await handler.handle_event(AudioChunk(audio=b"\x00" * 32000, rate=16000, width=2, channels=1).event())
        self.assertEqual(len(handler._audio_buffer), 32000)
        self.assertNotIn("audio-chunk", handler.events)
        await handler.handle_event(AudioStop().event())
        self.assertIn("audio-stop", handler.events)
        self.assertEqual(await handler._forward_to_upstream(b"audio"), "test transcript")

    async def test_rejects_overflow_without_retaining_buffer(self):
        handler = self.handler()
        await handler.handle_event(AudioStart(rate=16000, width=2, channels=1).event())
        await handler.handle_event(AudioChunk(audio=b"\x00" * (proxy.MAX_BYTES + 2), rate=16000, width=2, channels=1).event())
        self.assertEqual(handler._audio_buffer, b"")
        await handler.handle_event(AudioStop().event())
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "")
        self.assertNotIn("audio-stop", handler.events)

    async def test_discovery_delegates(self):
        handler = self.handler()
        await handler.handle_event(Describe().event())
        self.assertIn("describe", handler.events)

    async def test_forward_timeout_is_empty_not_bypass(self):
        handler = self.handler()
        async def timeout(awaitable, **kwargs):
            awaitable.close()
            raise asyncio.TimeoutError
        with patch.object(proxy.asyncio, "wait_for", timeout):
            self.assertEqual(await handler._forward_to_upstream(b"audio"), "")


if __name__ == "__main__":
    unittest.main()
