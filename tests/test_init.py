"""Tests for setting up and tearing down the MusicPal integration."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_PLAYING, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.musicpal.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SLOW_UPDATE_CYCLES,
)
from custom_components.musicpal.musicpal_api import (
    MusicPalAuthError,
    MusicPalConnectionError,
)
from custom_components.musicpal.upnp_events import (
    AVT_SERVICE_TYPE,
    parse_upnp_notify_body,
)

from .const import AVT_NOTIFY

ENTITY_ID = "media_player.musicpal"


async def test_setup_and_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The entry sets up and unloads cleanly."""
    assert setup_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    # Home Assistant keeps a restored placeholder state after unloading.
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_setup_retries_when_device_is_unreachable(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """An unreachable device leaves the entry in the retry state."""
    mock_client.get_state.side_effect = MusicPalConnectionError("down")

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Credentials going stale triggers a reauth flow instead of failing."""
    mock_client.get_state.side_effect = MusicPalAuthError("nope")

    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f for f in flows if f["context"]["source"] == "reauth"]


async def test_entity_becomes_unavailable_on_poll_failure(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed poll marks the entity unavailable rather than 'off'."""
    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING

    mock_client.get_state.side_effect = MusicPalConnectionError("down")
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_slow_data_is_polled_less_often(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Favorites and uptime are not re-fetched on every poll cycle."""
    fast_before = mock_client.get_state.await_count
    slow_before = mock_client.get_favorites.await_count

    for _ in range(3):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert mock_client.get_state.await_count == fast_before + 3
    # Well within the slow cycle, so no extra favorites request was made.
    assert mock_client.get_favorites.await_count == slow_before
    assert SLOW_UPDATE_CYCLES > 3


async def test_upnp_notify_updates_state_without_polling(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """A UPnP NOTIFY is applied to the shared state and pushed to the UI."""
    services = {AVT_SERVICE_TYPE: "http://192.168.1.50:1400/AVTransport/evt"}

    with (
        patch(
            "custom_components.musicpal.discover_upnp_services",
            AsyncMock(return_value=services),
        ),
        patch(
            "custom_components.musicpal.upnp_subscribe",
            AsyncMock(return_value="uuid:test-sid"),
        ),
        patch(
            "custom_components.musicpal.async_get_source_ip",
            AsyncMock(return_value="192.168.1.10"),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    callbacks = hass.data[DOMAIN]["upnp_callbacks"]
    assert "uuid:test-sid" in callbacks

    callbacks["uuid:test-sid"](parse_upnp_notify_body(AVT_NOTIFY))
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    assert coordinator.upnp.transport_state == "PLAYING"
    assert coordinator.upnp.avt_uri == "http://stream.example/radio.mp3"

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_PLAYING
    assert state.attributes["media_content_id"] == (
        "http://stream.example/radio.mp3"
    )


async def test_upnp_failure_does_not_block_setup(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Setup succeeds even when the device speaks no UPnP at all."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING


async def test_diagnostics(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Diagnostics expose the raw device state with credentials redacted."""
    from custom_components.musicpal.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    data = await async_get_config_entry_diagnostics(hass, setup_integration)
    assert data["entry"]["data"]["password"] == "**REDACTED**"
    assert data["entry"]["data"]["username"] == "**REDACTED**"
    assert data["entry"]["data"]["host"] == "192.168.1.50"
    assert data["device"]["state"]["display"] == "Radio Eins - Now playing"
    assert "upnp" in data
