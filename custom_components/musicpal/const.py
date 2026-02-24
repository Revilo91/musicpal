"""Constants for the MusicPal integration."""

DOMAIN = "musicpal"

# Configuration
CONF_HOST = "host"

# Default values
DEFAULT_NAME = "MusicPal"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

# Update intervals
SCAN_INTERVAL = 30  # seconds

# Attributes
ATTR_UPTIME = "uptime"
ATTR_FAVORITES = "favorites"

# UPnP event subscription
UPNP_NOTIFY_PATH = "/api/musicpal/upnp_notify"
UPNP_RENEWAL_INTERVAL = 1500  # seconds — renew 5 min before 30-min expiry
