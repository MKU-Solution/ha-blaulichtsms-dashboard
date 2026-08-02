"""The BlaulichtSMS Dashboard integration."""
import asyncio
import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.BUTTON]


class BlaulichtSMSSessionExpired(HomeAssistantError):
    """Raised when the dashboard session ID is no longer accepted.

    Im Gegensatz zu ``ConfigEntryAuthFailed`` bedeutet das nicht, dass die
    Zugangsdaten falsch sind - es reicht ein neuer Login.
    """


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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry.

    Version 1 leitete Device- und Entity-IDs aus der ``customer_id`` ab. Die ist
    nicht eindeutig (mehrere Dashboards je Kunde), daher hängen ab Version 2
    alle IDs an der ``entry_id``.
    """
    if entry.version > 2:
        # Downgrade von einer neueren Version wird nicht unterstützt.
        return False

    if entry.version == 1:
        old_prefix = f"blaulichtsms_{entry.data[CONF_CUSTOMER_ID]}_"
        new_prefix = f"{entry.entry_id}_"

        registry = er.async_get(hass)
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if not reg_entry.unique_id.startswith(old_prefix):
                continue
            new_unique_id = new_prefix + reg_entry.unique_id[len(old_prefix) :]
            _LOGGER.debug(
                "Migriere unique_id %s -> %s", reg_entry.unique_id, new_unique_id
            )
            registry.async_update_entity(reg_entry.entity_id, new_unique_id=new_unique_id)

        device_reg = dr.async_get(hass)
        old_identifier = (DOMAIN, entry.data[CONF_CUSTOMER_ID])
        for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
            if old_identifier in device.identifiers:
                device_reg.async_update_device(
                    device.id, new_identifiers={(DOMAIN, entry.entry_id)}
                )

        hass.config_entries.async_update_entry(entry, version=2)

    return True


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
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.session = async_get_clientsession(hass)
        self.blaulicht_session_id = None

    async def _async_update_data(self):
        """Fetch data from BlaulichtSMS.

        ``ConfigEntryAuthFailed`` wird bewusst nicht abgefangen: nur so startet
        Home Assistant den Reauth-Flow, statt endlos weiterzupollen.
        """
        try:
            if not self.blaulicht_session_id:
                await self._login()

            try:
                return await self._fetch_alarms()
            except BlaulichtSMSSessionExpired:
                _LOGGER.debug("Session abgelaufen, melde erneut an")

            await self._login()
            try:
                return await self._fetch_alarms()
            except BlaulichtSMSSessionExpired as err:
                raise ConfigEntryAuthFailed(
                    "Session wurde direkt nach dem Login abgelehnt"
                ) from err
        except (ConfigEntryAuthFailed, UpdateFailed):
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
            async with self.session.post(
                url, json=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status in (401, 403):
                    raise ConfigEntryAuthFailed("Ungültige Zugangsdaten")
                resp.raise_for_status()
                data = await resp.json()
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout beim Login") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Netzwerkfehler beim Login: {err}") from err

        self.blaulicht_session_id = data.get("sessionId")
        if not self.blaulicht_session_id:
            raise UpdateFailed("Keine Session ID nach dem Login erhalten")

    async def _fetch_alarms(self):
        """Fetch active alarms using session ID."""
        url = f"{BASE_URL}/{self.blaulicht_session_id}"
        try:
            async with self.session.get(url, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status in (401, 403):
                    # Session abgelaufen, ID zurücksetzen um neu einzuloggen
                    self.blaulicht_session_id = None
                    raise BlaulichtSMSSessionExpired("Session abgelaufen")
                resp.raise_for_status()
                data = await resp.json()
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout beim Abrufen der Alarme") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Netzwerkfehler beim Abrufen der Alarme: {err}") from err

        alarms = data.get("alarms", [])
        # Kein vollständiges Payload loggen - es enthält Namen und
        # Teilnahmestatus aller alarmierten Mitglieder.
        _LOGGER.debug(
            "%s Alarm(e) von BlaulichtSMS erhalten (Zeitstempel: %s)",
            len(alarms),
            [a.get("alarmDate") for a in alarms],
        )
        # Nicht auf die Sortierung der API vertrauen - alle Sensoren lesen data[0].
        return sorted(alarms, key=lambda a: a.get("alarmDate") or "", reverse=True)
