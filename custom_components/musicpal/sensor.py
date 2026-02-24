"""Support for MusicPal sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MusicPal sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    sensors = [
        MusicPalUpTimeSensor(coordinator, config_entry),
        MusicPalDisplaySensor(coordinator, config_entry),
        MusicPalFavoritesCountSensor(coordinator, config_entry),
    ]

    async_add_entities(sensors)


class MusicPalUpTimeSensor(CoordinatorEntity, SensorEntity):
    """Representation of the MusicPal uptime sensor."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "MusicPal Uptime"
        self._attr_unique_id = f"{config_entry.data[CONF_HOST]}_uptime"
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        uptime = self.coordinator.data.get("uptime")
        if uptime:
            return float(uptime.total_seconds())
        return None


class MusicPalDisplaySensor(CoordinatorEntity, SensorEntity):
    """Representation of the MusicPal display content sensor."""

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "MusicPal Display"
        self._attr_unique_id = f"{config_entry.data[CONF_HOST]}_display"
        self._attr_icon = "mdi:monitor"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        state_data = self.coordinator.data.get("state", {})
        return state_data.get("display", None)


class MusicPalFavoritesCountSensor(CoordinatorEntity, SensorEntity):
    """Representation of the MusicPal favorites count sensor."""

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "MusicPal Favorites Count"
        self._attr_unique_id = f"{config_entry.data[CONF_HOST]}_favorites_count"
        self._attr_icon = "mdi:heart-multiple"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        favorites = self.coordinator.data.get("favorites", [])
        return len(favorites)

    @property
    def extra_state_attributes(self) -> dict[str, list[str]] | None:
        """Return entity specific state attributes."""
        if not self.coordinator.data:
            return None

        favorites = self.coordinator.data.get("favorites", [])
        return {"favorites": [fav["name"] for fav in favorites]}
