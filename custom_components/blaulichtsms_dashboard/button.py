"""Button platform for BlaulichtSMS Dashboard."""
from datetime import datetime, timezone
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlaulichtSMS button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BlaulichtSMSTestAlarmButton(coordinator),
        BlaulichtSMSRepeatTTSButton(coordinator),
    ])


class BlaulichtSMSTestAlarmButton(CoordinatorEntity, ButtonEntity):
    """Button to trigger a test alarm."""

    def __init__(self, coordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Test Alarm Auslösen"
        self._attr_icon = "mdi:alarm-light"
        self._attr_unique_id = f"blaulichtsms_{coordinator.customer_id}_test_alarm_btn"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.customer_id)},
            "name": f"BlaulichtSMS ({self.coordinator.username})",
            "manufacturer": "BlaulichtSMS",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        fake_data = [
            {
                "alarmDate": now_str,
                "alarmText": "Generierter Probealarm via Home Assistant Button.",
                "authorName": "Home Assistant",
                "isTestAlarm": True,
                "alarmGroups": [{"groupName": "Test Gruppe"}],
                "usersAlertedCount": 0,
                "recipients": [],
                "geolocation": {"address": "Teststraße 1, 12345 Home Assistant"}
            }
        ]
        self.coordinator.async_set_updated_data(fake_data)


class BlaulichtSMSRepeatTTSButton(CoordinatorEntity, ButtonEntity):
    """Button to repeat the current alarm text for TTS."""

    def __init__(self, coordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "TTS Wiederholen"
        self._attr_icon = "mdi:bullhorn"
        self._attr_unique_id = f"blaulichtsms_{coordinator.customer_id}_repeat_tts_btn"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.customer_id)},
            "name": f"BlaulichtSMS ({self.coordinator.username})",
            "manufacturer": "BlaulichtSMS",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        # A button press in Home Assistant automatically creates a timestamp state change.
        # This is enough to trigger an automation. We can optionally fire a custom event.
        self.hass.bus.async_fire(
            f"{DOMAIN}_repeat_tts",
            {"customer_id": self.coordinator.customer_id}
        )
