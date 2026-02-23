"""Config flow for MusicPal integration."""

from typing import Any
import logging

import httpx
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_NAME, DEFAULT_PASSWORD, DEFAULT_USERNAME, DOMAIN
from .musicpal_api import MusicPalClient

_LOGGER = logging.getLogger(__name__)


class MusicPalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MusicPal."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test connection
                async with MusicPalClient(
                    hostname=user_input[CONF_HOST],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                ) as client:
                    await client.get_state()

                # Create unique ID based on host
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get("name", DEFAULT_NAME),
                    data=user_input,
                )

            except httpx.ConnectError:
                errors["base"] = "cannot_connect"
            except httpx.HTTPStatusError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(
                    CONF_USERNAME, default=DEFAULT_USERNAME
                ): cv.string,
                vol.Optional(
                    CONF_PASSWORD, default=DEFAULT_PASSWORD
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
