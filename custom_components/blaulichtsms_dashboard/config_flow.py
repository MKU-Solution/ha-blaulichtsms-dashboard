"""Config flow for BlaulichtSMS Dashboard integration."""
import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DOMAIN,
    BASE_URL,
    CONF_CUSTOMER_ID,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_SELECTOR = vol.All(
    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
)
PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD)
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot reach the BlaulichtSMS API."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate the dashboard credentials are wrong."""


async def validate_credentials(
    hass: HomeAssistant, customer_id: str, username: str, password: str
) -> None:
    """Try a real dashboard login; raise CannotConnect or InvalidAuth."""
    session = async_get_clientsession(hass)
    payload = {
        "customerId": customer_id,
        "username": username,
        "password": password,
    }
    try:
        async with session.post(
            f"{BASE_URL}/login", json=payload, timeout=REQUEST_TIMEOUT
        ) as resp:
            if resp.status in (401, 403):
                raise InvalidAuth
            resp.raise_for_status()
            result = await resp.json()
    except asyncio.TimeoutError as err:
        raise CannotConnect from err
    except aiohttp.ClientError as err:
        raise CannotConnect from err

    if not result.get("sessionId"):
        raise InvalidAuth


class BlaulichtSMSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BlaulichtSMS Dashboard."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_CUSTOMER_ID]}_{user_input[CONF_USERNAME]}"
            )
            self._abort_if_unique_id_configured()

            try:
                await validate_credentials(
                    self.hass,
                    user_input[CONF_CUSTOMER_ID],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unerwarteter Fehler beim Prüfen der Zugangsdaten")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"BlaulichtSMS ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_CUSTOMER_ID): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): SCAN_INTERVAL_SELECTOR,
            }
        )

        # Eingaben nach einem Fehler erhalten - das Passwort bewusst nicht.
        suggested = {
            k: v for k, v in (user_input or {}).items() if k != CONF_PASSWORD
        }

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(data_schema, suggested),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Handle re-authentication after the dashboard rejected our login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ):
        """Ask for a new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_credentials(
                    self.hass,
                    entry.data[CONF_CUSTOMER_ID],
                    entry.data[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unerwarteter Fehler beim Prüfen der Zugangsdaten")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}),
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return BlaulichtSMSOptionsFlowHandler()


class BlaulichtSMSOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): SCAN_INTERVAL_SELECTOR,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
