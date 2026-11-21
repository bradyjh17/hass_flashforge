"""Smooth the current layer reported by the printer."""

from __future__ import annotations

STATUS_PRINTING = "BUILDING_FROM_SD"
STATUS_PAUSED = "PAUSED"


class LayerFilter:
    """
    Remove the short upward jumps from the current layer while printing.

    The printer seems to derive the layer from the nozzle height, so a travel
    move with Z hop reads a layer or two too high for one update, and the
    nozzle waiting above the bed before the first layer reads as layer 20 or
    more. Those readings only ever jump up, so while printing the lower of the
    last two readings is taken, and the shown layer never goes back. Outside a
    print the reading is passed through unchanged.
    """

    def __init__(self) -> None:
        """Initialize."""
        self.value: int | None = None
        self._last: int | None = None
        self._total: int | None = None

    def update(self, status: str | None, layer: int | None, total: int | None) -> None:
        """Update with the latest reading from the printer."""
        if layer is None:
            return
        if status == STATUS_PAUSED and self.value is not None:
            # Hold while paused, the nozzle is parked away from the print.
            self._last = layer
            return
        if (
            status != STATUS_PRINTING
            or layer == 0
            or self._last is None
            or total != self._total
        ):
            # Not printing, or a new print: start over from this reading.
            self.value = layer
        else:
            candidate = min(self._last, layer)
            self.value = max(self.value or 0, candidate)
        if total:
            self.value = min(self.value, total)
        self._last = layer
        self._total = total
