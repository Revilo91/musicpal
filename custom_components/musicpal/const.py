"""Constants for the MusicPal integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "musicpal"

# === Device / branding =====================================================

DEFAULT_NAME: Final = "MusicPal"
DEFAULT_USERNAME: Final = "admin"
DEFAULT_PASSWORD: Final = "admin"

MANUFACTURER: Final = "Freecom"
MODEL: Final = "MusicPal"

# === Polling ===============================================================

DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 300

# Rarely changing data (favorites, uptime, device info) is only refreshed
# every N fast poll cycles so the 2007-era hardware is not hammered.
SLOW_UPDATE_CYCLES: Final = 20

# Per-request HTTP timeout.  Kept well below the default scan interval so a
# single unresponsive endpoint cannot stall the whole update cycle.
REQUEST_TIMEOUT: Final = 8.0

# === Device capabilities ===================================================

# The device reports/accepts volume as an integer step count.
VOLUME_MAX: Final = 20

# === Attributes ============================================================

ATTR_UPTIME: Final = "uptime"
ATTR_FAVORITES: Final = "favorites"

# === Services ==============================================================

SERVICE_SHOW_MESSAGE: Final = "show_message"
SERVICE_SHOW_CLOCK: Final = "show_clock"
SERVICE_REBOOT: Final = "reboot"

ATTR_MESSAGE: Final = "message"

# === UPnP event subscription ===============================================

UPNP_NOTIFY_PATH: Final = "/api/musicpal/upnp_notify"
# Renew ~5 minutes before the 30 minute subscription expires.
UPNP_RENEWAL_INTERVAL: Final = 1500  # seconds
