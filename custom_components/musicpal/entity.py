"""Base entity for the MusicPal integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import MusicPalDataUpdateCoordinator

# Info-page labels the device may use for its firmware version, lower-cased.
_VERSION_HINTS = ("firmware", "version", "software")


def _pick(info: dict[str, str], hints: tuple[str, ...]) -> str | None:
    """Return the first info value whose label matches one of *hints*."""
    for label, value in info.items():
        lowered = label.lower()
        if any(hint in lowered for hint in hints) and value:
            return value
    return None


class MusicPalEntity(CoordinatorEntity[MusicPalDataUpdateCoordinator]):
    """Common base class tying every entity to the MusicPal device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MusicPalDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        # Unique IDs stay host-based for backwards compatibility with
        # installations created before the device registry entry existed.
        self._attr_unique_id = f"{coordinator.host}_{key}"

        entry = coordinator.config_entry
        info = coordinator.data.info if coordinator.data else {}

        device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title or MODEL,
            configuration_url=f"http://{coordinator.host}/",
            sw_version=_pick(info, _VERSION_HINTS),
        )

        mac = _pick(info, ("mac",))
        if mac:
            device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, format_mac(mac))
            }

        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return True when the last poll succeeded."""
        return super().available and self.coordinator.data is not None
