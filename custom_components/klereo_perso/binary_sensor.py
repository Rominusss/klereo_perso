"""Binary sensor platform for Klereo."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import KlereoEntity, setup_discovery

_LOGGER = logging.getLogger(__name__)


def _extract_binary_sensors(coordinator, system_id, details):
    """Extract binary sensors from system details."""
    items = []
    # Created whenever the system reports alert-related fields at all,
    # regardless of whether there is currently an active alert.
    if "alertCount" in details or "alerts" in details:
        uid = f"{system_id}_alert_active"
        items.append((uid, KlereoAlertBinarySensor(coordinator, system_id)))
    return items


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Klereo binary sensors."""
    setup_discovery(hass, entry, async_add_entities, _extract_binary_sensors)


class KlereoAlertBinarySensor(KlereoEntity, BinarySensorEntity):
    """Whether the Klereo system currently reports an active alert.

    Klereo's own "alertCount" field and the length of the "alerts" list can
    disagree in practice (e.g. alertCount=0 while an unacknowledged alert is
    still present in "alerts"). To avoid missing a real problem, this sensor
    considers an alert active if *either* signal indicates one.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, system_id):
        """Initialize the alert binary sensor."""
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{system_id}_alert_active"
        self._attr_name = "Alert Active"
        self._update_from_data(coordinator.data.get(system_id, {}).get("details", {}))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        if self.system_id not in self.coordinator.data:
            self._attr_available = False
            return super()._handle_coordinator_update()
        self._attr_available = True
        details = self.coordinator.data[self.system_id].get("details", {})
        self._update_from_data(details)
        super()._handle_coordinator_update()

    def _update_from_data(self, details):
        """Update state from the system's alert data."""
        alerts = details.get("alerts", [])
        alert_count = details.get("alertCount", 0)
        self._attr_is_on = bool(alert_count) or bool(alerts)
        self._attr_extra_state_attributes = {
            "alert_count": alert_count,
            "notify_count": details.get("notifyCount"),
            "alerts": alerts,
        }
