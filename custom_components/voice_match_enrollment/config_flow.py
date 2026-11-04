"""Manual pairing for the development companion; no automatic device adoption."""

import probatio
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN
from .bridge_client import BridgeClient, validate_url
from .learning_bridge_protocol import BridgeError


class VoiceMatchEnrollmentConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                from cryptography.fernet import Fernet
                url = validate_url(user_input["url"])
                Fernet(user_input["key"])
                bridge = BridgeClient(url, user_input["key"], async_get_clientsession(self.hass))
                if await bridge.call("hello", None, {}) != {"ready": True}:
                    raise BridgeError("Learning bridge unavailable")
            except (ValueError, BridgeError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Voice Match enrolment (prototype)",
                                               data={"url": url, "key": user_input["key"]})
        return self.async_show_form(step_id="user", errors=errors, data_schema=probatio.Schema({
            probatio.Required("url"): str,
            probatio.Required("key"): selector.TextSelector({"type": selector.TextSelectorType.PASSWORD}),
        }))
