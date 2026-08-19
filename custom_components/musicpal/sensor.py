"""Support for MusicPal sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MusicPalConfigEntry
from .const import ATTR_FAVORITES
from .coordinator import MusicPalDataUpdateCoordinator
from .entity import MusicPalEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MusicPalConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MusicPal sensor platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        [
            MusicPalUptimeSensor(coordinator),
            MusicPalDisplaySensor(coordinator),
            MusicPalFavoritesCountSensor(coordinator),
        ]
    )


class MusicPalUptimeSensor(MusicPalEntity, SensorEntity):
    """Reports when the MusicPal last booted."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_boot"

    def __init__(self, coordinator: MusicPalDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        # The unique ID predates the switch from "seconds up" to a boot
        # timestamp and is kept so existing entities are not orphaned.
        super().__init__(coordinator, "uptime")

    @property
    def native_value(self) -> datetime | None:
        """Return the boot time of the device."""
        data = self.coordinator.data
        return data.boot_time if data else None


class MusicPalDisplaySensor(MusicPalEntity, SensorEntity):
    """Reports the text currently shown on the device display."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:monitor"
    _attr_translation_key = "display"

    def __init__(self, coordinator: MusicPalDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "display")

    @property
    def native_value(self) -> str | None:
        """Return the display content."""
        data = self.coordinator.data
        if data is None:
            return None
        display = data.state.get("display")
        if not display:
            return None
        # Sensor states are capped at 255 characters by Home Assistant.
        return display[:255]


class MusicPalFavoritesCountSensor(MusicPalEntity, SensorEntity):
    """Reports how many favorites are configured on the device."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:heart-multiple"
    _attr_translation_key = "favorites_count"

    def __init__(self, coordinator: MusicPalDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "favorites_count")

    @property
    def native_value(self) -> int | None:
        """Return the number of configured favorites."""
        data = self.coordinator.data
        return len(data.favorites) if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the favorite names."""
        data = self.coordinator.data
        if data is None:
            return {}
        return {ATTR_FAVORITES: [str(fav["name"]) for fav in data.favorites]}
