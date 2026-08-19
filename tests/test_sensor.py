"""Tests for the MusicPal sensors."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

UPTIME_ID = "sensor.musicpal_last_boot"
DISPLAY_ID = "sensor.musicpal_display"
FAVORITES_ID = "sensor.musicpal_favorites"


async def test_sensors_are_created(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """All three diagnostic sensors exist."""
    for entity_id in (UPTIME_ID, DISPLAY_ID, FAVORITES_ID):
        assert hass.states.get(entity_id) is not None, entity_id


async def test_last_boot_is_a_timestamp(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Uptime is exposed as a stable boot timestamp, not a growing counter."""
    state = hass.states.get(UPTIME_ID)
    assert state is not None
    assert state.attributes["device_class"] == "timestamp"
    # A parsable ISO timestamp, i.e. not "86400.0".
    from homeassistant.util import dt as dt_util

    assert dt_util.parse_datetime(state.state) is not None


async def test_display_sensor(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The display sensor mirrors the device screen."""
    state = hass.states.get(DISPLAY_ID)
    assert state is not None
    assert state.state == "Radio Eins - Now playing"


async def test_favorites_sensor_lists_names(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The favorites sensor counts and names the configured favorites."""
    state = hass.states.get(FAVORITES_ID)
    assert state is not None
    assert state.state == "3"
    assert state.attributes["favorites"] == [
        "Radio Eins",
        "Deutschlandfunk",
        "Jazz Radio",
    ]


async def test_sensors_are_diagnostic(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Sensors are categorised as diagnostic so they stay out of the way."""
    registry = er.async_get(hass)
    for entity_id in (UPTIME_ID, DISPLAY_ID, FAVORITES_ID):
        entry = registry.async_get(entity_id)
        assert entry is not None
        assert entry.entity_category == er.EntityCategory.DIAGNOSTIC
