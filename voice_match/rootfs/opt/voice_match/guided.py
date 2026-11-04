"""Ingress management and a persistent Wyoming front door for guided enrolment."""

import asyncio
from dataclasses import dataclass
from functools import partial
import hashlib
import hmac
import logging
import os
from pathlib import Path
import secrets
import signal
import sys
import time
import uuid

from aiohttp import web
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncClient
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncServer

from enrollment import Recording
from healthcheck import check
from identity import actor_from_users, identify
from voices import Denied, VoiceStore, validate_voiceprint

LOG = logging.getLogger("guided")
STATIC = Path(__file__).parent / "static"
BACKEND = "tcp://127.0.0.1:10351"


class Worker:
    def __init__(self):
        self.process = None
        self.monitor = None
        self.status = "stopped"

    async def stop(self):
        if self.monitor:
            self.monitor.cancel()
            await asyncio.gather(self.monitor, return_exceptions=True)
            self.monitor = None
        process, self.process = self.process, None
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 10)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        self.status = "stopped"

    async def start(self):
        await self.stop()
        env = {key: value for key, value in os.environ.items()
               if key not in {"SUPERVISOR_TOKEN", "HASSIO_TOKEN"}}
        env["LISTEN_URI"] = BACKEND
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, str(Path(__file__).with_name("worker.py")), env=env,
        )
        self.status = "loading"
        self.monitor = asyncio.create_task(self.watch())

    async def watch(self):
        for _ in range(600):
            if self.process.returncode is not None:
                self.status = "failed"
                return
            try:
                await asyncio.wait_for(check(BACKEND), 2)
                self.status = "ready"
                await self.process.wait()
                self.status = "failed"
                return
            except (OSError, asyncio.TimeoutError, RuntimeError):
                await asyncio.sleep(1)
        self.status = "failed"


@dataclass
class Job:
    voice_id: str
    actor_id: str
    recording: Recording
    deadline: float
    capture: object = None
    processing: bool = False
    error: str = ""
    notice: str = ""


class Runtime:
    def __init__(self, root, options, worker=None):
        self.store = VoiceStore(root)
        self.options = options
        self.worker = worker or Worker()
        self.active = None
        self.epoch = 0
        self.lock = asyncio.Lock()
        self.tasks = set()

    def spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def reload(self):
        self.epoch += 1
        if any((self.store.root / "voiceprints").glob("*.npy")):
            await self.worker.start()
        else:
            await self.worker.stop()

    def view(self, actor):
        profiles = []
        for profile in self.store.visible(actor):
            voice_id = profile["id"]
            profiles.append(dict(profile,
                enrolled=(self.store.root / "voiceprints" / f"{voice_id}.npy").is_file(),
                recording_bytes=self.store.recording_bytes(voice_id),
            ))
        result = {"profiles": profiles, "engine": self.worker.status, "paused": self.active is not None}
        job = self.active
        if job and (actor["admin"] or job.actor_id == actor["id"]):
            result["job"] = {"id": job.voice_id, "count": job.recording.count,
                             "target": job.recording.options["enrollment_samples"],
                             "processing": job.processing, "error": job.error, "notice": job.notice}
        return result

    async def begin(self, actor, data, users):
        if data.get("consent") is not True or data.get("pause_confirmed") is not True:
            raise ValueError("Confirm the speaker's consent and the temporary recognition pause")
        if self.active:
            raise ValueError("Another enrolment is in progress. Please wait")
        voice_id = data.get("id")
        if voice_id:
            self.store.get(voice_id, actor)
        else:
            owner = data.get("owner", actor["id"])
            if owner != actor["id"] and not actor["admin"]:
                raise Denied("You can only enrol your own voice")
            actor_from_users(owner, users)
            voice_id = self.store.create(data.get("name"), owner)
        profile = self.store.get(voice_id, actor)
        # Resume only when explicitly requested by an authorised user with consent.
        session = profile.get("pending") or uuid.uuid4().hex
        profile["pending"] = session
        self.store.save()
        opts = dict(self.options, enrollment_speaker=voice_id, enrollment_session=session)
        recording = Recording(opts, self.store.root, candidate_validator=validate_voiceprint)
        self.epoch += 1
        await self.worker.stop()
        self.active = Job(voice_id, actor["id"], recording, time.monotonic() + 900)
        if recording.complete.exists() or recording.count >= opts["enrollment_samples"]:
            self.active.processing = True
            self.spawn(self.ingest(self.active, b""))

    async def ingest(self, job, audio):
        async with self.lock:
            if self.active is not job:
                return
            try:
                job.processing = True
                await job.recording.save(audio)
                if job.recording.complete.exists():
                    profile = self.store.profiles[job.voice_id]
                    # Only after validated, atomic voiceprint installation and
                    # durable completion. Both legacy hard links are removed.
                    self.store.cleanup(job.voice_id)
                    profile.pop("pending", None)
                    self.store.save()
                    self.active = None
                    await self.reload()
                elif job.recording.count >= job.recording.options["enrollment_samples"]:
                    job.error = "Voice processing failed. Pause learning, then resume to retry with the saved samples"
                elif len(audio) < 32000:
                    job.notice = "That sample was too short. Please speak for about five seconds and try again"
                else:
                    job.notice = ""
            except Exception:
                LOG.error("Enrolment or sample cleanup failed; saved voice data was not broadly removed")
                job.error = "Processing failed. Your samples are kept where possible; retry or ask an administrator"
            finally:
                job.processing = False
                job.capture = None

    async def action(self, actor, data, users):
        if self.active and self.active.processing:
            raise ValueError("Please wait for voice processing to finish")
        async with self.lock:
            action = data.get("action")
            if action == "begin":
                await self.begin(actor, data, users)
                return
            if action == "cancel":
                job = self.active
                if not job or (job.actor_id != actor["id"] and not actor["admin"]):
                    raise Denied("No enrolment available to cancel")
                # Never interrupt voiceprint installation or delete a generation input.
                if job.processing:
                    raise ValueError("Please wait for voice processing to finish")
                self.active = None
                await self.reload()
                return
            voice_id = data.get("id")
            if action == "retry_engine":
                if not actor["admin"] or self.active:
                    raise Denied("Only administrators can retry the idle voice engine")
                await self.reload()
                return
            self.store.get(voice_id, actor)
            if self.active:
                raise ValueError("Finish or cancel enrolment before changing saved voices")
            if data.get("confirm") is not True:
                raise ValueError("Confirm this change first")
            if action == "assign":
                owner = data.get("owner")
                actor_from_users(owner, users)
                self.store.assign(voice_id, owner, actor)
            elif action == "cleanup":
                self.store.cleanup(voice_id)
                self.store.profiles[voice_id].pop("pending", None)
                self.store.save()
            elif action == "delete":
                # Stop inference and invalidate in-flight transcripts before
                # removing a voice, so cached embeddings cannot remain active.
                self.epoch += 1
                await self.worker.stop()
                try:
                    self.store.delete(voice_id, actor)
                finally:
                    await self.reload()
            else:
                raise ValueError("Unknown action")

    async def expire(self):
        while True:
            await asyncio.sleep(5)
            async with self.lock:
                job = self.active
                if job and not job.processing and time.monotonic() > job.deadline:
                    # Pause capture, preserve partial work. Explicit consent is
                    # required again before resuming after timeout or restart.
                    self.active = None
                    await self.reload()


class Gateway(AsyncEventHandler):
    def __init__(self, runtime, info, *args):
        super().__init__(*args)
        self.runtime, self.info = runtime, info
        self.audio = bytearray()
        self.valid = False
        self.job = None
        self.language = None
        self.epoch = -1

    async def disconnect(self):
        if self.job and self.job.capture is self:
            self.job.capture = None
        self.audio.clear()
        self.writer.close()
        await self.writer.wait_closed()

    async def handle_event(self, event):
        if Describe.is_type(event.type):
            await self.write_event(self.info.event())
        elif Transcribe.is_type(event.type):
            self.language = Transcribe.from_event(event).language
        elif AudioStart.is_type(event.type):
            self.audio.clear()
            start = AudioStart.from_event(event)
            self.valid = (start.rate, start.width, start.channels) == (16000, 2, 1)
            self.epoch = self.runtime.epoch
            self.job = self.runtime.active
            if self.job:
                if self.job.capture is None and not self.job.processing and not self.job.error:
                    self.job.capture = self
                else:
                    self.valid = False
        elif AudioChunk.is_type(event.type):
            chunk = AudioChunk.from_event(event)
            limit = 32000 * (10 if self.job else 60)
            if ((chunk.rate, chunk.width, chunk.channels) != (16000, 2, 1)
                    or len(self.audio) + len(chunk.audio) > limit or self.runtime.epoch != self.epoch):
                self.valid = False
                self.audio.clear()
            if self.valid:
                self.audio.extend(chunk.audio)
        elif AudioStop.is_type(event.type):
            text = ""
            valid = self.valid and len(self.audio) % 2 == 0 and self.epoch == self.runtime.epoch
            self.valid = False
            if self.job:
                if valid and self.runtime.active is self.job and self.job.capture is self:
                    # Claim processing before returning the empty enrolment
                    # transcript; no second connection can sneak in another sample.
                    self.job.processing = True
                    self.runtime.spawn(self.runtime.ingest(self.job, bytes(self.audio)))
                elif self.job.capture is self:
                    self.job.capture = None
                    self.job.notice = "Sample not saved: use mono 16 kHz audio and finish within ten seconds"
            elif valid and self.runtime.active is None and self.runtime.worker.status == "ready":
                try:
                    text = await asyncio.wait_for(self.transcribe(), 40)
                except (OSError, asyncio.TimeoutError):
                    LOG.warning("Voice engine unavailable; no unverified audio was forwarded")
            self.audio.clear()
            if self.runtime.epoch != self.epoch:
                text = ""
            await self.write_event(Transcript(text=text).event())
        return True

    async def transcribe(self):
        async with AsyncClient.from_uri(BACKEND) as client:
            await client.write_event(Transcribe(language=self.language).event())
            await client.write_event(AudioStart(rate=16000, width=2, channels=1).event())
            for offset in range(0, len(self.audio), 3200):
                await client.write_event(AudioChunk(audio=bytes(self.audio[offset:offset + 3200]), rate=16000, width=2, channels=1).event())
            await client.write_event(AudioStop().event())
            while True:
                event = await client.read_event()
                if event is None:
                    return ""
                if Transcript.is_type(event.type):
                    return Transcript.from_event(event).text


def create_app(runtime, identity_lookup=identify):
    secret = secrets.token_bytes(32)

    def csrf(user_id):
        return hmac.new(secret, user_id.encode(), hashlib.sha256).hexdigest()

    @web.middleware
    async def security(request, handler):
        try:
            actor, users = await identity_lookup(request)
            request["actor"], request["users"] = actor, users
            if request.method != "GET":
                if request.method != "POST" or request.content_type != "application/json":
                    raise Denied("Use the Voice Match controls to make changes")
                if request.headers.get("Sec-Fetch-Site") == "cross-site" or not hmac.compare_digest(
                    request.headers.get("X-Voice-CSRF", ""), csrf(actor["id"])
                ):
                    raise Denied("Refresh Voice Match before making changes")
            response = await handler(request)
        except Denied as exc:
            response = web.json_response({"error": str(exc)}, status=403)
        except ValueError as exc:
            response = web.json_response({"error": str(exc)}, status=400)
        except web.HTTPException as exc:
            response = web.json_response({"error": "Request not supported"}, status=exc.status)
        except Exception:
            # Do not serialize exceptions containing upstream credentials or data.
            LOG.error("Voice management request failed")
            response = web.json_response({"error": "Request failed; check app status and try again"}, status=503)
        response.headers.update({
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'",
            "Referrer-Policy": "no-referrer",
        })
        return response

    async def state(request):
        actor = request["actor"]
        value = runtime.view(actor)
        value.update(user=actor, csrf=csrf(actor["id"]))
        if actor["admin"]:
            value["accounts"] = [{"id": user["id"], "name": user.get("name") or "Unnamed account"}
                                 for user in request["users"]
                                 if user.get("is_active") and not user.get("system_generated")]
        return web.json_response(value)

    async def action(request):
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid request")
        await runtime.action(request["actor"], data, request["users"])
        return web.json_response({"ok": True})

    async def static(request):
        name = request.match_info.get("name", "index.html")
        if name not in {"index.html", "app.js", "style.css"}:
            raise web.HTTPNotFound()
        return web.FileResponse(STATIC / name)

    app = web.Application(middlewares=[security], client_max_size=4096)
    app.router.add_get("/", static)
    app.router.add_get("/static/{name}", static)
    app.router.add_get("/api/state", state)
    app.router.add_post("/api/action", action)
    return app


async def service_info(uri):
    languages = ["en"]
    try:
        async with AsyncClient.from_uri(uri) as client:
            await client.write_event(Describe().event())
            event = await asyncio.wait_for(client.read_event(), 5)
            if event and Info.is_type(event.type):
                found = [language for program in Info.from_event(event).asr
                         for model in program.models for language in model.languages]
                languages = list(dict.fromkeys(found)) or languages
    except (OSError, asyncio.TimeoutError):
        LOG.warning("Whisper language discovery failed; using English until the app is restarted")
    attribution = Attribution(name="Wyoming Voice Match", url="https://github.com/jxlarrea/wyoming-voice-match")
    return Info(asr=[AsrProgram(name="voice-match", description="Voice Match", attribution=attribution,
                               installed=True, version="0.2.0", models=[AsrModel(
                                   name="voice-match-proxy", description="Speaker-filtered ASR",
                                   attribution=attribution, installed=True, version="0.2.0", languages=languages)])])


async def serve(options):
    runtime = Runtime(Path("/data"), options)
    app = create_app(runtime)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8099).start()
    server = AsyncServer.from_uri("tcp://0.0.0.0:10350")
    tasks = []
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        info = await service_info(options["upstream_uri"])
        await server.start(partial(Gateway, runtime, info))
        await runtime.reload()
        tasks.append(asyncio.create_task(runtime.expire()))
        LOG.info("Manage voices is ready through Home Assistant Ingress")
        await stop.wait()
    finally:
        for task in tasks + list(runtime.tasks):
            task.cancel()
        await asyncio.gather(*tasks, *list(runtime.tasks), return_exceptions=True)
        await server.stop()
        await runtime.worker.stop()
        await runner.cleanup()
