"""Container-only contract checks with real upstream handler, stubbed inference.

No model downloads or real voice fixtures. Run inside the built image; outside
the image these tests explicitly skip when the upstream package is absent.
"""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "voice_match/rootfs/opt/voice_match"))
HAS_ENGINE = importlib.util.find_spec("wyoming_voice_match") is not None


@unittest.skipUnless(HAS_ENGINE, "Requires built image with pinned upstream engine")
class EngineContractTests(unittest.IsolatedAsyncioTestCase):
    def handler(self, match):
        from wyoming_voice_match.handler import SpeakerVerifyHandler
        from proxy import bounded_handler
        from wyoming.info import Info

        class Verifier:
            max_verify_seconds = 5
            def verify(self, audio, rate):
                return SimpleNamespace(
                    is_match=match, similarity=0.8 if match else 0.1,
                    threshold=0.3, matched_speaker="test" if match else None,
                    all_scores={"test": 0.8 if match else 0.1},
                )
            def extract_speaker_audio(self, audio, speaker, rate):
                return audio

        result = bounded_handler(SpeakerVerifyHandler)(
            Info(), Verifier(), "tcp://127.0.0.1:1", False, True, False, None, None,
        )
        result.write_event = AsyncMock()
        return result

    async def stream(self, handler):
        from wyoming.audio import AudioStart, AudioChunk, AudioStop
        await handler.handle_event(AudioStart(rate=16000, width=2, channels=1).event())
        # More than the upstream early-verify threshold: adapter must buffer only.
        await handler.handle_event(AudioChunk(audio=b"\x00" * 192000, rate=16000, width=2, channels=1).event())
        self.assertIsNone(handler._verify_task)
        await handler.handle_event(AudioStop().event())

    async def test_matched_audio_forwards_once_without_early_task(self):
        from wyoming.asr import Transcript
        handler = self.handler(True)
        handler._forward_to_upstream = AsyncMock(return_value="test command")
        await self.stream(handler)
        handler._forward_to_upstream.assert_awaited_once()
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "test command")

    async def test_unknown_audio_never_forwards(self):
        from wyoming.asr import Transcript
        handler = self.handler(False)
        handler._forward_to_upstream = AsyncMock()
        await self.stream(handler)
        handler._forward_to_upstream.assert_not_awaited()
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "")

    async def test_connection_failure_returns_empty_transcript(self):
        from wyoming.asr import Transcript
        handler = self.handler(True)
        await self.stream(handler)
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "")

    async def test_worker_metadata_is_tied_to_this_verification_not_a_global_sensor(self):
        from unittest.mock import patch
        from wyoming_voice_match.handler import SpeakerVerifyHandler
        handler = self.handler(True)
        # Use the real adapter write path, intercepting only the underlying wire.
        del handler.write_event
        handler._forward_to_upstream = AsyncMock(return_value="test command")
        with patch.object(SpeakerVerifyHandler, "write_event", new_callable=AsyncMock) as send:
            await self.stream(handler)
        event = send.call_args.args[0]
        self.assertEqual(event.data["voice_match"]["speaker"], "test")
        self.assertEqual(event.data["voice_match"]["similarity"], .8)
