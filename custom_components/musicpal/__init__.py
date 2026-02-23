"""The MusicPal integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, SCAN_INTERVAL
from .musicpal_api import MusicPalClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.SENSOR]

SERVICE_SHOW_MESSAGE = "show_message"
SERVICE_SHOW_CLOCK = "show_clock"
SERVICE_REBOOT = "reboot"

SERVICE_SHOW_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("message"): cv.string,
    }
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MusicPal from a config entry."""
    client = MusicPalClient(
        hostname=entry.data[CONF_HOST],
        username=entry.data.get(CONF_USERNAME, "admin"),
        password=entry.data.get(CONF_PASSWORD, "admin"),
    )

    async def async_update_data():
        """Fetch data from API."""
        try:
            async with client as api:
                state = await api.get_state()
                volume = await api.get_volume()
                favorites = await api.get_favorites()
                uptime = await api.get_uptime()

                return {
                    "state": state,
                    "volume": volume,
                    "favorites": favorites,
                    "uptime": uptime,
                }
        except httpx.ConnectError as err:
            raise UpdateFailed(
                f"Error communicating with device: {err}"
            ) from err
        except httpx.HTTPStatusError as err:
            raise UpdateFailed(f"HTTP error from device: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_show_message_service(call: ServiceCall) -> None:
        """Handle show_message service call."""
        message = call.data.get("message")
        async with client:
            await client.show_message(message)
        await coordinator.async_request_refresh()

    async def async_show_clock_service(call: ServiceCall) -> None:
        """Handle show_clock service call."""
        async with client:
            await client.show_clock()
        await coordinator.async_request_refresh()

    async def async_reboot_service(call: ServiceCall) -> None:
        """Handle reboot service call."""
        async with client:
            await client.reboot()

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SHOW_MESSAGE,
        async_show_message_service,
        schema=SERVICE_SHOW_MESSAGE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SHOW_CLOCK,
        async_show_clock_service,
        schema=SERVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REBOOT,
        async_reboot_service,
        schema=SERVICE_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
