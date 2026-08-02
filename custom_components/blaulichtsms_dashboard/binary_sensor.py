"""Binary sensor platform for BlaulichtSMS Dashboard."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BlaulichtSMSEntity
from .helpers import is_alarm_active


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlaulichtSMS binary sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BlaulichtSMSAlarmBinarySensor(coordinator)])


class BlaulichtSMSAlarmBinarySensor(BlaulichtSMSEntity, BinarySensorEntity):
    """Sprachneutrale Variante des Einsatzstatus-Sensors."""

    _attr_translation_key = "einsatz_aktiv"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, "einsatz_aktiv")

    @property
    def is_on(self) -> bool:
        """Return True while an alarm is active."""
        return is_alarm_active(self.coordinator.data)
