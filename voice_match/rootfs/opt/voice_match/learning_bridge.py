"""Opt-in trusted-HA bridge; never trust forwarded account or device headers."""

import base64
import json
import logging
import os
import secrets
import time

from enrollment_transport import MAX_SAMPLE_BYTES
from learning_bridge_protocol import BridgeError, open_message, seal
from voices import Denied

LOG = logging.getLogger("learning_bridge")


class LearningBridge:
    def __init__(self, root):
        self.path = root / "learning_bridge.json"
        self.key = None
        if self.path.exists():
            try:
                from cryptography.fernet import Fernet
                if self.path.is_symlink() or self.path.stat().st_size > 4096:
                    raise ValueError
                self.key = json.loads(self.path.read_text())["key"]
                if self.key is not None:
                    Fernet(self.key)
            except (OSError, ValueError, KeyError, TypeError):
                self.key = None
                LOG.warning("Learning bridge pairing is unavailable; ordinary recognition is unaffected")
        self.boot = secrets.token_hex(16)
        self.seen = {}
        self.sessions = {}

    def view(self):
        return {"paired": self.key is not None}

    def configure(self, actor, data):
        if not actor["admin"] or data.get("confirm") is not True:
            raise Denied("Only administrators can pair the learning companion")
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode() if data["action"] == "learning_bridge_rotate" else None
        temporary = self.path.with_name(f".learning-bridge-{secrets.token_hex(8)}.tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as output:
                json.dump({"key": key}, output)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
        self.key = key
        self.boot = secrets.token_hex(16)
        self.seen.clear()
        self.sessions.clear()
        return {"learning_bridge_key": key} if key else {}

    def receive(self, token):
        if self.key is None:
            raise BridgeError("Learning bridge unavailable")
        request_id, data = open_message(self.key, token, "request", self.boot)
        now = time.monotonic()
        self.seen = {key: expiry for key, expiry in self.seen.items() if expiry > now}
        # Do not evict valid entries to accommodate a flood. Retention exceeds
        # Fernet's TTL plus its allowed future clock skew.
        if request_id in self.seen or len(self.seen) >= 1024:
            raise BridgeError("Learning bridge request unavailable")
        self.seen[request_id] = now + 120
        return request_id, data

    def reply(self, request_id, data):
        return seal(self.key, "response", self.boot, request_id, data)

    def job(self, runtime, actor, data):
        token = data.get("session_token")
        if not isinstance(token, str) or len(token) > 128:
            raise Denied("Learning session unavailable")
        job = self.sessions.get(token)
        if job is None or actor["id"] != job.actor_id:
            raise Denied("Learning session unavailable")
        runtime.store.get(job.voice_id, actor)
        job.learning.authorize(data.get("source"), token)
        return job

    async def dispatch(self, runtime, actor, users, operation, data, *, boot):
        if operation == "begin":
            if (set(data) - {"id", "source", "consent", "isolation_confirmed"}
                    or not isinstance(data.get("id"), str) or not data["id"]):
                raise ValueError("Choose an existing authorised voice profile")
            self.sessions = {token: job for token, job in self.sessions.items()
                             if job.learning.expires > time.monotonic()}
            if len(self.sessions) >= 32:
                raise ValueError("Too many learning sessions")
            result = await runtime.action(actor, {**data, "action": "begin"}, users, bridge_boot=boot)
            self.sessions[result["session_token"]] = runtime.active
            return result
        job = self.job(runtime, actor, data)
        headers = {"X-Learning-Source": data.get("source"), "X-Learning-Session": data.get("session_token")}
        if operation == "state":
            return {"id": job.voice_id, "outcome": job.outcome, "processing": job.processing,
                    "count": (job.recording.options["enrollment_samples"] if job.outcome == "complete" else job.recording.count),
                    "target": job.recording.options["enrollment_samples"], "error": bool(job.error),
                    "notice": bool(job.notice)}
        if operation == "cancel":
            # A delayed cancellation must never cancel a subsequent session.
            if runtime.active is job:
                await runtime.action(actor, {"action": "cancel"}, users)
            return {"outcome": job.outcome}
        if runtime.active is not job:
            raise Denied("Learning session ended")
        if operation == "permit":
            return await runtime.recording_permit(actor, headers)
        if operation == "sample":
            headers["X-Learning-Permit"] = data.get("permit")
            claimed = await runtime.claim_recording(actor, headers)
            queued = False
            try:
                encoded = data.get("audio")
                if not isinstance(encoded, str) or len(encoded) > 426668:
                    raise ValueError("Recording is too large")
                audio = base64.b64decode(encoded, validate=True)
                if len(audio) > MAX_SAMPLE_BYTES or len(audio) % 2:
                    raise ValueError("Unsupported recording size")
                runtime.spawn(runtime.ingest(claimed, audio))
                queued = True
                return {"queued": True}
            finally:
                if not queued:
                    claimed.processing = False
                    claimed.notice = "Sample not saved; request a fresh recording permit and try again"
        raise ValueError("Unknown learning operation")
