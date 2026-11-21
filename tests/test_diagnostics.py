"""Tests for the Flashforge diagnostics."""

import json

import pytest
from homeassistant.core import HomeAssistant

from custom_components.flashforge.diagnostics import (
    async_get_config_entry_diagnostics,
)

from . import init_integration

# Layer in the printing response, see const_response.
PRINT_LAYER = 44


@pytest.mark.asyncio
@pytest.mark.usefixtures("enable_custom_integrations", "mock_printer_network")
async def test_diagnostics_leave_out_private_data(hass: HomeAssistant) -> None:
    """Test the diagnostics have the printer state but nothing private."""
    entry = await init_integration(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    dumped = json.dumps(diagnostics, default=str)

    assert diagnostics["printer"]["machine_type"] == "Flashforge Adventurer 4"
    assert diagnostics["printer"]["machine_status"] == "BUILDING_FROM_SD"
    assert diagnostics["coordinator"]["print_layer"] == PRINT_LAYER
    # Serial number (also the title), IP address and MAC address.
    for private in ("SNADVA1234567", "Adventurer4", "127.0.0.1", "88:A9:A7"):
        assert private not in dumped
