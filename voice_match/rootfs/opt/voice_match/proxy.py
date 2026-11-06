"""Small safety adapter around the pinned upstream recognition engine.

Buffer once until AudioStop to avoid upstream's early/final verification race.
The verifier/extractor remain upstream implementations, not our own models.
"""

import asyncio
import logging

from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop

from identity_assessment import IDENTITY_MODE, assess_identity

_LOGGER = logging.getLogger("proxy")
MAX_BYTES = 16000 * 2 * 60


class VerificationTap:
    """Capture the result for this connection, never a shared 'last speaker'."""
    def __init__(self, base):
        self.base = base
        self.result = None

    def __getattr__(self, name):
        return getattr(self.base, name)

    def verify(self, audio, rate):
        self.result = self.base.verify(audio, rate)
        return self.result


def match_metadata(result):
    if (result is None or not result.is_match or not result.matched_speaker
            or result.matched_speaker not in result.all_scores):
        return None
    scores = sorted(result.all_scores.values(), reverse=True)
    margin = scores[0] - scores[1] if len(scores) > 1 else 1.0
    return {"speaker": result.matched_speaker, "similarity": result.similarity, "margin": margin}


def bounded_handler(base):
    class BoundedHandler(base):
        async def write_event(self, event):
            if Transcript.is_type(event.type) and getattr(self, "_speaker_tap", None):
                # Only the private loopback worker emits this extension. The
                # ordinary external STT endpoint never forwards it to HA.
                if getattr(self, "_assess_identity", False):
                    # The gateway must not fall back to old-worker filter scores.
                    event.data["voice_match_identity"] = IDENTITY_MODE
                    metadata = self._identity_metadata
                else:
                    metadata = match_metadata(self._speaker_tap.result)
                if metadata and Transcript.from_event(event).text:
                    event.data["voice_match"] = metadata
            await super().write_event(event)

        async def disconnect(self):
            self._audio_buffer = b""
            await super().disconnect()
            self.writer.close()
            await self.writer.wait_closed()

        async def handle_event(self, event):
            if AudioStart.is_type(event.type):
                self._assess_identity = event.data.get("voice_match_identity") == IDENTITY_MODE
                self._identity_metadata = None
                verifier = getattr(self, "verifier", None)
                if verifier is not None:
                    if isinstance(verifier, VerificationTap):
                        verifier = verifier.base
                    self._speaker_tap = VerificationTap(verifier)
                    self.verifier = self._speaker_tap
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
            tap = getattr(self, "_speaker_tap", None)
            if getattr(self, "_assess_identity", False) and tap is not None and tap.result is not None:
                # Filter acceptance/extraction is already decided. Score the exact
                # forwarded bytes off-loop; never change that decision or audio.
                if tap.result.is_match:
                    self._identity_metadata = await asyncio.to_thread(
                        assess_identity, tap.base, audio_bytes, 16000,
                        tap.result.matched_speaker,
                    )
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
