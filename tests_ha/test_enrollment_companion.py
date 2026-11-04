"""Native HA contracts without real devices, credentials or network pairing."""

from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.voice_match_enrollment import DOMAIN
from custom_components.voice_match_enrollment.coordinator import Coordinator


async def test_setup_registers_controls_but_no_real_speakers(hass):
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://addon:8099", "key": Fernet.generate_key().decode()})
    entry.add_to_hass(hass)
    with patch("custom_components.voice_match_enrollment.bridge_client.BridgeClient.call", AsyncMock(return_value={"ready": True})):
        assert await hass.config_entries.async_setup(entry.entry_id)
    runtime = hass.data[DOMAIN][entry.entry_id]
    assert runtime["speakers"] == {}
    assert runtime["coordinator"].view()["outcome"] == "idle"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_config_flow_masks_key_and_verifies_pairing(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    key = Fernet.generate_key().decode()
    with patch("custom_components.voice_match_enrollment.bridge_client.BridgeClient.call", AsyncMock(return_value={"ready": True})), \
         patch("custom_components.voice_match_enrollment.async_setup_entry", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            "url": "http://addon:8099/", "key": key,
        })
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"url": "http://addon:8099", "key": key}


async def test_ws_rejects_unregistered_speaker_and_spoofed_user(hass, hass_ws_client):
    assert await async_setup_component(hass, DOMAIN, {})
    coordinator = Coordinator(AsyncMock())
    hass.data[DOMAIN]["test"] = {"coordinator": coordinator, "speakers": {}}
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": DOMAIN + "/manage", "entry_id": "test",
                           "action": "start", "voice_id": "voice", "satellite_id": "assist_satellite.fake",
                           "consent": True})
    result = await client.receive_json()
    assert result["success"] is False
    assert result["error"]["code"] == "not_ready"
    assert not coordinator.running
    await client.send_json({"id": 2, "type": DOMAIN + "/manage", "entry_id": "test",
                           "action": "status", "user_id": "someone_else"})
    result = await client.receive_json()
    assert result["success"] is False
    assert result["error"]["code"] == "invalid_format"


async def test_ws_cannot_inspect_or_cancel_another_users_session(hass, hass_ws_client):
    assert await async_setup_component(hass, DOMAIN, {})
    coordinator = Coordinator(AsyncMock())
    coordinator.actor_id = "another-account"
    hass.data[DOMAIN]["test"] = {"coordinator": coordinator, "speakers": {}}
    user = await hass.auth.async_create_user("Test user", group_ids=["system-users"])
    refresh = await hass.auth.async_create_refresh_token(user, client_id="http://test-client")
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))
    for index, action in enumerate(("status", "cancel"), 1):
        await client.send_json({"id": index, "type": DOMAIN + "/manage", "entry_id": "test", "action": action})
        result = await client.receive_json()
        assert result["success"] is False
        assert result["error"]["code"] == "unauthorized"


async def test_ws_start_uses_authenticated_caller_not_device_or_profile_name(hass, hass_ws_client, hass_admin_user):
    assert await async_setup_component(hass, DOMAIN, {})
    coordinator = Coordinator(AsyncMock())
    coordinator.start = AsyncMock()
    speaker = object()  # Trusted in-process stand-in; no real device is registered.
    hass.data[DOMAIN]["test"] = {"coordinator": coordinator, "speakers": {"assist_satellite.test": speaker}}
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": DOMAIN + "/manage", "entry_id": "test",
        "action": "start", "voice_id": "profile-id", "satellite_id": "assist_satellite.test", "consent": True})
    result = await client.receive_json()
    assert result["success"] is True
    coordinator.start.assert_awaited_once_with(hass_admin_user.id, "profile-id", speaker, consent=True)


async def test_bad_pairing_is_not_saved_and_does_not_echo_the_key(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {
        "url": "http://addon:8099", "key": "synthetic-invalid-key",
    })
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert "synthetic-invalid-key" not in str(result)
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_unload_refuses_to_forget_unverified_device_restoration(hass):
    from custom_components.voice_match_enrollment import async_unload_entry
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN)
    coordinator = Coordinator(AsyncMock())
    coordinator._state.update(outcome="attention", restored=False)
    coordinator.cancel = AsyncMock()
    runtime = {"coordinator": coordinator, "speakers": {}}
    hass.data[DOMAIN][entry.entry_id] = runtime
    assert not await async_unload_entry(hass, entry)
    assert hass.data[DOMAIN][entry.entry_id] is runtime
    coordinator.cancel.assert_awaited_once()
