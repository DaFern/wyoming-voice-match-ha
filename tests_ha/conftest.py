"""Real-HA framework contracts, separate from the add-on unit suite."""

import pytest


@pytest.fixture(autouse=True)
def enable_companion(enable_custom_integrations):
    yield
