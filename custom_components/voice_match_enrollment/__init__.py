"""Account-bound learning companion; no training from ordinary Assist traffic."""

DOMAIN = "voice_match_enrollment"


async def async_setup(hass, config):
    from .launcher import register_panel
    from .websocket_api import register
    hass.data.setdefault(DOMAIN, {})
    register(hass)
    await register_panel(hass)
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
    phone = None
    if entry.options.get("phone_test_enabled", False):
        from .phone_runtime import PhoneRuntime
        from .stt import control_source
        try:
            control_source(hass, entry.options.get("control_stt_engine"))
        except ValueError:
            raise ConfigEntryNotReady("Phone learning needs an ordinary Wyoming Whisper STT source") from None
        phone = PhoneRuntime(hass, entry, bridge, entry.options["control_stt_engine"])
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator, "speakers": {}, "phone": phone}
    if phone is not None:
        from homeassistant.const import Platform
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.STT, Platform.CONVERSATION])
    entry.async_on_unload(entry.add_update_listener(_reload_options))
    return True


async def _reload_options(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    runtime = hass.data[DOMAIN].get(entry.entry_id)
    if runtime is not None:
        await runtime["coordinator"].cancel()
        if runtime["coordinator"].view()["restored"] is False:
            return False
        if runtime.get("phone") is not None:
            from homeassistant.const import Platform
            if not await runtime["phone"].shutdown():
                return False
            if not await hass.config_entries.async_unload_platforms(entry, [Platform.STT, Platform.CONVERSATION]):
                return False
        hass.data[DOMAIN].pop(entry.entry_id)
    return True
