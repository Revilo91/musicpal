"""Diagnostics support for the MusicPal integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import MusicPalConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MusicPalConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        },
        # The raw state document is the most useful thing to look at when the
        # media player state does not match what the device is doing.
        "device": {
            "state": data.state if data else None,
            "volume": data.volume if data else None,
            "now_playing": data.now_playing if data else None,
            "favorites": data.favorites if data else None,
            "uptime": str(data.uptime) if data and data.uptime else None,
            "info": data.info if data else None,
        },
        "upnp": coordinator.upnp.as_dict(),
    }
