"""Sensor platform for BlaulichtSMS Dashboard."""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import BlaulichtSMSEntity
from .helpers import (
    clean_for_tts,
    generate_tts_text,
    is_alarm_active,
    truncate_state,
)

_LOGGER = logging.getLogger(__name__)

# Re-Export für Rückwärtskompatibilität: bis v1.5.0 lagen diese Funktionen hier.
__all__ = [
    "clean_for_tts",
    "generate_tts_text",
    "is_alarm_active",
    "truncate_state",
]


@dataclass(frozen=True, kw_only=True)
class BlaulichtSMSSensorEntityDescription(SensorEntityDescription):
    """Describes BlaulichtSMS sensor entity."""
    value_fn: Callable[[Any], Any]


SENSOR_TYPES: tuple[BlaulichtSMSSensorEntityDescription, ...] = (
    BlaulichtSMSSensorEntityDescription(
        key="einsatzstatus",
        translation_key="einsatzstatus",
        icon="mdi:fire-truck",
        value_fn=lambda data: "Aktiv" if is_alarm_active(data) else "Inaktiv",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="aktive_alarme_anzahl",
        translation_key="aktive_alarme_anzahl",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(data) if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="alarm_text",
        translation_key="alarm_text",
        icon="mdi:text-box",
        value_fn=lambda data: data[0].get("alarmText", "Unbekannt") if data else "Kein Alarm",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="alarm_date",
        translation_key="alarm_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: dt_util.parse_datetime(data[0]["alarmDate"])
        if data and data[0].get("alarmDate")
        else None,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="alarm_autor",
        translation_key="alarm_autor",
        icon="mdi:account-hard-hat",
        value_fn=lambda data: data[0].get("authorName", "Unbekannt") if data else "Kein Alarm",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="alarm_gruppen",
        translation_key="alarm_gruppen",
        icon="mdi:account-group",
        value_fn=lambda data: ", ".join(g.get("groupName", "") for g in data[0].get("alarmGroups", []) if g.get("groupName")) if data else "Keine",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="anzahl_alarmiert",
        translation_key="anzahl_alarmiert",
        icon="mdi:account-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data[0].get("usersAlertedCount", 0) if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="teilnehmer_zugesagt",
        translation_key="teilnehmer_zugesagt",
        icon="mdi:account-check",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(1 for r in data[0].get("recipients", []) if r.get("participation") == "yes") if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="teilnehmer_abgesagt",
        translation_key="teilnehmer_abgesagt",
        icon="mdi:account-cancel",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(1 for r in data[0].get("recipients", []) if r.get("participation") == "no") if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="teilnehmer_ausstehend",
        translation_key="teilnehmer_ausstehend",
        icon="mdi:account-clock",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(1 for r in data[0].get("recipients", []) if r.get("participation") == "pending") if data else 0,
    ),
    BlaulichtSMSSensorEntityDescription(
        key="einsatzort",
        translation_key="einsatzort",
        icon="mdi:map-marker",
        value_fn=lambda data: (
            data[0].get("geolocation", {}).get("address") or
            data[0].get("coordinates") or
            "Unbekannt"
        ) if data else "Kein Alarm",
    ),
    BlaulichtSMSSensorEntityDescription(
        key="tts_text",
        translation_key="tts_text",
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


class BlaulichtSMSSensor(BlaulichtSMSEntity, SensorEntity):
    """Representation of a BlaulichtSMS Sensor."""

    entity_description: BlaulichtSMSSensorEntityDescription

    def __init__(self, coordinator, description: BlaulichtSMSSensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    def _raw_value(self) -> Any:
        """Return the untruncated value, or None if it cannot be computed."""
        try:
            return self.entity_description.value_fn(self.coordinator.data)
        except Exception:
            _LOGGER.exception(
                "Wert für Sensor '%s' konnte nicht ermittelt werden",
                self.entity_description.key,
            )
            return None

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return truncate_state(self._raw_value())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the untruncated value for text sensors."""
        raw = self._raw_value()
        if isinstance(raw, str):
            return {"full_value": raw}
        return None
