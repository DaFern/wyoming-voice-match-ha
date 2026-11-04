"""Phone-only runtime; no device-ID or accountless-satellite fallback."""

import asyncio

from .phone_flow import PhoneController
from .phone_handoff import PhoneHandoffs


class PhoneRuntime:
    def __init__(self, hass, entry, bridge, source_id):
        self.hass, self.entry, self.source_id = hass, entry, source_id
        self.controller = PhoneController(bridge)
        self.frames = PhoneHandoffs()
        self.connections = {}
        self.cleanup_tasks = set()

    def watch(self, connection):
        if self.controller.closing:
            raise ValueError("Phone learning is stopping")
        if id(connection) in self.connections:
            return
        if len(self.connections) >= 32:
            raise ValueError("Too many phone connections")
        key = ("voice_match_enrollment_phone", self.entry.entry_id)
        self.connections[id(connection)] = (connection, key)
        def disconnect():
            self.connections.pop(id(connection), None)
            self.frames.drop_connection(connection)  # Drop raw audio synchronously.
            if not self.hass.is_stopping:
                task = self.hass.async_create_background_task(
                    self.controller.disconnect(connection), "phone_voice_learning_disconnect")
                self.cleanup_tasks.add(task)
                task.add_done_callback(self.cleanup_tasks.discard)
        connection.subscriptions[key] = disconnect

    async def shutdown(self):
        ready = await self.controller.shutdown()
        if self.cleanup_tasks:
            await asyncio.gather(*list(self.cleanup_tasks), return_exceptions=True)
        if ready:
            self.frames.close()
            for connection, key in self.connections.values():
                connection.subscriptions.pop(key, None)
            self.connections.clear()
        return ready
