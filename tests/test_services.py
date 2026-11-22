"""Tests for the Flashforge services."""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

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
@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("BUILDING_COMPLETED", "Clear the bed and confirm on the printer's screen"),
        ("BUILDING_FROM_SD", "The printer is BUILDING_FROM_SD"),
    ],
)
async def test_print_file_needs_ready(
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
    status: str,
    message: str,
) -> None:
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
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_print_file_when_ready(
    hass: HomeAssistant, mock_printer_network: MagicMock
) -> None:
    """Test a print is started when the printer is READY."""
    entry = await init_integration(hass)
    await _set_status(hass, entry.entry_id, mock_printer_network, STATUS_READY)

    await hass.services.async_call(
        DOMAIN, "print_file", {"file_name": "test.gcode"}, blocking=True
    )
    mock_printer_network.sendPrintRequest.assert_awaited_once_with(file="test.gcode")


@pytest.mark.asyncio
@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize(
    "file_name",
    [
        "x.gcode\r\n~M104 S280",  # a second printer command after a line break
        "x.gcode\n~M26",
        "~M26",
        "../x.gcode",
        "folder/x.gcode",
        r"folder\x.gcode",
        "x\x00.gcode",
        "",
        "   ",
        "x" * 256,
    ],
)
async def test_print_file_rejects_unsafe_names(
    hass: HomeAssistant, mock_printer_network: MagicMock, file_name: str
) -> None:
    """Test a file name that could add printer commands is never sent."""
    entry = await init_integration(hass)
    await _set_status(hass, entry.entry_id, mock_printer_network, STATUS_READY)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "print_file", {"file_name": file_name}, blocking=True
        )
    mock_printer_network.sendPrintRequest.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_print_file_needs_a_file_name(
    hass: HomeAssistant, mock_printer_network: MagicMock
) -> None:
    """Test print_file without a file name is refused."""
    entry = await init_integration(hass)
    await _set_status(hass, entry.entry_id, mock_printer_network, STATUS_READY)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "print_file", {}, blocking=True)
    mock_printer_network.sendPrintRequest.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_print_file_accepts_usual_names(
    hass: HomeAssistant, mock_printer_network: MagicMock
) -> None:
    """Test names with spaces, brackets and plus signs still print."""
    entry = await init_integration(hass)
    await _set_status(hass, entry.entry_id, mock_printer_network, STATUS_READY)
    name = "Gear+Box (v3.0) final_PETG_1h29m.gcode.3mf"

    await hass.services.async_call(
        DOMAIN, "print_file", {"file_name": name}, blocking=True
    )
    mock_printer_network.sendPrintRequest.assert_awaited_once_with(file=name)


@pytest.mark.asyncio
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_service_gives_up_on_a_silent_printer(
    hass: HomeAssistant, mock_printer_network: MagicMock
) -> None:
    """Test an action stops waiting for a printer that never answers."""
    await init_integration(hass)

    async def never_answer(*_: object, **__: object) -> None:
        await asyncio.Event().wait()

    mock_printer_network.sendPauseRequest.side_effect = never_answer
    mock_printer_network.disconnect.reset_mock()
    with (
        patch("custom_components.flashforge.commands.UPDATE_TIMEOUT", 0.05),
        pytest.raises(HomeAssistantError, match="No answer from the printer"),
    ):
        await hass.services.async_call(DOMAIN, "pause", {}, blocking=True)
    mock_printer_network.disconnect.assert_awaited()


@pytest.mark.asyncio
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_print_button_needs_a_chosen_file(
    hass: HomeAssistant, mock_printer_network: MagicMock
) -> None:
    """Test the Print File button sends nothing without a valid chosen file."""
    entry = await init_integration(hass)
    registry = er.async_get(hass)
    button = registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.unique_id}_print_file"
    )
    select = registry.async_get_entity_id("select", DOMAIN, f"{entry.unique_id}_select")
    assert button
    assert select
    hass.states.async_set(select, "x.gcode\r\n~M26")

    with pytest.raises(HomeAssistantError, match="Choose a file"):
        await hass.services.async_call(
            "button", "press", {"entity_id": button}, blocking=True
        )
    mock_printer_network.sendPrintRequest.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_print_button_prints_the_chosen_file(
    hass: HomeAssistant, mock_printer_network: MagicMock
) -> None:
    """Test the Print File button sends a file chosen from the printer's list."""
    entry = await init_integration(hass)
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data["files"] = ["Gear Box (v3).gcode"]
    registry = er.async_get(hass)
    button = registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.unique_id}_print_file"
    )
    select = registry.async_get_entity_id("select", DOMAIN, f"{entry.unique_id}_select")
    assert button
    assert select
    hass.states.async_set(select, "Gear Box (v3).gcode")

    await hass.services.async_call(
        "button", "press", {"entity_id": button}, blocking=True
    )
    mock_printer_network.sendPrintRequest.assert_awaited_once_with(
        file="Gear Box (v3).gcode"
    )
