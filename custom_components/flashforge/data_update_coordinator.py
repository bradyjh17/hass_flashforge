"""DataUpdateCoordinator for flashforge integration."""

import asyncio
import logging
import time
from datetime import datetime, timedelta

from ffpp.Printer import ConnectionStatus, Printer
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    MAX_FAILED_UPDATES,
    SCAN_INTERVAL,
    UPDATE_TIMEOUT,
)
from .estimator import PrintTimeEstimator
from .layers import LayerFilter

_LOGGER = logging.getLogger(__name__)


def _to_float(value: object) -> float | None:
    """Convert a printer value, ffpp 0.0.15 returns numbers as strings."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    """Convert a printer value to a whole number."""
    number = _to_float(value)
    return None if number is None else int(number)


class FlashForgeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FlashForgeprinter data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, printer: Printer, config_entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DEFAULT_NAME}-{config_entry.entry_id}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            update_method=self.async_update_data,
        )
        self.config_entry = config_entry
        self.printer = printer
        self._printer_offline = False
        self.data = {
            "status": None,
        }
        self.failedupdates = 0
        self._updated_once = False
        self._estimator = PrintTimeEstimator()
        self._layer_filter = LayerFilter()
        self.job_remaining: int | None = None
        self.job_end: datetime | None = None

    async def async_update_data(self) -> dict[str, list[str] | str | None]:
        """Update data via API."""
        try:
            async with asyncio.timeout(UPDATE_TIMEOUT):
                await self.printer.update()
                files = await self.printer.network.sendGetFileNames()
        except OSError as err:
            # TimeoutError and ConnectionError are both OSErrors.
            # ffpp 0.0.15 keeps the socket open when a request is cancelled,
            # the next request would read the stale reply. Start over.
            await self.printer.network.disconnect()
            if isinstance(err, TimeoutError):
                msg = f"No answer from the printer within {UPDATE_TIMEOUT} s"
            else:
                msg = f"Can't connect to the printer: {err}"
            self.failedupdates += 1
            if self.failedupdates >= MAX_FAILED_UPDATES or not self._updated_once:
                raise UpdateFailed(msg) from err
            # Ride out a short glitch: keep the last values until the next poll
            # instead of retrying right away.
            _LOGGER.debug("%s (%s of %s)", msg, self.failedupdates, MAX_FAILED_UPDATES)
            return self.data

        if not files:
            files = []
        files = [f.removeprefix("/data/") for f in files]
        self.failedupdates = 0
        self._updated_once = True
        self._update_job_estimate()
        self._layer_filter.update(
            status=self.printer.machine_status,
            layer=_to_int(self.printer.print_layer),
            total=_to_int(self.printer.job_layers),
        )

        return {"status": self.printer.machine_status, "files": files}

    @property
    def print_layer(self) -> int | None:
        """Current layer, without the printer's short jumps."""
        return self._layer_filter.value

    def _update_job_estimate(self) -> None:
        self._estimator.update(
            status=self.printer.machine_status,
            progress=_to_float(self.printer.print_percent),
            now=time.monotonic(),
        )
        remaining = self._estimator.remaining
        if remaining is None:
            self.job_remaining = None
            self.job_end = None
            return
        self.job_remaining = round(remaining / 60)
        end = dt_util.utcnow() + timedelta(seconds=remaining)
        self.job_end = end.replace(second=0, microsecond=0)

    async def async_config_entry_first_refresh(self) -> None:
        """Connect to printer and update with machine info."""
        self.printer.connected = ConnectionStatus.DISCONNECTED
        await self.printer.connect()

        return await super().async_config_entry_first_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        unique_id = self.config_entry.unique_id or ""
        model = self.printer.machine_type
        name = self.printer.machine_name or self.config_entry.title
        firmware = self.printer.firmware
        sn = self.printer.serial
        mac = self.printer.mac_address

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="FlashForge",
            model=model,
            name=name,
            sw_version=firmware,
            serial_number=sn,
            hw_version=mac,
        )
