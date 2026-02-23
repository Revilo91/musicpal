"""The Freecom MusicPal integration."""
import logging
import voluptuous as vol

from homeassistant.const import Platform, CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
import homeassistant.helpers.device_registry as dr

from .const import DOMAIN, ENDPOINT_IPC_SEND, ENDPOINT_ADMIN_CGI

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.BUTTON]

# Service schemas
SERVICE_SHOW_MESSAGE = "show_message"
SERVICE_SHOW_LIST = "show_list"
SERVICE_PLAY_URL = "play_url"
SERVICE_SELECT_FAVORITE = "select_favorite"

SHOW_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
    }
)

SHOW_LIST_SCHEMA = vol.Schema(
    {
        vol.Required("items"): cv.string,
    }
)

PLAY_URL_SCHEMA = vol.Schema(
    {
        vol.Required("url"): cv.string,
    }
)

SELECT_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Required("index"): cv.positive_int,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the MusicPal component from yaml."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MusicPal from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_USERNAME: entry.data[CONF_USERNAME],
        CONF_PASSWORD: entry.data[CONF_PASSWORD],
    }

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_show_message(call: ServiceCall) -> None:
        """Handle the show_message service call."""
        message = call.data["message"]
        device_id = call.data.get("device_id")

        if device_id:
            device_entry = await _get_device_entry(hass, device_id)
            if device_entry:
                config_entry_id = next(iter(device_entry.config_entries))
                device_data = hass.data[DOMAIN][config_entry_id]
                await _send_ipc_command(
                    hass,
                    device_data[CONF_HOST],
                    device_data[CONF_USERNAME],
                    device_data[CONF_PASSWORD],
                    "show_msg_box",
                    [message],
                )

    async def handle_show_list(call: ServiceCall) -> None:
        """Handle the show_list service call."""
        items = call.data["items"]
        device_id = call.data.get("device_id")

        if device_id:
            device_entry = await _get_device_entry(hass, device_id)
            if device_entry:
                config_entry_id = next(iter(device_entry.config_entries))
                device_data = hass.data[DOMAIN][config_entry_id]
                # Split items by comma and pass as arguments
                item_list = [item.strip() for item in items.split(",")]
                await _send_ipc_command(
                    hass,
                    device_data[CONF_HOST],
                    device_data[CONF_USERNAME],
                    device_data[CONF_PASSWORD],
                    "show_list",
                    item_list,
                )

    async def handle_play_url(call: ServiceCall) -> None:
        """Handle the play_url service call."""
        url = call.data["url"]
        device_id = call.data.get("device_id")

        if device_id:
            device_entry = await _get_device_entry(hass, device_id)
            if device_entry:
                config_entry_id = next(iter(device_entry.config_entries))
                device_data = hass.data[DOMAIN][config_entry_id]
                await _send_ipc_command(
                    hass,
                    device_data[CONF_HOST],
                    device_data[CONF_USERNAME],
                    device_data[CONF_PASSWORD],
                    "play",
                    [url],
                )

    async def handle_select_favorite(call: ServiceCall) -> None:
        """Handle the select_favorite service call."""
        index = call.data["index"]
        device_id = call.data.get("device_id")

        if device_id:
            device_entry = await _get_device_entry(hass, device_id)
            if device_entry:
                config_entry_id = next(iter(device_entry.config_entries))
                device_data = hass.data[DOMAIN][config_entry_id]
                await _send_admin_command(
                    hass,
                    device_data[CONF_HOST],
                    device_data[CONF_USERNAME],
                    device_data[CONF_PASSWORD],
                    "favorites",
                    {"n": "../favorites.html", "a": "p", "i": str(index)},
                )

    hass.services.async_register(
        DOMAIN, SERVICE_SHOW_MESSAGE, handle_show_message, schema=SHOW_MESSAGE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SHOW_LIST, handle_show_list, schema=SHOW_LIST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PLAY_URL, handle_play_url, schema=PLAY_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_FAVORITE, handle_select_favorite, schema=SELECT_FAVORITE_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        # Unregister services if this was the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SHOW_MESSAGE)
            hass.services.async_remove(DOMAIN, SERVICE_SHOW_LIST)
            hass.services.async_remove(DOMAIN, SERVICE_PLAY_URL)
            hass.services.async_remove(DOMAIN, SERVICE_SELECT_FAVORITE)

    return unload_ok


async def _get_device_entry(hass: HomeAssistant, device_id: str):
    """Get device entry from device ID."""
    device_registry = dr.async_get(hass)
    return device_registry.async_get(device_id)


async def _send_ipc_command(
    hass: HomeAssistant,
    host: str,
    username: str,
    password: str,
    command: str,
    args: list[str] | None = None,
) -> None:
    """Send an IPC command to the device."""
    try:
        client = get_async_client(hass)
        cmd_parts = [command] + (args or [])
        url = f"http://{host}{ENDPOINT_IPC_SEND}?" + "&".join(cmd_parts)

        await client.get(
            url,
            auth=(username, password),
            timeout=10.0,
        )
    except Exception as err:
        _LOGGER.error("Error sending IPC command %s: %s", command, err)


async def _send_admin_command(
    hass: HomeAssistant,
    host: str,
    username: str,
    password: str,
    command: str,
    params: dict | None = None,
) -> None:
    """Send an admin command to the device."""
    try:
        client = get_async_client(hass)
        if params is None:
            params = {}
        params["f"] = command

        await client.get(
            f"http://{host}{ENDPOINT_ADMIN_CGI}",
            params=params,
            auth=(username, password),
            timeout=10.0,
        )
    except Exception as err:
        _LOGGER.error("Error sending admin command %s: %s", command, err)
