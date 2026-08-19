"""The MusicPal integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from aiohttp import web as aiohttp_web
from homeassistant.components.network import async_get_source_ip
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    UPNP_NOTIFY_PATH,
    UPNP_RENEWAL_INTERVAL,
)
from .coordinator import MusicPalDataUpdateCoordinator
from .upnp_events import (
    AVT_SERVICE_TYPE,
    RC_SERVICE_TYPE,
    discover_upnp_services,
    parse_upnp_notify_body,
    upnp_subscribe,
    upnp_unsubscribe,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.SENSOR]

MusicPalConfigEntry = ConfigEntry[MusicPalDataUpdateCoordinator]

# hass.data[DOMAIN] key holding the shared "SID -> callback" dispatch table
# for the single, globally registered UPnP NOTIFY route.
_UPNP_CALLBACKS = "upnp_callbacks"

NotifyCallback = Callable[[dict[str, str]], None]
CallbackTable = dict[str, NotifyCallback]


# =============================================================================
# Setup / teardown
# =============================================================================


async def async_setup_entry(
    hass: HomeAssistant, entry: MusicPalConfigEntry
) -> bool:
    """Set up MusicPal from a config entry."""
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = MusicPalDataUpdateCoordinator(hass, entry, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Probing for UPnP can take several seconds on devices that do not speak
    # it at all, so never let it delay setup.  Polling works regardless.
    entry.async_create_background_task(
        hass,
        _async_setup_upnp(hass, entry, coordinator),
        name=f"{DOMAIN}-upnp-setup-{entry.entry_id}",
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MusicPalConfigEntry
) -> bool:
    """Unload a config entry."""
    # Registered UPnP cleanup runs through entry.async_on_unload().
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: MusicPalConfigEntry
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


# =============================================================================
# UPnP eventing (best effort — the integration falls back to polling)
# =============================================================================


@callback
def _async_register_notify_route(hass: HomeAssistant) -> CallbackTable:
    """Register the shared UPnP NOTIFY route once per Home Assistant run.

    Returns the ``SID -> callback`` dispatch table used by the route.
    """
    domain_data: dict[str, Any] = hass.data.setdefault(DOMAIN, {})
    existing: CallbackTable | None = domain_data.get(_UPNP_CALLBACKS)
    if existing is not None:
        return existing

    callbacks: CallbackTable = {}
    domain_data[_UPNP_CALLBACKS] = callbacks

    async def _handle_notify(
        request: aiohttp_web.Request,
    ) -> aiohttp_web.Response:
        """Dispatch an incoming UPnP NOTIFY request to its subscriber."""
        cb = callbacks.get(request.headers.get("SID", ""))
        if cb is not None and (
            state_vars := parse_upnp_notify_body(await request.read())
        ):
            cb(state_vars)
        return aiohttp_web.Response(status=200)

    hass.http.app.router.add_route("NOTIFY", UPNP_NOTIFY_PATH, _handle_notify)
    _LOGGER.debug("Registered UPnP NOTIFY route at %s", UPNP_NOTIFY_PATH)
    return callbacks


async def _async_setup_upnp(
    hass: HomeAssistant,
    entry: MusicPalConfigEntry,
    coordinator: MusicPalDataUpdateCoordinator,
) -> None:
    """Subscribe to UPnP AVTransport/RenderingControl events on the device.

    Every failure mode is handled gracefully: when UPnP is unavailable the
    integration simply keeps polling.
    """
    host: str = entry.data[CONF_HOST]
    client = get_async_client(hass)

    try:
        callbacks = _async_register_notify_route(hass)
    except (RuntimeError, ValueError) as err:
        _LOGGER.debug(
            "Could not register UPnP NOTIFY route (%s) — polling only", err
        )
        return

    services = await discover_upnp_services(client, host)
    if not services:
        _LOGGER.debug("No UPnP services on %s — polling only", host)
        return

    local_ip = await async_get_source_ip(hass, host)
    if not local_ip:
        _LOGGER.debug("Could not determine local IP for the UPnP callback")
        return
    port = getattr(hass.http, "server_port", 8123)
    callback_url = f"http://{local_ip}:{port}{UPNP_NOTIFY_PATH}"

    @callback
    def _on_notify(state_vars: dict[str, str]) -> None:
        """Apply a NOTIFY payload to the shared UPnP state."""
        upnp = coordinator.upnp
        changed = False

        if (value := state_vars.get("TransportState")) is not None:
            upnp.transport_state = value
            changed = True
        if (value := state_vars.get("AVTransportURI")) is not None:
            upnp.avt_uri = value or None
            changed = True
        if (value := state_vars.get("CurrentTrackTitle")) is not None:
            upnp.track_title = value or None
            changed = True
        if (value := state_vars.get("Volume")) is not None:
            try:
                upnp.volume = int(value)
                changed = True
            except ValueError:
                pass
        if (value := state_vars.get("Mute")) is not None:
            upnp.muted = value in ("1", "true", "True")
            changed = True

        if changed:
            # Push the new state to the UI right away, then let the debounced
            # refresh reconcile the polled fields (now playing text, volume).
            coordinator.async_update_listeners()
            hass.async_create_task(coordinator.async_request_refresh())

    subscriptions: list[tuple[str, str]] = []

    for service_type in (AVT_SERVICE_TYPE, RC_SERVICE_TYPE):
        event_url = services.get(service_type)
        if not event_url:
            continue
        sid = await upnp_subscribe(client, event_url, callback_url)
        if not sid:
            continue
        callbacks[sid] = _on_notify
        subscriptions.append((sid, event_url))
        _LOGGER.debug(
            "Subscribed to %s on %s (SID: %s)", service_type, host, sid
        )

    if not subscriptions:
        _LOGGER.debug("No UPnP subscriptions established for %s", host)
        return

    async def _renew(_now: Any) -> None:
        """Renew every subscription before it expires."""
        for index, (sid, event_url) in enumerate(list(subscriptions)):
            new_sid = await upnp_subscribe(
                client, event_url, callback_url, sid=sid
            )
            if new_sid is None:
                # Renewal failed — try establishing a fresh subscription.
                new_sid = await upnp_subscribe(client, event_url, callback_url)
            if new_sid is None:
                _LOGGER.debug("Lost UPnP subscription to %s", event_url)
                continue
            if new_sid != sid:
                callbacks.pop(sid, None)
                callbacks[new_sid] = _on_notify
                subscriptions[index] = (new_sid, event_url)

    entry.async_on_unload(
        async_track_time_interval(
            hass, _renew, timedelta(seconds=UPNP_RENEWAL_INTERVAL)
        )
    )

    async def _unsubscribe_all() -> None:
        for sid, event_url in subscriptions:
            callbacks.pop(sid, None)
            await upnp_unsubscribe(client, event_url, sid)

    entry.async_on_unload(_unsubscribe_all)
