"""Support for Freecom MusicPal media player."""
from __future__ import annotations

import logging
from typing import Any

import httpx
import bs4

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
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
    ENDPOINT_ADMIN_CGI,
    ENDPOINT_STATE_CGI,
    ENDPOINT_IPC_SEND,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MusicPal media player from a config entry."""
    host = config_entry.data[CONF_HOST]
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    # Create the media player entity
    async_add_entities([MusicPalMediaPlayer(hass, host, username, password)], True)


class MusicPalMediaPlayer(MediaPlayerEntity):
    """Representation of a MusicPal media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:radio"

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the MusicPal device."""
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._attr_unique_id = f"musicpal_{host.replace('.', '_').replace(':', '_')}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": DEFAULT_NAME,
            "manufacturer": "Freecom",
            "model": "MusicPal",
        }

        # State tracking
        self._attr_state = MediaPlayerState.OFF
        self._attr_volume_level = None
        self._attr_is_volume_muted = False
        self._attr_source = None
        self._attr_source_list = []
        self._attr_media_title = None
        self._attr_media_artist = None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
        )

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
                await self._parse_state(soup.state)
                self._attr_state = MediaPlayerState.ON
            else:
                self._attr_state = MediaPlayerState.OFF

        except (httpx.ConnectError, httpx.TimeoutException) as err:
            _LOGGER.warning("Could not connect to MusicPal at %s: %s", self._host, err)
            self._attr_state = MediaPlayerState.OFF
        except Exception as err:
            _LOGGER.error("Error updating MusicPal: %s", err)

    async def _parse_state(self, state_tag: bs4.Tag) -> None:
        """Parse state information from XML."""
        for tag in state_tag.children:
            if isinstance(tag, bs4.Tag) and tag.name and tag.string:
                # Parse volume, source, current track, etc.
                if tag.name == "volume":
                    try:
                        # Assuming volume is 0-20
                        volume = int(tag.string)
                        self._attr_volume_level = volume / 20.0
                    except (ValueError, TypeError):
                        pass
                elif tag.name == "source":
                    self._attr_source = tag.string
                elif tag.name == "title":
                    self._attr_media_title = tag.string
                elif tag.name == "artist":
                    self._attr_media_artist = tag.string
                elif tag.name == "state":
                    # Parse playing/paused state
                    state_str = tag.string.lower()
                    if "play" in state_str:
                        self._attr_state = MediaPlayerState.PLAYING
                    elif "pause" in state_str:
                        self._attr_state = MediaPlayerState.PAUSED
                    elif "stop" in state_str:
                        self._attr_state = MediaPlayerState.IDLE

    async def _send_command(
        self, command: str, params: dict[str, Any] | None = None
    ) -> None:
        """Send a command to the MusicPal device."""
        try:
            client = get_async_client(self._hass)
            if params is None:
                params = {}
            params["f"] = command

            await client.get(
                f"http://{self._host}{ENDPOINT_ADMIN_CGI}",
                params=params,
                auth=(self._username, self._password),
                timeout=10.0,
            )
            # Request an update after sending a command
            await self.async_update()
        except Exception as err:
            _LOGGER.error("Error sending command %s: %s", command, err)

    async def _send_ipc_command(
        self, command: str, args: list[str] | None = None
    ) -> None:
        """Send an IPC command to the device."""
        try:
            client = get_async_client(self._hass)
            cmd_parts = [command] + (args or [])
            url = f"http://{self._host}{ENDPOINT_IPC_SEND}?" + "&".join(cmd_parts)

            await client.get(
                url,
                auth=(self._username, self._password),
                timeout=10.0,
            )
            # Request an update after sending a command
            await self.async_update()
        except Exception as err:
            _LOGGER.error("Error sending IPC command %s: %s", command, err)

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._send_ipc_command("power_up")

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._send_ipc_command("power_down")

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._send_command("play_pause")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._send_command("play_pause")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._send_command("play_pause")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._send_command("next_song")

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._send_command("volume_inc")

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        await self._send_command("volume_dec")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # Convert 0..1 to 0..20
        volume_value = int(volume * 20)
        await self._send_command(
            "volume_set", {"n": "../now_playing_frame.html", "v": volume_value}
        )
