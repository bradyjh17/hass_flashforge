"""Tests for the current layer filter."""

import pytest

from custom_components.flashforge.layers import LayerFilter

PRINTING = "BUILDING_FROM_SD"

# Current layer readings recorded by Home Assistant during two prints on an
# Adventurer 5M (firmware 5.2.0), repeated readings left out. Each print
# starts after READY and ends with the printer reporting BUILDING_COMPLETED.
# fmt: off
PRINT_105_LAYERS = [
    0, 26, 3, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20,
    21, 24, 21, 23, 24, 25, 26, 28, 29, 30, 31, 33, 34, 35, 36, 37, 38, 39,
    40, 41, 42, 44, 45, 46, 47, 49, 50, 51, 52, 54, 55, 56, 57, 59, 60, 61,
    62, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80,
    81, 82, 83, 84, 86, 87, 88, 89, 91, 92, 93, 94, 96, 99, 103, 105,
]
PRINT_108_LAYERS = [
    0, 3, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 18, 16, 17, 18, 19, 20,
    21, 23, 24, 25, 26, 28, 29, 30, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41,
    42, 44, 45, 46, 49, 50, 49, 50, 51, 52, 54, 55, 56, 57, 61, 60, 61, 64,
    62, 64, 65, 66, 67, 68, 69, 70, 73, 74, 72, 73, 74, 75, 76, 79, 77, 78,
    79, 80, 81, 82, 83, 84, 86, 87, 88, 89, 93, 91, 92, 93, 94, 96, 97, 98,
    99, 102, 104, 107, 108,
]
# fmt: on


def replay(readings: list[int], total: int) -> list[int | None]:
    """Feed a recorded print to the filter, return the layer shown each time."""
    layer_filter = LayerFilter()
    layer_filter.update("READY", 0, 0)
    shown = []
    for layer in readings:
        layer_filter.update(PRINTING, layer, total)
        shown.append(layer_filter.value)
    layer_filter.update("BUILDING_COMPLETED", readings[-1], total)
    shown.append(layer_filter.value)
    return shown


@pytest.mark.parametrize(
    ("readings", "total"), [(PRINT_105_LAYERS, 105), (PRINT_108_LAYERS, 108)]
)
def test_recorded_prints(readings: list[int], total: int) -> None:
    """Test the layer never goes back, has no jumps and ends at the total."""
    shown = replay(readings, total)

    assert shown == sorted(shown)
    assert max(shown) <= total
    assert shown[-1] == total
    for i, value in enumerate(shown[:-1]):
        # Never more than one layer above what the printer reports later on.
        assert value <= min(readings[i + 1 :] or [value]) + 1


def test_waiting_above_the_bed_is_not_shown() -> None:
    """Test the high reading before the first layer is filtered out."""
    shown = replay(PRINT_105_LAYERS, 105)

    assert shown[:4] == [0, 0, 3, 3]


def feed(layer_filter: LayerFilter, readings: list[tuple]) -> list[int | None]:
    """Feed (status, layer, total) readings, return the layer shown each time."""
    shown = []
    for status, layer, total in readings:
        layer_filter.update(status, layer, total)
        shown.append(layer_filter.value)
    return shown


def test_completed_shows_the_last_layer() -> None:
    """Test the last layer isn't held back once the print is completed."""
    readings = [(PRINTING, layer, 108) for layer in (0, 106, 107, 108)]
    readings.append(("BUILDING_COMPLETED", 108, 108))

    assert feed(LayerFilter(), readings) == [0, 0, 106, 107, 108]


def test_new_print_starts_over() -> None:
    """Test the layer starts over for the next print."""
    layer_filter = LayerFilter()
    feed(layer_filter, [(PRINTING, 0, 108), (PRINTING, 50, 108)])
    feed(layer_filter, [(PRINTING, 51, 108), ("BUILDING_COMPLETED", 108, 108)])

    # Started again straight from the printer, without READY in between.
    readings = [(PRINTING, layer, 105) for layer in (0, 2, 3)]
    assert feed(layer_filter, readings) == [0, 0, 2]


def test_paused_holds_the_layer() -> None:
    """Test the layer is held while paused."""
    readings = [(PRINTING, 0, 108), (PRINTING, 10, 108), (PRINTING, 11, 108)]
    readings += [("PAUSED", 40, 108), (PRINTING, 11, 108)]

    assert feed(LayerFilter(), readings) == [0, 0, 10, 10, 11]


def test_no_reading() -> None:
    """Test a missing reading keeps the last value."""
    readings = [(PRINTING, None, None), (PRINTING, 5, 108), (PRINTING, None, 108)]

    assert feed(LayerFilter(), readings) == [None, 5, 5]


@pytest.mark.parametrize(
    ("readings", "expected"),
    [
        # Waiting above the bed for two and three updates.
        ([0, 26, 26, 2, 2, 3], [0, 0, 26, 26, 2, 2]),
        ([0, 26, 26, 26, 2, 2, 3], [0, 0, 26, 26, 26, 2, 2]),
        # One layer lower isn't enough to go back.
        ([0, 26, 3, 2, 2, 2, 3], [0, 0, 3, 3, 3, 3, 3]),
    ],
)
def test_follows_the_printer_down(readings: list[int], expected: list[int]) -> None:
    """Test a high reading that got through is corrected by two lower ones."""
    shown = feed(LayerFilter(), [(PRINTING, layer, 108) for layer in readings])

    assert shown == expected


def test_paused_reading_is_ignored() -> None:
    """Test a reading while parked doesn't pull the layer down after resuming."""
    readings = [(PRINTING, layer, 108) for layer in (0, 10, 11, 12)]
    readings += [("PAUSED", 0, 108), ("PAUSED", 0, 108), (PRINTING, 12, 108)]

    assert feed(LayerFilter(), readings) == [0, 0, 10, 11, 11, 11, 12]
