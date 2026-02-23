"""Constants for the MusicPal integration."""

DOMAIN = "musicpal"

# Configuration constants
CONF_HOSTNAME = "hostname"
DEFAULT_NAME = "MusicPal"
DEFAULT_PORT = 80
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

# Scan interval
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Endpoints
ENDPOINT_ADMIN_CGI = "/admin/cgi-bin/admin.cgi"
ENDPOINT_STATE_CGI = "/admin/cgi-bin/state.cgi"
ENDPOINT_DEBUG_CGI = "/admin/cgi-bin/debug.cgi"
ENDPOINT_IPC_SEND = "/admin/cgi-bin/ipc_send"
