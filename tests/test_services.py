"""Tests for the Flashforge services."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.flashforge.const import DOMAIN

from . import init_integration
from .const_response import STATUS_PRINTING, STATUS_READY

if TYPE_CHECKING:
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


async def _set_status(
    hass: HomeAssistant, entry_id: str, network: MagicMock, response: str
) -> None:
    network.sendStatusRequest.side_effect = None
    network.sendStatusRequest.return_value = response
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("BUILDING_COMPLETED", "Clear the bed and confirm on the printer's screen"),
        ("BUILDING_FROM_SD", "The printer is BUILDING_FROM_SD"),
    ],
)
async def test_print_file_needs_ready(
    enable_custom_integrations,
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
    status: str,
    message: str,
):
    """Test a print is only started when the printer is READY."""
    entry = await init_integration(hass)
    response = STATUS_PRINTING.replace("BUILDING_FROM_SD", status)
    await _set_status(hass, entry.entry_id, mock_printer_network, response)

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            DOMAIN, "print_file", {"file_name": "test.gcode"}, blocking=True
        )
    mock_printer_network.sendPrintRequest.assert_not_called()


@pytest.mark.asyncio
async def test_print_file_when_ready(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test a print is started when the printer is READY."""
    entry = await init_integration(hass)
    await _set_status(hass, entry.entry_id, mock_printer_network, STATUS_READY)

    await hass.services.async_call(
        DOMAIN, "print_file", {"file_name": "test.gcode"}, blocking=True
    )
    mock_printer_network.sendPrintRequest.assert_awaited_once_with(file="test.gcode")
