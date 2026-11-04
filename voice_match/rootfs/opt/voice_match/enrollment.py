"""Explicit, capped Wyoming enrolment. Never forward enrolment speech as commands."""

import asyncio
from functools import partial
import logging
import os
from pathlib import Path
import sys
import uuid
import wave

from wyoming.asr import Transcript
from wyoming.audio import AudioStart, AudioChunk, AudioStop
from wyoming.info import Describe
from wyoming.server import AsyncEventHandler, AsyncServer

_LOGGER = logging.getLogger("enrollment")
MAX_BYTES = 16000 * 2 * 10


class Recording:
    """Persistent sessions prevent silent re-recording after a restart."""

    def __init__(self, options, root=Path("/data")):
        self.options = options
        self.root = root
        self.directory = root / "enrollment" / options["enrollment_speaker"] / options["enrollment_session"]
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.complete = self.directory / "COMPLETE"
        self.lock = asyncio.Lock()

    @property
    def count(self):
        return len(list(self.directory.glob("*.wav")))

    async def save(self, audio):
        async with self.lock:
            if self.complete.exists():
                return
            if self.count < self.options["enrollment_samples"]:
                if not 16000 * 2 <= len(audio) <= MAX_BYTES or len(audio) % 2:
                    _LOGGER.warning("Sample skipped: requires 1–10 seconds of mono 16 kHz PCM")
                    return
                temporary = self.directory / f"{uuid.uuid4().hex}.part"
                with wave.open(str(temporary), "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(16000)
                    output.writeframes(audio)
                temporary.replace(temporary.with_suffix(".wav"))
                _LOGGER.info("Saved sample %d/%d", self.count, self.options["enrollment_samples"])
            if self.count >= self.options["enrollment_samples"]:
                # Parent contains exactly the chosen speaker session. Upstream
                # enrols from <enrollment-dir>/<speaker>, not nested folders.
                staging = self.root / "enrollment_work"
                target = staging / self.options["enrollment_speaker"]
                target.mkdir(parents=True, mode=0o700, exist_ok=True)
                # Only this session's samples; no biometric import from elsewhere.
                for old in target.glob("*.wav"):
                    old.unlink()
                for source in self.directory.glob("*.wav"):
                    os.link(source, target / source.name)
                generated = self.directory / "generated"
                generated.mkdir(mode=0o700, exist_ok=True)
                candidate = generated / f"{self.options['enrollment_speaker']}.npy"
                candidate.unlink(missing_ok=True)
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "scripts.enroll",
                    "--speaker", self.options["enrollment_speaker"],
                    "--enrollment-dir", str(staging),
                    "--voiceprints-dir", str(generated),
                    "--model-dir", str(self.root / "models"), "--device", "cpu",
                )
                result = await process.wait()
                if result != 0 or not candidate.is_file():
                    _LOGGER.error("Enrolment failed; inspect logs, then restart to retry")
                    return
                voiceprints = self.root / "voiceprints"
                voiceprints.mkdir(mode=0o700, exist_ok=True)
                candidate.replace(voiceprints / candidate.name)
                self.complete.write_text("Enrolment completed. Switch mode to proxy.\n")
                _LOGGER.info("Enrolment complete. Set mode=proxy and restart the app")


class Handler(AsyncEventHandler):
    def __init__(self, info, recording, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.info = info
        self.recording = recording
        self.audio = bytearray()
        self.valid = False

    async def disconnect(self):
        self.audio.clear()
        self.writer.close()
        await self.writer.wait_closed()

    async def handle_event(self, event):
        if Describe.is_type(event.type):
            await self.write_event(self.info.event())
        elif AudioStart.is_type(event.type):
            start = AudioStart.from_event(event)
            self.audio.clear()
            self.valid = (start.rate, start.width, start.channels) == (16000, 2, 1)
        elif AudioChunk.is_type(event.type):
            chunk = AudioChunk.from_event(event)
            if ((chunk.rate, chunk.width, chunk.channels) != (16000, 2, 1)
                    or len(self.audio) + len(chunk.audio) > MAX_BYTES):
                self.valid = False
                self.audio.clear()
            if self.valid and not self.recording.complete.exists():
                self.audio.extend(chunk.audio)
        elif AudioStop.is_type(event.type):
            # Empty transcript prevents enrolment phrases reaching the agent.
            await self.write_event(Transcript(text="").event())
            if self.valid:
                await self.recording.save(bytes(self.audio))
            else:
                _LOGGER.warning("Sample skipped: unsupported format or longer than 10 seconds")
            self.audio.clear()
            self.valid = False
        return True


async def serve(options):
    from wyoming_voice_match.__main__ import query_upstream_languages
    from wyoming.info import AsrModel, AsrProgram, Attribution, Info

    recording = Recording(options)
    # Resume voiceprint generation after a crash once enough files were saved.
    if recording.count >= options["enrollment_samples"]:
        await recording.save(b"")
    attribution = Attribution(name="Wyoming Voice Match", url="https://github.com/jxlarrea/wyoming-voice-match")
    languages = await query_upstream_languages(options["upstream_uri"], max_retries=1) or ["en"]
    info = Info(asr=[AsrProgram(
        name="voice-match", description="Voice Match enrolment (no commands)",
        attribution=attribution, installed=True, version="0.1.0",
        models=[AsrModel(name="voice-match-proxy", description="Enrolment",
                         attribution=attribution, installed=True, languages=languages, version="0.1.0")],
    )])
    _LOGGER.warning("Enrolment mode: only the consenting speaker should use the selected pipeline")
    if recording.complete.exists():
        _LOGGER.info("Session already complete; recording disabled. Switch mode to proxy")
    await AsyncServer.from_uri("tcp://0.0.0.0:10350").run(partial(Handler, info, recording))
