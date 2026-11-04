"""Small safety adapter around the pinned upstream recognition engine.

Buffer once until AudioStop to avoid upstream's early/final verification race.
The verifier/extractor remain upstream implementations, not our own models.
"""

import asyncio
import logging

from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop

_LOGGER = logging.getLogger("proxy")
MAX_BYTES = 16000 * 2 * 60


def bounded_handler(base):
    class BoundedHandler(base):
        async def disconnect(self):
            self._audio_buffer = b""
            await super().disconnect()
            self.writer.close()
            await self.writer.wait_closed()

        async def handle_event(self, event):
            if AudioStart.is_type(event.type):
                start = AudioStart.from_event(event)
                self._valid_format = (start.rate, start.width, start.channels) == (16000, 2, 1)
                self._verify_result_cache = None
                return await super().handle_event(event)
            if AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                if ((chunk.rate, chunk.width, chunk.channels) != (16000, 2, 1)
                        or len(self._audio_buffer) + len(chunk.audio) > MAX_BYTES):
                    self._valid_format = False
                    self._audio_buffer = b""
                if getattr(self, "_valid_format", False):
                    self._audio_rate, self._audio_width, self._audio_channels = 16000, 2, 1
                    self._audio_buffer += chunk.audio
                return True
            if AudioStop.is_type(event.type) and (
                not getattr(self, "_valid_format", False) or len(self._audio_buffer) % 2
            ):
                _LOGGER.warning("Audio rejected: requires mono 16 kHz/16-bit PCM, at most 60 seconds")
                await self.write_event(Transcript(text="").event())
                return True
            return await super().handle_event(event)

        async def _forward_to_upstream(self, audio_bytes):
            try:
                return await asyncio.wait_for(super()._forward_to_upstream(audio_bytes), timeout=30)
            except asyncio.TimeoutError:
                _LOGGER.error("Upstream Whisper did not respond within 30 seconds")
                return ""

    return BoundedHandler


def run():
    from wyoming_voice_match import __main__ as upstream
    upstream.SpeakerVerifyHandler = bounded_handler(upstream.SpeakerVerifyHandler)
    asyncio.run(upstream.main())
