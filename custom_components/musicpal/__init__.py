"""The MusicPal integration."""

from __future__ import annotations

import logging
import socket
from datetime import timedelta
from typing import Any, Callable, Optional

import httpx
import voluptuous as vol
from aiohttp import web as aiohttp_web

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    UPNP_NOTIFY_PATH,
    UPNP_RENEWAL_INTERVAL,
)
from .musicpal_api import MusicPalClient
from .upnp_events import (
    AVT_SERVICE_TYPE,
    discover_upnp_services,
    parse_upnp_notify_body,
    upnp_subscribe,
    upnp_unsubscribe,
)

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

    def _make_client() -> MusicPalClient:
        """Create a fresh MusicPalClient from config entry data."""
        return MusicPalClient(
            hostname=entry.data[CONF_HOST],
            username=entry.data.get(CONF_USERNAME, "admin"),
            password=entry.data.get(CONF_PASSWORD, "admin"),
        )

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from API."""
        try:
            async with _make_client() as api:
                state = await api.get_state()
                volume = await api.get_volume()
                favorites = await api.get_favorites()
                uptime = await api.get_uptime()
                now_playing = await api.get_now_playing()

                return {
                    "state": state,
                    "volume": volume,
                    "favorites": favorites,
                    "uptime": uptime,
                    "now_playing": now_playing,
                }
        except httpx.TimeoutException as err:
            raise UpdateFailed(
                f"Timeout communicating with device: {err}"
            ) from err
        except httpx.HTTPError as err:
            raise UpdateFailed(
                f"Error communicating with device: {err}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Shared UPnP state updated by NOTIFY callbacks and read by entities.
    upnp_state: dict[str, Optional[str]] = {
        "transport_state": None,
        "avt_uri": None,
    }

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "make_client": _make_client,
        "upnp_state": upnp_state,
        # Populated by _setup_upnp if subscription succeeds:
        "upnp_avt_sid": None,
        "upnp_avt_event_url": None,
        "upnp_cancel_renewal": None,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_show_message_service(call: ServiceCall) -> None:
        """Handle show_message service call."""
        message = call.data.get("message")
        async with _make_client() as api:
            await api.show_message(message)
        await coordinator.async_request_refresh()

    async def async_show_clock_service(call: ServiceCall) -> None:
        """Handle show_clock service call."""
        async with _make_client() as api:
            await api.show_clock()
        await coordinator.async_request_refresh()

    async def async_reboot_service(call: ServiceCall) -> None:
        """Handle reboot service call."""
        async with _make_client() as api:
            await api.reboot()

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

    # Try to set up real-time UPnP event subscription (best-effort).
    await _setup_upnp(hass, entry, coordinator, upnp_state)

    return True


def _get_local_ip_for(target: str) -> Optional[str]:
    """Return the local IP address that would be used to reach *target*."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((target, 80))
            ip: str = sock.getsockname()[0]
            return ip
    except OSError:
        return None


async def _setup_upnp(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: Any,
    upnp_state: dict[str, Optional[str]],
) -> None:
    """Attempt to subscribe to UPnP AVTransport events on the device.

    Registers a global aiohttp NOTIFY route (once per HA instance) and
    sends a UPnP SUBSCRIBE request.  All failures are handled
    gracefully; the integration falls back to polling when UPnP is
    unavailable.
    """
    host: str = entry.data[CONF_HOST]
    entry_id: str = entry.entry_id

    # Register the NOTIFY route on the aiohttp server (once globally).
    domain_data = hass.data[DOMAIN]
    if "upnp_sid_callbacks" not in domain_data:
        sid_callbacks: dict[str, Callable[[dict[str, str]], None]] = {}
        domain_data["upnp_sid_callbacks"] = sid_callbacks

        async def _handle_notify(
            request: aiohttp_web.Request,
        ) -> aiohttp_web.Response:
            """Dispatch an incoming UPnP NOTIFY request."""
            sid = request.headers.get("SID", "")
            cb = sid_callbacks.get(sid)
            if cb is not None:
                body = await request.read()
                state_vars = parse_upnp_notify_body(body)
                if state_vars:
                    cb(state_vars)
            return aiohttp_web.Response(status=200)

        try:
            hass.http.app.router.add_route(
                "NOTIFY", UPNP_NOTIFY_PATH, _handle_notify
            )
            _LOGGER.debug(
                "Registered UPnP NOTIFY route at %s", UPNP_NOTIFY_PATH
            )
        except RuntimeError as err:
            _LOGGER.debug(
                "Could not register UPnP NOTIFY route: %s — "
                "real-time UPnP events disabled",
                err,
            )
            return
    else:
        sid_callbacks = domain_data["upnp_sid_callbacks"]

    # Discover the device's UPnP service event URLs.
    services = await discover_upnp_services(host)
    if not services or AVT_SERVICE_TYPE not in services:
        _LOGGER.debug(
            "UPnP AVTransport service not found for %s — using polling only",
            host,
        )
        return

    avt_event_url: str = services[AVT_SERVICE_TYPE]

    # Build the callback URL pointing to HA's NOTIFY endpoint.
    local_ip = _get_local_ip_for(host)
    if not local_ip:
        _LOGGER.debug("Could not determine local IP for UPnP callback")
        return
    ha_port = getattr(hass.http, "server_port", 8123)
    callback_url = f"http://{local_ip}:{ha_port}{UPNP_NOTIFY_PATH}"

    # Subscribe to AVTransport events.
    sid = await upnp_subscribe(avt_event_url, callback_url)
    if not sid:
        _LOGGER.debug("UPnP SUBSCRIBE to %s failed", avt_event_url)
        return

    entry_data = hass.data[DOMAIN][entry_id]
    entry_data["upnp_avt_sid"] = sid
    entry_data["upnp_avt_event_url"] = avt_event_url

    def _on_avt_notify(state_vars: dict[str, str]) -> None:
        """Handle an AVTransport NOTIFY event from the device."""
        changed = False
        transport_state = state_vars.get("TransportState")
        if transport_state is not None:
            upnp_state["transport_state"] = transport_state
            changed = True
        avt_uri = state_vars.get("AVTransportURI")
        if avt_uri is not None:
            upnp_state["avt_uri"] = avt_uri
            changed = True
        if changed:
            hass.async_create_task(coordinator.async_request_refresh())

    sid_callbacks[sid] = _on_avt_notify

    # Schedule periodic subscription renewal before it expires.
    async def _renew_subscription(now: Any) -> None:
        current_sid: Optional[str] = entry_data.get("upnp_avt_sid")
        if not current_sid:
            return
        new_sid = await upnp_subscribe(
            avt_event_url, callback_url, sid=current_sid
        )
        if new_sid and new_sid != current_sid:
            # Device issued a new SID on renewal.
            sid_callbacks.pop(current_sid, None)
            sid_callbacks[new_sid] = _on_avt_notify
            entry_data["upnp_avt_sid"] = new_sid

    cancel_renewal = async_track_time_interval(
        hass,
        _renew_subscription,
        timedelta(seconds=UPNP_RENEWAL_INTERVAL),
    )
    entry_data["upnp_cancel_renewal"] = cancel_renewal

    _LOGGER.debug(
        "Subscribed to UPnP AVTransport events on %s (SID: %s)",
        host,
        sid,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})

    # Cancel subscription renewal timer.
    cancel_renewal = entry_data.get("upnp_cancel_renewal")
    if cancel_renewal is not None:
        cancel_renewal()

    # Unsubscribe from UPnP events.
    sid: Optional[str] = entry_data.get("upnp_avt_sid")
    event_url: Optional[str] = entry_data.get("upnp_avt_event_url")
    if sid and event_url:
        await upnp_unsubscribe(event_url, sid)
        domain_data = hass.data.get(DOMAIN, {})
        sid_callbacks = domain_data.get("upnp_sid_callbacks", {})
        sid_callbacks.pop(sid, None)

    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
