"""Support for MusicPal media player."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_FAVORITES, ATTR_UPTIME, DOMAIN
from .musicpal_api import MusicPalClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MusicPal media player platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]

    async_add_entities([MusicPalMediaPlayer(coordinator, client, config_entry)])


class MusicPalMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a MusicPal media player."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(
        self,
        coordinator,
        client: MusicPalClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the MusicPal media player."""
        super().__init__(coordinator)
        self._client = client
        self._attr_name = "MusicPal"
        self._attr_unique_id = f"{config_entry.data[CONF_HOST]}_media_player"
        self._media_title: str | None = None

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if not self.coordinator.data:
            return MediaPlayerState.OFF

        state_data = self.coordinator.data.get("state", {})
        display = state_data.get("display", "")

        # Try to determine state from display content
        if "clock" in display.lower():
            return MediaPlayerState.IDLE
        if "playing" in display.lower() or state_data.get("playing"):
            return MediaPlayerState.PLAYING
        if "pause" in display.lower() or state_data.get("paused"):
            return MediaPlayerState.PAUSED

        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if not self.coordinator.data:
            return None

        volume = self.coordinator.data.get("volume", 0)
        return volume / 20.0  # Convert from 0-20 to 0-1

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        if not self.coordinator.data:
            return None

        favorites = self.coordinator.data.get("favorites", [])
        return [fav["name"] for fav in favorites]

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._media_title

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self.coordinator.data:
            return {}

        attrs = {}

        if uptime := self.coordinator.data.get("uptime"):
            attrs[ATTR_UPTIME] = str(uptime)

        if favorites := self.coordinator.data.get("favorites"):
            attrs[ATTR_FAVORITES] = len(favorites)

        return attrs

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        try:
            async with self._client:
                await self._client.power_on()
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to turn on MusicPal: %s", err)

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        try:
            async with self._client:
                await self._client.power_off()
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to turn off MusicPal: %s", err)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        try:
            volume_int = int(volume * 20)  # Convert from 0-1 to 0-20
            async with self._client:
                await self._client.set_volume(volume_int)
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to set volume: %s", err)

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        try:
            async with self._client:
                await self._client.volume_up()
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to increase volume: %s", err)

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        try:
            async with self._client:
                await self._client.volume_down()
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to decrease volume: %s", err)

    async def async_media_play(self) -> None:
        """Send play command."""
        try:
            async with self._client:
                await self._client.play_pause()
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to play: %s", err)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        try:
            async with self._client:
                await self._client.play_pause()
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to pause: %s", err)

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        try:
            async with self._client:
                await self._client.next_track()
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to skip to next track: %s", err)

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        try:
            # Get metadata from kwargs (provided by Music Assistant, etc.)
            metadata = kwargs.get("metadata", {})
            title = (
                kwargs.get("title")
                or metadata.get("title")
                or kwargs.get("media_title")
            )
            artist = (
                kwargs.get("artist")
                or metadata.get("artist")
                or kwargs.get("media_artist")
            )
            album = (
                kwargs.get("album")
                or metadata.get("album")
                or kwargs.get("media_album_name")
            )

            # Build display message from available metadata
            if title:
                display_parts = [title]
                if artist:
                    display_parts.append(f"by {artist}")
                if album:
                    display_parts.append(f"({album})")
                display_message = " ".join(display_parts)
                self._media_title = title
            else:
                # No metadata provided
                display_message = "Unknown"
                self._media_title = None

            async with self._client:
                # Show the metadata on the device display
                await self._client.show_message(display_message)
                # Play the media
                await self._client.play_url(media_id)

            _LOGGER.info(
                "Playing media: %s (URL: %s, kwargs: %s)",
                display_message,
                media_id,
                kwargs,
            )
            await self.coordinator.async_request_refresh()
        except httpx.HTTPError as err:
            _LOGGER.error("Failed to play media: %s", err)

    async def async_select_source(self, source: str) -> None:
        """Select input source (favorite)."""
        if not self.coordinator.data:
            return

        favorites = self.coordinator.data.get("favorites", [])
        for fav in favorites:
            if fav["name"] == source:
                try:
                    async with self._client:
                        await self._client.play_favorite(fav["index"])
                    await self.coordinator.async_request_refresh()
                    return
                except httpx.HTTPError as err:
                    _LOGGER.error("Failed to select source: %s", err)
                    return

        _LOGGER.warning("Source %s not found in favorites", source)
