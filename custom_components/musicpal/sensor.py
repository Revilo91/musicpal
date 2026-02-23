"""Support for MusicPal sensors."""
from __future__ import annotations

import logging
from typing import Any

import httpx
import bs4

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    ENDPOINT_STATE_CGI,
    ENDPOINT_ADMIN_CGI,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MusicPal sensors from a config entry."""
    host = config_entry.data[CONF_HOST]
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    sensors = [
        MusicPalStateSensor(hass, host, username, password, "volume", "Volume", "mdi:volume-high"),
        MusicPalStateSensor(hass, host, username, password, "source", "Source", "mdi:radio"),
        MusicPalStateSensor(hass, host, username, password, "title", "Title", "mdi:music-note"),
        MusicPalStateSensor(hass, host, username, password, "artist", "Artist", "mdi:account-music"),
        MusicPalStateSensor(hass, host, username, password, "album", "Album", "mdi:album"),
        MusicPalStateSensor(hass, host, username, password, "state", "State", "mdi:information"),
        MusicPalUptimeSensor(hass, host, username, password),
    ]

    async_add_entities(sensors, True)


class MusicPalStateSensor(SensorEntity):
    """Representation of a MusicPal state sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        state_key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the MusicPal sensor."""
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._state_key = state_key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"musicpal_{host.replace('.', '_').replace(':', '_')}_{state_key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": DEFAULT_NAME,
            "manufacturer": "Freecom",
            "model": "MusicPal",
        }
        self._attr_native_value = None

    async def async_update(self) -> None:
        """Fetch latest state from the device."""
        try:
            client = get_async_client(self._hass)
            response = await client.get(
                f"http://{self._host}{ENDPOINT_STATE_CGI}",
                params={"fav": 0},
                auth=(self._username, self._password),
                timeout=10.0,
            )
            response.raise_for_status()

            # Parse state from response
            soup = bs4.BeautifulSoup(response.content, "lxml")
            if soup.state:
                for tag in soup.state.children:
                    if isinstance(tag, bs4.Tag) and tag.name == self._state_key:
                        self._attr_native_value = tag.string
                        break
            else:
                self._attr_native_value = None

        except (httpx.ConnectError, httpx.TimeoutException) as err:
            _LOGGER.warning("Could not connect to MusicPal at %s: %s", self._host, err)
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error("Error updating MusicPal sensor %s: %s", self._state_key, err)


class MusicPalUptimeSensor(SensorEntity):
    """Representation of a MusicPal uptime sensor."""

    _attr_has_entity_name = True
    _attr_name = "Uptime"
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = "s"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the MusicPal uptime sensor."""
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._attr_unique_id = f"musicpal_{host.replace('.', '_').replace(':', '_')}_uptime"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": DEFAULT_NAME,
            "manufacturer": "Freecom",
            "model": "MusicPal",
        }
        self._attr_native_value = None

    async def async_update(self) -> None:
        """Fetch latest uptime from the device."""
        try:
            client = get_async_client(self._hass)
            response = await client.get(
                f"http://{self._host}{ENDPOINT_ADMIN_CGI}",
                params={"f": "uptime", "n": "../empty.html"},
                auth=(self._username, self._password),
                timeout=10.0,
            )
            response.raise_for_status()

            # Parse uptime from response
            soup = bs4.BeautifulSoup(response.content, "lxml")
            if soup.string:
                parts = soup.string.strip().split()
                if len(parts) >= 2:
                    try:
                        self._attr_native_value = float(parts[1])
                    except (ValueError, IndexError):
                        self._attr_native_value = None

        except (httpx.ConnectError, httpx.TimeoutException) as err:
            _LOGGER.warning("Could not connect to MusicPal at %s: %s", self._host, err)
            self._attr_native_value = None
        except Exception as err:
            _LOGGER.error("Error updating MusicPal uptime sensor: %s", err)
