"""Support for MusicPal buttons."""
from __future__ import annotations

import logging

import httpx

from homeassistant.components.button import ButtonEntity
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
    ENDPOINT_DEBUG_CGI,
    ENDPOINT_ADMIN_CGI,
    ENDPOINT_IPC_SEND,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MusicPal buttons from a config entry."""
    host = config_entry.data[CONF_HOST]
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    buttons = [
        MusicPalDebugButton(hass, host, username, password, "reboot", "Reboot", "mdi:restart"),
        MusicPalDebugButton(hass, host, username, password, "restart", "Restart Nashville", "mdi:reload"),
        MusicPalAdminButton(hass, host, username, password, "show_clock", "Show Clock", "mdi:clock"),
        MusicPalIpcButton(hass, host, username, password, "menu_collapse", "Close Menu", "mdi:menu-close"),
    ]

    async_add_entities(buttons, True)


class MusicPalDebugButton(ButtonEntity):
    """Representation of a MusicPal debug button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        command: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the MusicPal button."""
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._command = command
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"musicpal_{host.replace('.', '_').replace(':', '_')}_{command}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": DEFAULT_NAME,
            "manufacturer": "Freecom",
            "model": "MusicPal",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            client = get_async_client(self._hass)
            await client.get(
                f"http://{self._host}{ENDPOINT_DEBUG_CGI}",
                params={"f": self._command},
                auth=(self._username, self._password),
                timeout=10.0,
            )
            _LOGGER.info("Executed command %s on MusicPal at %s", self._command, self._host)
        except Exception as err:
            _LOGGER.error("Error executing command %s: %s", self._command, err)


class MusicPalAdminButton(ButtonEntity):
    """Representation of a MusicPal admin button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        command: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the MusicPal button."""
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._command = command
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"musicpal_{host.replace('.', '_').replace(':', '_')}_{command}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": DEFAULT_NAME,
            "manufacturer": "Freecom",
            "model": "MusicPal",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            client = get_async_client(self._hass)
            await client.request(
                method="POST",
                url=f"http://{self._host}{ENDPOINT_ADMIN_CGI}",
                params={"f": self._command},
                auth=(self._username, self._password),
                timeout=10.0,
            )
            _LOGGER.info("Executed command %s on MusicPal at %s", self._command, self._host)
        except Exception as err:
            _LOGGER.error("Error executing command %s: %s", self._command, err)


class MusicPalIpcButton(ButtonEntity):
    """Representation of a MusicPal IPC button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        command: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the MusicPal button."""
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._command = command
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"musicpal_{host.replace('.', '_').replace(':', '_')}_{command}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": DEFAULT_NAME,
            "manufacturer": "Freecom",
            "model": "MusicPal",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            client = get_async_client(self._hass)
            url = f"http://{self._host}{ENDPOINT_IPC_SEND}?{self._command}"
            await client.get(
                url,
                auth=(self._username, self._password),
                timeout=10.0,
            )
            _LOGGER.info("Executed command %s on MusicPal at %s", self._command, self._host)
        except Exception as err:
            _LOGGER.error("Error executing command %s: %s", self._command, err)
