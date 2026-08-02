"""Button platform for BlaulichtSMS Dashboard."""
from datetime import datetime, timezone

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BlaulichtSMSEntity
from .helpers import generate_tts_text


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


class BlaulichtSMSTestAlarmButton(BlaulichtSMSEntity, ButtonEntity):
    """Button to trigger a test alarm.

    Achtung: der Knopf überschreibt die Coordinator-Daten mit einem Fake-Alarm.
    Ein laufender echter Alarm ist dadurch bis zum nächsten Poll verdeckt -
    deshalb ist die Entity als Diagnose-Werkzeug eingestuft.
    """

    _attr_translation_key = "test_alarm"
    _attr_icon = "mdi:alarm-light"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "test_alarm_btn")

    async def async_press(self) -> None:
        """Handle the button press."""
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        alarm_text = "Generierter Probealarm via Home Assistant Button."
        if self.coordinator.data and len(self.coordinator.data) > 0:
            alarm_text = self.coordinator.data[0].get("alarmText", alarm_text)

        fake_data = [
            {
                "alarmDate": now_str,
                "alarmText": alarm_text,
                "authorName": "Home Assistant",
                "isTestAlarm": True,
                "alarmGroups": [{"groupName": "Test Gruppe"}],
                "usersAlertedCount": 0,
                "recipients": [],
                "geolocation": {"address": "Teststraße 1, 12345 Home Assistant"}
            }
        ]
        self.coordinator.async_set_updated_data(fake_data)


class BlaulichtSMSRepeatTTSButton(BlaulichtSMSEntity, ButtonEntity):
    """Button to repeat the current alarm text for TTS."""

    _attr_translation_key = "repeat_tts"
    _attr_icon = "mdi:bullhorn"

    def __init__(self, coordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "repeat_tts_btn")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"tts_text": generate_tts_text(self.coordinator.data)}

    async def async_press(self) -> None:
        """Handle the button press."""
        # A button press in Home Assistant automatically creates a timestamp state change.
        # This is enough to trigger an automation. We can optionally fire a custom event.
        self.hass.bus.async_fire(
            f"{DOMAIN}_repeat_tts",
            {
                "customer_id": self.coordinator.customer_id,
                "entry_id": self.coordinator.config_entry.entry_id,
                "tts_text": generate_tts_text(self.coordinator.data),
            },
        )
