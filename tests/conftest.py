"""Fixtures for the MusicPal tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.musicpal.const import DOMAIN

MOCK_CONFIG = {
    CONF_HOST: "192.168.1.50",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "admin",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable loading of the custom integration in every test."""


@pytest.fixture(autouse=True)
def no_upnp() -> Generator[AsyncMock, None, None]:
    """Keep the UPnP discovery probe off the network by default."""
    with patch(
        "custom_components.musicpal.discover_upnp_services",
        AsyncMock(return_value=None),
    ) as mock:
        yield mock


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    """Patch every MusicPalClient method with a working fake device."""
    targets = {
        "get_state": {"display": "Radio Eins - Now playing", "volume": "12"},
        "get_volume": 12,
        "get_now_playing": "Radio Eins Die Neue",
        "get_favorites": [
            {"index": 0, "name": "Radio Eins"},
            {"index": 1, "name": "Deutschlandfunk"},
            {"index": 4, "name": "Jazz Radio"},
        ],
        "get_uptime": timedelta(days=1),
        "get_info": {
            "Firmware version": "1.62",
            "MAC": "00:1a:2b:3c:4d:5e",
        },
        "set_volume": None,
        "volume_up": None,
        "volume_down": None,
        "play_pause": None,
        "next_track": None,
        "play_url": None,
        "power_on": None,
        "power_off": None,
        "play_favorite": None,
        "show_message": None,
        "show_clock": None,
        "reboot": None,
    }

    with (
        patch(
            "custom_components.musicpal.coordinator.MusicPalClient"
        ) as coordinator_cls,
        patch(
            "custom_components.musicpal.config_flow.MusicPalClient"
        ) as flow_cls,
    ):
        client = AsyncMock()
        for name, value in targets.items():
            setattr(client, name, AsyncMock(return_value=value))
        coordinator_cls.return_value = client
        flow_cls.return_value = client
        yield client


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MusicPal config entry added to Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title="MusicPal",
        unique_id=MOCK_CONFIG[CONF_HOST],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> MockConfigEntry:
    """Set up the MusicPal integration with a fake device."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
