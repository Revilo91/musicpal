"""Tests for the MusicPal media player entity."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_VOLUME_SET,
)
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.musicpal.const import DOMAIN
from custom_components.musicpal.musicpal_api import MusicPalConnectionError

ENTITY_ID = "media_player.musicpal"


async def test_entity_state_and_attributes(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The media player reflects the polled device state."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_PLAYING
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == pytest.approx(0.6)
    assert state.attributes["source_list"] == [
        "Radio Eins",
        "Deutschlandfunk",
        "Jazz Radio",
    ]


async def test_entity_is_registered_on_a_device(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Every entity belongs to one MusicPal device."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.device_id is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.manufacturer == "Freecom"
    assert device.sw_version == "1.62"
    assert device.configuration_url == "http://192.168.1.50/"


async def test_volume_set_maps_to_device_steps(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A 0..1 volume level is converted to the device's 0..20 scale."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    mock_client.set_volume.assert_awaited_once_with(10)


async def test_play_is_a_no_op_while_already_playing(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The play/pause toggle is not sent when it would stop playback."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_client.play_pause.assert_not_awaited()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_client.play_pause.assert_awaited_once()


async def test_power_and_next_track(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Power and transport commands reach the device."""
    for service, method in (
        (SERVICE_TURN_ON, mock_client.power_on),
        (SERVICE_TURN_OFF, mock_client.power_off),
        (SERVICE_MEDIA_NEXT_TRACK, mock_client.next_track),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        method.assert_awaited_once()


async def test_select_source_plays_the_right_slot(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Selecting a favorite uses its slot index, not its list position."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, "source": "Jazz Radio"},
        blocking=True,
    )
    # "Jazz Radio" is the third entry in the list but lives in slot 4.
    mock_client.play_favorite.assert_awaited_once_with(4)


async def test_select_unknown_source_raises(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """An unknown favorite name is a user error, not a silent no-op."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, "source": "Does Not Exist"},
            blocking=True,
        )


async def test_play_media(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Playing a URL forwards it to the device."""
    url = "http://stream.example/radio.mp3"
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": url,
        },
        blocking=True,
    )
    mock_client.play_url.assert_awaited_once_with(url)


async def test_device_failures_surface_to_the_caller(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A failing command raises instead of only being logged."""
    mock_client.next_track.side_effect = MusicPalConnectionError("timeout")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def test_custom_entity_services(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """The integration's own services target the entity properly."""
    await hass.services.async_call(
        DOMAIN,
        "show_message",
        {ATTR_ENTITY_ID: ENTITY_ID, "message": "Dinner is ready"},
        blocking=True,
    )
    mock_client.show_message.assert_awaited_once_with("Dinner is ready")

    await hass.services.async_call(
        DOMAIN, "show_clock", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_client.show_clock.assert_awaited_once()

    await hass.services.async_call(
        DOMAIN, "reboot", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_client.reboot.assert_awaited_once()


@pytest.mark.parametrize(
    ("device_state", "expected"),
    [
        # state.cgi reports "0"/"1" strings. A bare truthiness check treats
        # "0" as True, which used to pin the player to "playing" after
        # pausing on the device itself (upstream PR #30).
        ({"display": "Radio", "playing": "1", "paused": "0"}, "playing"),
        ({"display": "Radio", "playing": "0", "paused": "1"}, "paused"),
        ({"display": "Radio", "playing": "0", "paused": "0"}, "idle"),
        # The explicit flags win over the display text.
        ({"display": "Clock", "playing": "1", "paused": "0"}, "playing"),
        # Without flags the display text still decides.
        ({"display": "Clock"}, "off"),
        ({"display": "Paused"}, "paused"),
    ],
)
async def test_state_flags_are_compared_explicitly(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: AsyncMock,
    freezer,
    device_state: dict[str, str],
    expected: str,
) -> None:
    """The device's playing/paused flags are read as "0"/"1", not truthiness."""
    from datetime import timedelta

    from pytest_homeassistant_custom_component.common import (
        async_fire_time_changed,
    )

    from custom_components.musicpal.const import DEFAULT_SCAN_INTERVAL

    mock_client.get_state.return_value = device_state
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == expected
