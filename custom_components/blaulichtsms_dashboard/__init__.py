"""The BlaulichtSMS Dashboard integration."""
import asyncio
import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_CUSTOMER_ID,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    BASE_URL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BlaulichtSMS Dashboard from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = BlaulichtSMSCoordinator(hass, entry)

    # Erster Datenabruf
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload wenn Optionen (z.B. Polling Intervall) geändert werden
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


class BlaulichtSMSCoordinator(DataUpdateCoordinator):
    """Class to manage fetching BlaulichtSMS data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.customer_id = entry.data[CONF_CUSTOMER_ID]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]

        # Hole das Polling Intervall aus den Optionen, falls vorhanden, sonst aus den Setup-Daten, sonst Default
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.session = async_get_clientsession(hass)
        self.blaulicht_session_id = None

    async def _async_update_data(self):
        """Fetch data from BlaulichtSMS."""
        try:
            if not self.blaulicht_session_id:
                await self._login()

            return await self._fetch_alarms()
        except ConfigEntryAuthFailed as err:
            # Session möglicherweise abgelaufen, versuche erneuten Login
            _LOGGER.warning("Authentifizierung fehlgeschlagen, versuche erneuten Login: %s", err)
            try:
                await self._login()
                return await self._fetch_alarms()
            except Exception as login_err:
                raise UpdateFailed(f"Erneute Authentifizierung fehlgeschlagen: {login_err}") from login_err
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Fehler bei der Kommunikation mit der API: {err}") from err

    async def _login(self):
        """Perform login to get session ID."""
        url = f"{BASE_URL}/login"
        payload = {
            "customerId": self.customer_id,
            "username": self.username,
            "password": self.password,
        }
        try:
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status in (401, 403):
                    raise ConfigEntryAuthFailed("Ungültige Zugangsdaten")
                resp.raise_for_status()
                data = await resp.json()
                self.blaulicht_session_id = data.get("sessionId")
                if not self.blaulicht_session_id:
                    raise UpdateFailed("Keine Session ID nach dem Login erhalten")
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout beim Login") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Netzwerkfehler beim Login: {err}") from err

    async def _fetch_alarms(self):
        """Fetch active alarms using session ID."""
        url = f"{BASE_URL}/{self.blaulicht_session_id}"
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status in (401, 403):
                    # Session abgelaufen, ID zurücksetzen um beim nächsten Aufruf neu einzuloggen
                    self.blaulicht_session_id = None
                    raise ConfigEntryAuthFailed("Session abgelaufen")
                resp.raise_for_status()
                data = await resp.json()
                _LOGGER.debug("Empfangenes JSON von BlaulichtSMS: %s", data)
                return data.get("alarms", [])
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout beim Abrufen der Alarme") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Netzwerkfehler beim Abrufen der Alarme: {err}") from err
