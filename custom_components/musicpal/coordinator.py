"""Data update coordinator for the MusicPal integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    SLOW_UPDATE_CYCLES,
)
from .musicpal_api import (
    MusicPalAuthError,
    MusicPalClient,
    MusicPalError,
)

_LOGGER = logging.getLogger(__name__)

# Boot time is derived from the reported uptime, so it jitters by the round
# trip time.  Rounding hides that jitter and keeps the timestamp sensor stable.
_BOOT_TIME_TOLERANCE = timedelta(seconds=60)


@dataclass
class UpnpState:
    """Real-time device state received through UPnP NOTIFY events."""

    transport_state: str | None = None
    avt_uri: str | None = None
    track_title: str | None = None
    volume: int | None = None
    muted: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation (for diagnostics)."""
        return {
            "transport_state": self.transport_state,
            "avt_uri": self.avt_uri,
            "track_title": self.track_title,
            "volume": self.volume,
            "muted": self.muted,
        }


@dataclass
class MusicPalData:
    """Snapshot of everything polled from the device."""

    state: dict[str, str] = field(default_factory=dict)
    volume: int | None = None
    now_playing: str = ""
    favorites: list[dict[str, Any]] = field(default_factory=list)
    uptime: timedelta | None = None
    boot_time: datetime | None = None
    info: dict[str, str] = field(default_factory=dict)


class MusicPalDataUpdateCoordinator(DataUpdateCoordinator[MusicPalData]):
    """Poll a MusicPal device, refreshing slow-moving data less often."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        self.host: str = entry.data[CONF_HOST]
        # Reuse Home Assistant's shared httpx client so every poll does not
        # build up a fresh connection pool against the device.
        self.client = MusicPalClient(
            hostname=self.host,
            username=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
            password=entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD),
            client=get_async_client(hass),
        )
        self.upnp = UpnpState()
        self._cycle = 0

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> MusicPalData:
        """Fetch the current device state."""
        previous = self.data
        # Favorites, uptime and the info page barely ever change; refresh them
        # on the first run and then only every SLOW_UPDATE_CYCLES polls.
        refresh_slow = previous is None or self._cycle % SLOW_UPDATE_CYCLES == 0
        self._cycle += 1

        try:
            state = await self.client.get_state()
            volume = await self.client.get_volume()
            now_playing = await self.client.get_now_playing()

            if refresh_slow:
                favorites = await self.client.get_favorites()
                uptime = await self.client.get_uptime()
                info = await self.client.get_info()
            else:
                favorites = previous.favorites if previous else []
                uptime = previous.uptime if previous else None
                info = previous.info if previous else {}
        except MusicPalAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MusicPalError as err:
            raise UpdateFailed(str(err)) from err

        boot_time = previous.boot_time if previous else None
        if uptime is not None:
            candidate = dt_util.utcnow() - uptime
            if (
                boot_time is None
                or abs(candidate - boot_time) > _BOOT_TIME_TOLERANCE
            ):
                boot_time = candidate

        return MusicPalData(
            state=state,
            volume=volume,
            now_playing=now_playing,
            favorites=favorites,
            uptime=uptime,
            boot_time=boot_time,
            info=info,
        )

    def async_invalidate_slow_data(self) -> None:
        """Force the next poll to also refresh favorites, uptime and info."""
        self._cycle = 0
