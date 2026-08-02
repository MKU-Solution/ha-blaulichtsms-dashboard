"""Base entity for the BlaulichtSMS Dashboard integration."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class BlaulichtSMSEntity(CoordinatorEntity):
    """Common device info and naming for all BlaulichtSMS entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=f"BlaulichtSMS ({coordinator.username})",
            manufacturer="BlaulichtSMS",
        )
