"""Development companion: no real speaker adapter or automatic pipeline routing."""

DOMAIN = "voice_match_enrollment"


async def async_setup(hass, config):
    from .websocket_api import register
    hass.data.setdefault(DOMAIN, {})
    register(hass)
    return True


async def async_setup_entry(hass, entry):
    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from .bridge_client import BridgeClient
    from .coordinator import Coordinator
    from .learning_bridge_protocol import BridgeError
    bridge = BridgeClient(entry.data["url"], entry.data["key"], async_get_clientsession(hass))
    try:
        if await bridge.call("hello", None, {}) != {"ready": True}:
            raise BridgeError("Learning bridge unavailable")
    except BridgeError:
        raise ConfigEntryNotReady("Learning bridge pairing is unavailable") from None
    coordinator = Coordinator(bridge, task_factory=lambda coroutine:
        entry.async_create_background_task(hass, coroutine, "voice_match_enrollment"))
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator, "speakers": {}}
    return True


async def async_unload_entry(hass, entry):
    runtime = hass.data[DOMAIN].get(entry.entry_id)
    if runtime is not None:
        await runtime["coordinator"].cancel()
        if runtime["coordinator"].view()["restored"] is False:
            return False
        hass.data[DOMAIN].pop(entry.entry_id)
    return True
