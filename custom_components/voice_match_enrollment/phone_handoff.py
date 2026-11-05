"""Bounded one-turn RAM handoff; marker text is not a recording credential."""

import asyncio
import time
from dataclasses import dataclass

from .phone_diagnostics import record
from .phone_flow import PhoneFrame


@dataclass(repr=False)
class Pending:
    connection: object
    user_id: str
    session: object
    started_at: float
    frame: PhoneFrame | None = None
    timer: object = None


class PhoneHandoffs:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.pending = {}
        self.busy = {}
        self.closed = False

    def reserve(self, connection, user_id, session):
        task = asyncio.current_task()
        if (self.closed or task is None or session is None or len(self.pending) >= 8
                or id(connection) in self.busy or task in self.pending):
            raise ValueError("Phone recording unavailable")
        pending = Pending(connection, user_id, session, self.clock())
        self.pending[task] = pending
        self.busy[id(connection)] = task
        pending.timer = asyncio.get_running_loop().call_later(60, self.discard, task)
        task.add_done_callback(self.discard)
        return task

    def put(self, owner, audio, text):
        pending = self.pending.get(owner)
        if pending is None or self.clock() - pending.started_at >= 60:
            raise ValueError("Recording expired")
        pending.frame = PhoneFrame(pending.connection, pending.user_id,
            pending.session.conversation_id, pending.started_at, audio, text)

    def take(self, connection, user_id, session, conversation_id):
        task = asyncio.current_task()
        pending = self.pending.pop(task, None)
        if pending is None:
            record("handoff", "missing")
            return None
        pending.timer.cancel()
        valid = (pending.connection is connection and pending.user_id == user_id
                 and pending.session is session and session is not None
                 and session.conversation_id == conversation_id
                 and self.clock() - pending.started_at < 60)
        if not valid and pending.frame is not None:
            pending.frame.audio, pending.frame.text = b"", ""
        record("handoff", "consumed" if valid else "expired"
               if self.clock() - pending.started_at >= 60 else "binding_mismatch")
        # The connection stays reserved until the native pipeline task ends,
        # including its TTS stage. Overlapping phone turns fail closed.
        return pending.frame if valid else None

    def discard(self, task):
        pending = self.pending.pop(task, None)
        if pending is not None:
            record("handoff", "expired" if self.clock() - pending.started_at >= 60 else "discarded")
            pending.timer.cancel()
            if pending.frame is not None:
                pending.frame.audio, pending.frame.text = b"", ""
        for connection, owner in list(self.busy.items()):
            if owner is task:
                self.busy.pop(connection, None)

    def drop_connection(self, connection):
        owner = self.busy.get(id(connection))
        if owner is not None:
            self.discard(owner)

    def close(self):
        self.closed = True
        for owner in list(self.pending):
            self.discard(owner)
        self.busy.clear()
