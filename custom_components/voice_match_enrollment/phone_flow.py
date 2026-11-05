"""Phone turns: fresh spoken consent, one account/connection/chat, no LLM tools."""

import asyncio
import base64
import re
import secrets
import time
from dataclasses import dataclass, field

from .learning_bridge_protocol import BridgeError
from .phone_diagnostics import record

MARKER = "Voice learning input"
NOTICE = (
    "Voice learning makes recordings and a biometric voiceprint for your signed-in Home Assistant account. "
    "Recordings are stored on this system and deleted after a validated replacement is installed. "
    "Your selected Whisper service also processes the speech. Only you should use this phone microphone. "
    "Your existing voiceprint stays until its replacement validates. A voice match is not authentication. "
    "Do you consent to starting? Say yes, or say no to cancel."
)
STOP = {"no", "stop", "pause", "cancel", "stop learning", "pause learning", "cancel learning"}
STATUS = {"status", "check status", "continue"}


def control_category(text):
    """Describe the existing parser without broadening consent or stop matching."""
    command = text.casefold().strip(" .!?\r\n\t")
    if command == "yes":
        return "yes"
    if command in STOP:
        return "stop"
    if command in STATUS:
        return "status"
    # Diagnostic only: these variants are NOT accepted by the current parser.
    unpunctuated = re.sub(r"^\W+|\W+$", "", command)
    if unpunctuated in STOP:
        return "stop_punctuation"
    if unpunctuated == "yes":
        return "yes_punctuation"
    if "biometric voiceprint" in command and "do you consent" in command:
        return "notice_like"
    return "other"


@dataclass(repr=False)
class PhoneFrame:
    connection: object
    user_id: str
    conversation_id: str
    started_at: float
    audio: bytes
    text: str


@dataclass
class PhoneReply:
    speech: str
    continue_conversation: bool = False


@dataclass(repr=False)
class PhoneFlow:
    connection: object
    user_id: str
    conversation_id: str
    profile_id: str
    source: str = field(default_factory=lambda: "phone-" + secrets.token_hex(16))
    expires: float = field(default_factory=lambda: time.monotonic() + 120)
    issued: float = field(default_factory=time.monotonic)
    phase: str = "consent"
    credentials: dict | None = None
    permit: dict | None = None
    prompt: str = ""


class PhoneController:
    def __init__(self, bridge):
        self.bridge = bridge
        self.flows = {}
        self.lock = asyncio.Lock()
        self.closing = False

    def key(self, frame):
        return (id(frame.connection), frame.user_id, frame.conversation_id)

    async def _pause(self, key, flow):
        if flow.credentials is None and flow.phase == "consent":
            self.flows.pop(key, None)
            return True
        if flow.expires <= time.monotonic():
            # Dead credentials cannot accept new audio. Do not claim a pending
            # generation was cancelled, but local phone state may be forgotten.
            self.flows.pop(key, None)
            return False
        if flow.credentials is not None:
            try:
                result = await self.bridge.call("cancel", flow.user_id, flow.credentials)
                if result.get("outcome") in {"paused", "complete", "expired"}:
                    self.flows.pop(key, None)
                    return True
            except BridgeError:
                pass
        flow.phase = "attention"
        flow.permit = None
        return False

    async def _next(self, flow):
        state = await self.bridge.call("state", flow.user_id, flow.credentials)
        if state["error"]:
            flow.phase, flow.permit = "attention", None
            return PhoneReply("Voice processing needs attention. Say pause, or check Voice Match management.")
        if state["outcome"] == "complete":
            self.flows.pop((id(flow.connection), flow.user_id, flow.conversation_id), None)
            return PhoneReply("Your replacement voiceprint validated and the saved samples were cleaned up. Voice learning is complete.")
        if state["outcome"] != "active":
            flow.phase, flow.permit = "attention", None
            return PhoneReply("This learning session has ended. Start a new conversation for fresh consent.")
        if state["processing"]:
            flow.phase, flow.permit = "processing", None
            return PhoneReply("Processing your voice recording. Please wait, then ask for status. Do not read another sample yet.")
        permit = await self.bridge.call("permit", flow.user_id, flow.credentials)
        flow.permit, flow.phase = permit, "sample"
        flow.issued = time.monotonic()
        prefix = "Sample not saved. Please try again. " if state["notice"] else ""
        flow.prompt = f"{prefix}Sample {permit['count'] + 1} of {state['target']}. Read aloud: {permit['prompt']}"
        return PhoneReply(flow.prompt, True)

    async def handle(self, frame):
        if self.closing:
            record("flow", "closing")
            return PhoneReply("Phone voice learning is unavailable.")
        async with asyncio.timeout(60), self.lock:
            previous = self.flows.get(self.key(frame))
            if previous is not None:
                continuity = "expired_scope" if previous.expires <= time.monotonic() else "same_scope"
            elif any(flow.connection is frame.connection and flow.user_id == frame.user_id
                     for flow in self.flows.values()):
                continuity = "chat_changed"
            elif any(flow.user_id == frame.user_id for flow in self.flows.values()):
                continuity = "connection_changed"
            elif any(flow.connection is frame.connection for flow in self.flows.values()):
                continuity = "account_changed"
            else:
                continuity = "new_scope"
            record("flow", "received", control=control_category(frame.text), continuity=continuity,
                   phase=previous.phase if previous is not None else "none", audio_bytes=len(frame.audio))
            # No audio/consent may survive into a different chat or connection.
            for key, previous in list(self.flows.items()):
                if previous.expires <= time.monotonic():
                    self.flows.pop(key, None)
                elif (previous.connection is frame.connection and previous.user_id == frame.user_id
                      and previous.conversation_id != frame.conversation_id
                      and not await self._pause(key, previous)):
                    return PhoneReply("The previous learning session needs attention or is still processing. Check Voice Match management before starting again.")
            key = self.key(frame)
            flow = self.flows.get(key)
            command = frame.text.casefold().strip(" .!?\r\n\t")
            if command in STOP:
                if flow is None:
                    record("flow", "stop_no_session")
                    return PhoneReply("Voice learning has not started.")
                if await self._pause(key, flow):
                    record("flow", "stop_paused")
                    return PhoneReply("Voice learning is paused. Partial samples are kept for an explicitly consented resume.")
                record("flow", "stop_unverified")
                return PhoneReply("I could not verify the pause. Processing may still be running; check Voice Match management.")
            if flow is None:
                if len(self.flows) >= 16:
                    return PhoneReply("Phone learning is busy. Try again later.")
                own = await self.bridge.call("own_profile", frame.user_id, {})
                if not own.get("id"):
                    return PhoneReply("You need an existing voice profile explicitly assigned to your account. Ask an administrator to check Voice Match management.")
                flow = PhoneFlow(frame.connection, frame.user_id, frame.conversation_id, own["id"])
                self.flows[key] = flow
                record("flow", "notice_new")
                return PhoneReply(NOTICE, True)  # Even an initial 'yes' is never consent.
            if frame.started_at <= flow.issued:
                record("flow", "stale_turn")
                return PhoneReply("That recording began before the current prompt. Please wait for the prompt to finish and record again.")
            if flow.phase == "consent":
                if command != "yes":
                    record("flow", "notice_repeat")
                    return PhoneReply(NOTICE, True)
                flow.phase, flow.expires = "attention", time.monotonic() + 900
                result = await self.bridge.call("begin", frame.user_id, {
                    "id": flow.profile_id, "source": flow.source, "own_only": True,
                    "consent": True, "isolation_confirmed": True,
                })
                flow.credentials = {"session_token": result["session_token"], "source": flow.source}
                return await self._next(flow)  # Consent audio is discarded, never submitted.
            if flow.phase in {"processing", "attention"} or command in STATUS:
                if flow.credentials is not None:
                    return await self._next(flow)  # Status/recovery turns are not samples.
                return PhoneReply("Setup could not be verified. Check Voice Match management; do not repeat setup blindly.")
            permit, flow.permit = flow.permit, None
            if permit is None:
                return PhoneReply("There is no recording permit. Ask for status before recording again.")
            flow.phase = "attention"  # Lost/cancelled responses cannot reuse this clip.
            await self.bridge.call("sample", frame.user_id, {
                **flow.credentials, "permit": permit["permit"],
                "audio": base64.b64encode(frame.audio).decode(),
            })
            return await self._next(flow)

    async def disconnect(self, connection):
        async with self.lock:
            results = [await self._pause(key, flow) for key, flow in list(self.flows.items())
                       if flow.connection is connection]
            return all(results)

    async def shutdown(self):
        self.closing = True
        async with self.lock:
            results = await asyncio.gather(*(self._pause(key, flow) for key, flow in list(self.flows.items())))
            return all(results)
