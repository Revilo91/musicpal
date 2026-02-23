"""Config flow for MusicPal integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import httpx

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, DEFAULT_USERNAME, DEFAULT_PASSWORD, ENDPOINT_STATE_CGI

_LOGGER = logging.getLogger(__name__)


class MusicPalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MusicPal."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the connection
            try:
                await self._test_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except httpx.ConnectError:
                errors["base"] = "cannot_connect"
            except httpx.TimeoutException:
                errors["base"] = "timeout_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create the entry
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"MusicPal ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def _test_connection(
        self, host: str, username: str, password: str
    ) -> None:
        """Test if we can connect to the MusicPal device."""
        client = get_async_client(self.hass)
        response = await client.get(
            f"http://{host}{ENDPOINT_STATE_CGI}",
            params={"fav": 0},
            auth=(username, password),
            timeout=10.0,
        )
        response.raise_for_status()
