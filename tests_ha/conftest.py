"""Real-HA framework contracts, separate from the add-on unit suite."""

import pytest
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def enable_companion(enable_custom_integrations, hass):
    assert await async_setup_component(hass, "homeassistant", {})
    yield
