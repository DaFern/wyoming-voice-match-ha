"""Account-bound coordinator controls, never an audio/device impersonation API."""

import probatio
from homeassistant.components import websocket_api
from homeassistant.exceptions import Unauthorized

from . import DOMAIN


def register(hass):
    from .launcher import launch_info
    websocket_api.async_register_command(hass, manage)
    websocket_api.async_register_command(hass, launch_info)


@websocket_api.websocket_command({
    probatio.Required("type"): DOMAIN + "/manage",
    probatio.Required("entry_id"): str,
    probatio.Required("action"): probatio.In(["start", "status", "cancel"]),
    probatio.Optional("voice_id"): str,
    probatio.Optional("satellite_id"): str,
    probatio.Optional("consent"): bool,
})
@websocket_api.async_response
async def manage(hass, connection, msg):
    user = await hass.auth.async_get_user(connection.user.id)
    if user is None or not user.is_active or user.system_generated:
        raise Unauthorized
    runtime = hass.data[DOMAIN].get(msg["entry_id"])
    if runtime is None:
        connection.send_error(msg["id"], "not_ready", "Learning companion unavailable")
        return
    coordinator = runtime["coordinator"]
    if msg["action"] != "start" and coordinator.actor_id not in (None, user.id) and not user.is_admin:
        raise Unauthorized
    try:
        if msg["action"] == "start":
            # No real device adapters ship yet. A browser-supplied entity ID must
            # match an adapter registered by trusted integration code, not merely
            # an existing device/entity name.
            speaker = runtime["speakers"].get(msg.get("satellite_id"))
            if not msg.get("voice_id"):
                raise ValueError
            await coordinator.start(user.id, msg["voice_id"], speaker, consent=msg.get("consent"))
        elif msg["action"] == "cancel":
            await coordinator.cancel()
    except ValueError:
        connection.send_error(msg["id"], "not_ready", "Fresh consent and a trusted learning adapter are required; another session may be active")
        return
    connection.send_result(msg["id"], coordinator.view())
