"""Checks and limits for commands sent to the printer."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import UPDATE_TIMEOUT

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ffpp.Printer import Printer

MAX_FILE_NAME_LENGTH = 255
# "~" starts a printer command, "/" and "\" would leave the printer's file folder.
FORBIDDEN_FILE_NAME_CHARS = frozenset("~/\\")


def valid_file_name(value: Any) -> str:
    """
    Return value if it is a plain file name on the printer, else raise vol.Invalid.

    The file name ends up inside a printer command line, so a line break or
    another control character could add commands of its own.
    """
    name = cv.string(value)
    if (
        not name.strip()
        or len(name) > MAX_FILE_NAME_LENGTH
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in name)  # noqa: PLR2004
        or not FORBIDDEN_FILE_NAME_CHARS.isdisjoint(name)
    ):
        msg = "Not a valid file name on the printer"
        raise vol.Invalid(msg)
    return name


@contextlib.asynccontextmanager
async def printer_command(printer: Printer) -> AsyncIterator[None]:
    """
    Limit how long a command may wait for the printer.

    ffpp has no read timeout, so a printer that accepts the connection but
    never answers would hang the action forever.
    """
    try:
        async with asyncio.timeout(UPDATE_TIMEOUT):
            yield
    except OSError as err:
        # TimeoutError and ConnectionError are both OSErrors. ffpp 0.0.15
        # keeps the socket open when a request is cancelled, start over.
        await printer.network.disconnect()
        if isinstance(err, TimeoutError):
            msg = f"No answer from the printer within {UPDATE_TIMEOUT} s"
        else:
            msg = "Can't reach the printer"
        raise HomeAssistantError(msg) from err
