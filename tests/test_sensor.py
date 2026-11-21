"""Tests for the Flashforge sensors."""

import asyncio
from datetime import timedelta
from itertools import count
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from custom_components.flashforge.const import DOMAIN, MAX_FAILED_UPDATES

from . import init_integration
from .const_response import STATUS_PRINTING

SENSORS = (
    {
        "entity_id": "sensor.adventurer4_extruder_current",
        "state": "198.0",
        "name": "Adventurer4 Extruder Current",
        "unique_id": "SNADVA1234567_extruder_current",
    },
    {
        "entity_id": "sensor.adventurer4_extruder_target",
        "state": "210.0",
        "name": "Adventurer4 Extruder Target",
        "unique_id": "SNADVA1234567_extruder_target",
    },
    {
        "entity_id": "sensor.adventurer4_bed_current",
        "state": "48.0",
        "name": "Adventurer4 Bed Current",
        "unique_id": "SNADVA1234567_bed_current",
    },
    {
        "entity_id": "sensor.adventurer4_bed_target",
        "state": "64.0",
        "name": "Adventurer4 Bed Target",
        "unique_id": "SNADVA1234567_bed_target",
    },
    {
        "entity_id": "sensor.adventurer4_status",
        "state": "BUILDING_FROM_SD",
        "name": "Adventurer4 Status",
        "unique_id": "SNADVA1234567_status",
    },
    {
        "entity_id": "sensor.adventurer4_job_percentage",
        "state": "11",
        "name": "Adventurer4 Job Percentage",
        "unique_id": "SNADVA1234567_job_percentage",
    },
    {
        # Not enough progress for an estimate.
        "entity_id": "sensor.adventurer4_job_remaining",
        "state": "unknown",
        "name": "Adventurer4 Job Remaining",
        "unique_id": "SNADVA1234567_job_remaining",
    },
    {
        "entity_id": "sensor.adventurer4_job_end",
        "state": "unknown",
        "name": "Adventurer4 Job End",
        "unique_id": "SNADVA1234567_job_end",
    },
)


@pytest.mark.asyncio
async def test_sensors(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test Flashforge sensors."""
    await init_integration(hass)
    registry = entity_registry.async_get(hass)

    for expected in SENSORS:
        state = hass.states.get(expected["entity_id"])
        assert state is not None
        assert state.state == expected["state"]
        assert state.name == expected["name"]
        entry = registry.async_get(expected["entity_id"])
        assert entry.unique_id == expected["unique_id"]


@pytest.mark.asyncio
async def test_unload_integration_and_sensors(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test Flashforge sensors are unavailable and then deleted when integration."""
    entry = await init_integration(hass)

    # Sensor become unavailable when integration unloads.
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    for expected in SENSORS:
        state = hass.states.get(expected["entity_id"])
        assert state.state == STATE_UNAVAILABLE

    # Sensor become None when integration is deleted.
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(SENSORS[0]["entity_id"])
    assert state is None


@pytest.mark.asyncio
async def test_sensor_update_error(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test a short glitch is ridden out, sensors are unavailable after that."""
    entry = await init_integration(hass)
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Change printer respond.
    mock_printer_network.sendStatusRequest.side_effect = ConnectionError("conn_error")

    for _ in range(MAX_FAILED_UPDATES - 1):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.last_update_success
        assert hass.states.get("sensor.adventurer4_status").state == "BUILDING_FROM_SD"

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert "conn_error" in str(coordinator.last_exception)
    for expected in SENSORS:
        state = hass.states.get(expected["entity_id"])
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_sensor_update_error2(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test a printer that times out isn't asked again right away."""
    entry = await init_integration(hass)
    INIT_CALL_COUNT = 3

    # Change printer respond.
    mock_printer_network.sendStatusRequest.side_effect = TimeoutError()

    # Request sensor update.
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    for refresh in range(1, MAX_FAILED_UPDATES + 1):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        # One request per update, no retries in between.
        assert (
            mock_printer_network.sendStatusRequest.call_count
            == INIT_CALL_COUNT + refresh
        )

    assert not coordinator.last_update_success
    assert "No answer from the printer" in str(coordinator.last_exception)
    for expected in SENSORS:
        state = hass.states.get(expected["entity_id"])
        assert state.state == STATE_UNAVAILABLE

    # Still failing, still unavailable.
    await coordinator.async_refresh()
    assert not coordinator.last_update_success


@pytest.mark.asyncio
async def test_sensor_update_hanging_printer(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test that a printer that never answers can't stall the updates."""
    entry = await init_integration(hass)

    async def never_answers(*_args: object, **_kwargs: object) -> str:
        await asyncio.Event().wait()
        return ""

    mock_printer_network.sendStatusRequest.side_effect = never_answers
    mock_printer_network.disconnect.reset_mock()

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    with patch(
        "custom_components.flashforge.data_update_coordinator.UPDATE_TIMEOUT", 0.01
    ):
        for _ in range(MAX_FAILED_UPDATES):
            await asyncio.wait_for(coordinator.async_refresh(), 5)
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    # The connection is reset, a stale reply must not be read next time.
    assert mock_printer_network.disconnect.await_count >= MAX_FAILED_UPDATES
    for expected in SENSORS:
        state = hass.states.get(expected["entity_id"])
        assert state.state == STATE_UNAVAILABLE

    # The printer answers again, the next update recovers.
    mock_printer_network.sendStatusRequest.side_effect = None
    mock_printer_network.sendStatusRequest.return_value = STATUS_PRINTING
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert hass.states.get("sensor.adventurer4_status").state == "BUILDING_FROM_SD"


@pytest.mark.asyncio
async def test_setup_fails_on_first_error(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test setup is retried later when the printer doesn't answer at all."""
    mock_printer_network.sendStatusRequest.side_effect = TimeoutError()

    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_printer_network.sendStatusRequest.call_count == 1


@pytest.mark.asyncio
async def test_remaining_time_estimate(
    enable_custom_integrations, hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test the estimated remaining time and end of a print at 1 % per minute."""
    mock_printer_network.sendStatusRequest.side_effect = None
    mock_printer_network.sendStatusRequest.return_value = STATUS_PRINTING
    mock_printer_network.sendProgressRequest.side_effect = (
        f"CMD M27 Received.\r\nSD printing byte {percent}/100\r\nok\r\n"
        for percent in count()
    )

    with patch(
        "custom_components.flashforge.data_update_coordinator.time"
    ) as mock_time:
        mock_time.monotonic.side_effect = count(0, 60)
        entry = await init_integration(hass)
        coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        # Connecting read 0 %, the two coordinator updates during setup 1 % and
        # 2 %. The first step was to 2 %, so 7 % is needed for an estimate.
        for _ in range(5):
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    # 7 % done, 93 % left.
    assert hass.states.get("sensor.adventurer4_job_percentage").state == "7"
    assert hass.states.get("sensor.adventurer4_job_remaining").state == "93"
    job_end = dt_util.parse_datetime(
        hass.states.get("sensor.adventurer4_job_end").state
    )
    expected_end = dt_util.utcnow() + timedelta(minutes=93)
    assert abs(job_end - expected_end) < timedelta(minutes=2)
