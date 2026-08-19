"""Support for the MusicPal media player."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from . import MusicPalConfigEntry
from .const import (
    ATTR_FAVORITES,
    ATTR_MESSAGE,
    ATTR_UPTIME,
    SERVICE_REBOOT,
    SERVICE_SHOW_CLOCK,
    SERVICE_SHOW_MESSAGE,
    VOLUME_MAX,
)
from .coordinator import MusicPalDataUpdateCoordinator
from .entity import MusicPalEntity
from .musicpal_api import MusicPalError

_LOGGER = logging.getLogger(__name__)

# UPnP AVTransport states mapped onto Home Assistant media player states.
_TRANSPORT_STATES: dict[str, MediaPlayerState] = {
    "PLAYING": MediaPlayerState.PLAYING,
    "PAUSED_PLAYBACK": MediaPlayerState.PAUSED,
    "PAUSED_RECORDING": MediaPlayerState.PAUSED,
    "TRANSITIONING": MediaPlayerState.BUFFERING,
    "STOPPED": MediaPlayerState.IDLE,
    "NO_MEDIA_PRESENT": MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MusicPalConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MusicPal media player platform."""
    async_add_entities([MusicPalMediaPlayer(config_entry.runtime_data)])

    # Entity services keep the target handling (entity_id / device_id / area)
    # in Home Assistant's hands instead of reimplementing it per service.
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SHOW_MESSAGE,
        {vol.Required(ATTR_MESSAGE): cv.string},
        "async_show_message",
    )
    platform.async_register_entity_service(
        SERVICE_SHOW_CLOCK, None, "async_show_clock"
    )
    platform.async_register_entity_service(SERVICE_REBOOT, None, "async_reboot")


class MusicPalMediaPlayer(MusicPalEntity, MediaPlayerEntity):
    """Representation of a MusicPal media player."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: MusicPalDataUpdateCoordinator) -> None:
        """Initialize the MusicPal media player."""
        super().__init__(coordinator, "media_player")
        self._selected_source: str | None = None

    # --- state ------------------------------------------------------------

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device.

        Precedence: real-time UPnP AVTransport state, then the explicit
        playing/paused flags reported by ``state.cgi``, and only then the
        display text as a last resort.
        """
        transport_state = self.coordinator.upnp.transport_state
        if transport_state and transport_state in _TRANSPORT_STATES:
            return _TRANSPORT_STATES[transport_state]

        data = self.coordinator.data
        if data is None:
            return MediaPlayerState.OFF

        # state.cgi reports these as "0"/"1" strings, so they have to be
        # compared explicitly — a bare truthiness check treats "0" as True
        # and leaves the player stuck on "playing" after pausing it on the
        # device itself.
        if data.state.get("playing") == "1":
            return MediaPlayerState.PLAYING
        if data.state.get("paused") == "1":
            return MediaPlayerState.PAUSED

        display = data.state.get("display", "").lower()
        # The MusicPal shows the clock screen while in standby, which is what
        # "power_down" puts it into — report that as off so the power buttons
        # reflect reality.
        if "clock" in display:
            return MediaPlayerState.OFF
        if "playing" in display:
            return MediaPlayerState.PLAYING
        if "pause" in display:
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        data = self.coordinator.data
        if data is None or data.volume is None:
            return None
        return data.volume / VOLUME_MAX

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources (the device favorites)."""
        data = self.coordinator.data
        if data is None:
            return None
        return [str(fav["name"]) for fav in data.favorites]

    @property
    def source(self) -> str | None:
        """Return the currently selected favorite, when it can be told."""
        data = self.coordinator.data
        if data is None:
            return self._selected_source

        now_playing = data.now_playing.lower()
        for fav in data.favorites:
            name = str(fav["name"])
            if name and name.lower() in now_playing:
                return name
        return self._selected_source

    @property
    def media_title(self) -> str | None:
        """Title of the currently playing media."""
        # Track metadata pushed via UPnP is more precise than the screen text.
        if title := self.coordinator.upnp.track_title:
            return title
        data = self.coordinator.data
        if data is not None and data.now_playing:
            return data.now_playing
        return None

    @property
    def media_content_id(self) -> str | None:
        """Content ID (URL) of the currently playing media."""
        return self.coordinator.upnp.avt_uri

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        data = self.coordinator.data
        if data is None:
            return {}

        attrs: dict[str, Any] = {}
        if data.uptime is not None:
            attrs[ATTR_UPTIME] = str(data.uptime)
        if data.favorites:
            attrs[ATTR_FAVORITES] = len(data.favorites)
        return attrs

    # --- helpers ----------------------------------------------------------

    async def _async_command(self, action: str, coro: Any) -> None:
        """Await a device command and surface failures to the caller."""
        try:
            await coro
        except MusicPalError as err:
            raise HomeAssistantError(f"Failed to {action}: {err}") from err
        await self.coordinator.async_request_refresh()

    # --- commands ---------------------------------------------------------

    async def async_turn_on(self) -> None:
        """Wake the device from standby."""
        await self._async_command(
            "turn on MusicPal", self.coordinator.client.power_on()
        )

    async def async_turn_off(self) -> None:
        """Send the device to standby."""
        await self._async_command(
            "turn off MusicPal", self.coordinator.client.power_off()
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level, range 0..1."""
        await self._async_command(
            "set volume",
            self.coordinator.client.set_volume(round(volume * VOLUME_MAX)),
        )

    async def async_volume_up(self) -> None:
        """Increase the volume by one step."""
        await self._async_command(
            "increase volume", self.coordinator.client.volume_up()
        )

    async def async_volume_down(self) -> None:
        """Decrease the volume by one step."""
        await self._async_command(
            "decrease volume", self.coordinator.client.volume_down()
        )

    async def async_media_play(self) -> None:
        """Resume playback.

        The device only offers a play/pause toggle, so the command is only
        sent when it would actually change something.
        """
        if self.state == MediaPlayerState.PLAYING:
            return
        await self._async_command(
            "start playback", self.coordinator.client.play_pause()
        )

    async def async_media_pause(self) -> None:
        """Pause playback (see :meth:`async_media_play` about the toggle)."""
        if self.state in (MediaPlayerState.PAUSED, MediaPlayerState.OFF):
            return
        await self._async_command(
            "pause playback", self.coordinator.client.play_pause()
        )

    async def async_media_stop(self) -> None:
        """Stop playback.

        The firmware has no dedicated stop command, so this pauses instead.
        """
        await self.async_media_pause()

    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self._async_command(
            "skip to the next track", self.coordinator.client.next_track()
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        media_id = async_process_play_media_url(self.hass, media_id)

        await self._async_command(
            "play media", self.coordinator.client.play_url(media_id)
        )

        # Keep media_content_id meaningful even without UPnP eventing.
        self.coordinator.upnp.avt_uri = media_id
        self._selected_source = None

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse Home Assistant media sources."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith(
                "audio/"
            ),
        )

    async def async_select_source(self, source: str) -> None:
        """Select an input source (a device favorite)."""
        data = self.coordinator.data
        favorites = data.favorites if data else []

        for fav in favorites:
            if str(fav["name"]) == source:
                self._selected_source = source
                await self._async_command(
                    f"select favorite '{source}'",
                    self.coordinator.client.play_favorite(int(fav["index"])),
                )
                return

        raise ServiceValidationError(
            f"'{source}' is not a MusicPal favorite. Available: "
            + (", ".join(str(fav["name"]) for fav in favorites) or "none")
        )

    # --- entity services --------------------------------------------------

    async def async_show_message(self, message: str) -> None:
        """Show a message box on the device display."""
        await self._async_command(
            "show the message", self.coordinator.client.show_message(message)
        )

    async def async_show_clock(self) -> None:
        """Show the clock screen on the device display."""
        await self._async_command(
            "show the clock", self.coordinator.client.show_clock()
        )

    async def async_reboot(self) -> None:
        """Reboot the device."""
        try:
            await self.coordinator.client.reboot()
        except MusicPalError as err:
            raise HomeAssistantError(f"Failed to reboot: {err}") from err
        # Uptime and device info are stale after a reboot.
        self.coordinator.async_invalidate_slow_data()
