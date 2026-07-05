"""Sensor platform for BlaulichtSMS Dashboard."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def is_alarm_active(data) -> bool:
    """Check if the latest alarm is active (younger than 1 hour)."""
    if not data:
        return False
        
    alarm_date_str = data[0].get("alarmDate")
    if not alarm_date_str:
        return True
        
    try:
        alarm_date = datetime.fromisoformat(alarm_date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now - alarm_date > timedelta(hours=1):
            return False
        return True
    except Exception:
        return True


def generate_tts_text(data) -> str:
    """Generate a TTS friendly text."""
    if not is_alarm_active(data):
        return "Kein aktiver Alarm"
    
    alarm_text = data[0].get("alarmText", "")
    is_probe = "probe" in alarm_text.lower() or data[0].get("isTestAlarm", False)
    
    if is_probe:
        return f"Achtung, dies ist ein Probealarm! {alarm_text}"
    else:
        return f"Achtung, Einsatzalarm! {alarm_text}"


@dataclass(frozen=True, kw_only=True)
class BlaulichtSMSSensorEntityDescription(SensorEntityDescription):
    """Describes BlaulichtSMS sensor entity."""
    value_fn: Callable[[Any], Any]


SENSOR_TYPES: tuple[BlaulichtSMSSensorEntityDescription, ...] = (
    BlaulichtSMSSensorEntityDescription(
        key="einsatzstatus",
        name="Einsatzstatus",
        icon="mdi:fire-truck",
        value_fn=lambda data: "Aktiv" if is_alarm_active(data) else "Inaktiv",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="aktive_alarme_anzahl",
        name="Aktive Alarme Anzahl",
        icon="mdi:counter",
        value_fn=lambda data: len(data) if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="alarm_text",
        name="Alarm Text",
        icon="mdi:text-box",
        value_fn=lambda data: data[0].get("alarmText", "Unbekannt") if data else "Kein Alarm",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="alarm_date",
        name="Alarm Datum",
        icon="mdi:calendar-clock",
        value_fn=lambda data: data[0].get("alarmDate", "Unbekannt") if data else "Kein Alarm",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="alarm_autor",
        name="Alarm Autor",
        icon="mdi:account-hard-hat",
        value_fn=lambda data: data[0].get("authorName", "Unbekannt") if data else "Kein Alarm",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="alarm_gruppen",
        name="Alarm Gruppen",
        icon="mdi:account-group",
        value_fn=lambda data: ", ".join(g.get("groupName", "") for g in data[0].get("alarmGroups", []) if g.get("groupName")) if data else "Keine",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="anzahl_alarmiert",
        name="Anzahl Alarmiert",
        icon="mdi:account-multiple",
        value_fn=lambda data: data[0].get("usersAlertedCount", 0) if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="teilnehmer_zugesagt",
        name="Teilnehmer Zugesagt",
        icon="mdi:account-check",
        value_fn=lambda data: sum(1 for r in data[0].get("recipients", []) if r.get("participation") == "yes") if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="teilnehmer_abgesagt",
        name="Teilnehmer Abgesagt",
        icon="mdi:account-cancel",
        value_fn=lambda data: sum(1 for r in data[0].get("recipients", []) if r.get("participation") == "no") if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="teilnehmer_ausstehend",
        name="Teilnehmer Ausstehend",
        icon="mdi:account-clock",
        value_fn=lambda data: sum(1 for r in data[0].get("recipients", []) if r.get("participation") == "pending") if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="einsatzort",
        name="Einsatzort",
        icon="mdi:map-marker",
        value_fn=lambda data: (
            data[0].get("geolocation", {}).get("address") or 
            data[0].get("coordinates") or 
            "Unbekannt"
        ) if data else "Kein Alarm",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="tts_text",
        name="TTS Text",
        icon="mdi:speaker-message",
        value_fn=lambda data: generate_tts_text(data),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlaulichtSMS sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BlaulichtSMSSensor(coordinator, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class BlaulichtSMSSensor(CoordinatorEntity, SensorEntity):
    """Representation of a BlaulichtSMS Sensor."""

    entity_description: BlaulichtSMSSensorEntityDescription

    def __init__(self, coordinator, description: BlaulichtSMSSensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"blaulichtsms_{coordinator.customer_id}_{description.key}"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.customer_id)},
            "name": f"BlaulichtSMS ({self.coordinator.username})",
            "manufacturer": "BlaulichtSMS",
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        try:
            return self.entity_description.value_fn(self.coordinator.data)
        except Exception:
            return None
