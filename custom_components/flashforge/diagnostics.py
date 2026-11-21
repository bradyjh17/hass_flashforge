"""Diagnostics for the Flashforge integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_IP_ADDRESS

from .const import CONF_SERIAL_NUMBER, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .data_update_coordinator import FlashForgeDataUpdateCoordinator

TO_REDACT = {CONF_IP_ADDRESS, CONF_SERIAL_NUMBER, "title", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """
    Return diagnostics for a config entry.

    Serial number, IP and MAC address are left out, and file names too as
    they can be personal. What's left helps adding support for other models.
    """
    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    printer = coordinator.printer
    data = coordinator.data or {}

    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
            },
            TO_REDACT,
        ),
        "printer": {
            "machine_type": printer.machine_type,
            "firmware": printer.firmware,
            "machine_status": printer.machine_status,
            "move_mode": printer.move_mode,
            "status": printer.status,
            "print_percent": printer.print_percent,
            "print_layer": printer.print_layer,
            "job_layers": printer.job_layers,
            "printing_a_file": bool(printer.job_file),
            "extruders": [
                {"now": tool.now, "target": tool.target}
                for tool in printer.extruder_tools
            ],
            "beds": [
                {"now": tool.now, "target": tool.target} for tool in printer.bed_tools
            ],
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "failed_updates": coordinator.failedupdates,
            "files_on_printer": len(data.get("files") or []),
            "print_layer": coordinator.print_layer,
            "job_remaining": coordinator.job_remaining,
            "job_end": coordinator.job_end,
        },
    }
