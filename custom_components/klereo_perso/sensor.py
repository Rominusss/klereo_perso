"""Sensor platform for Klereo."""
import logging
import re

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    PARAM_INFO_SENSORS,
    PARAM_NAMES,
    PARAM_TYPES,
    PUMP_TELEMETRY_SENSORS,
    SENSOR_TYPES,
)
from .entity import KlereoEntity, setup_discovery

_LOGGER = logging.getLogger(__name__)


def _humanize_key(key: str) -> str:
    """Convert a camelCase API key to a human-readable name."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key)


def _extract_sensors(coordinator, system_id, details):
    """Extract probe sensors and param sensors from system details."""
    items = []
    for probe in details.get("probes", []):
        if probe.get("index") is None:
            continue
        uid = f"{system_id}_sensor_{probe['index']}"
        items.append((uid, KlereoSensor(coordinator, system_id, probe)))

    # Regulation mode sensors (RegulModes). Writable setpoints (PARAM_TYPES)
    # are excluded here since they become number entities instead.
    for key, value in details.get("RegulModes", {}).items():
        if key in PARAM_TYPES:
            continue
        uid = f"{system_id}_param_{key}"
        items.append((uid, KlereoParamSensor(coordinator, system_id, key, value)))

    # Read-only informational counters/config from details["params"]
    # (pool volume, filtration runtime, dosing time...). Writable setpoints
    # (PARAM_TYPES) are excluded here too since they become number entities.
    for key in details.get("params", {}):
        if key not in PARAM_INFO_SENSORS:
            continue
        uid = f"{system_id}_paraminfo_{key}"
        items.append((uid, KlereoParamInfoSensor(coordinator, system_id, key)))

    # Variable-speed pump telemetry from details["ExtraParams"].
    extra_params = details.get("ExtraParams", {})
    for key in extra_params:
        if key not in PUMP_TELEMETRY_SENSORS:
            continue
        uid = f"{system_id}_pump_{key}"
        items.append((uid, KlereoPumpSensor(coordinator, system_id, key)))

    # System-level alert counter, always created once alerts info is present.
    if "alertCount" in details or "alerts" in details:
        uid = f"{system_id}_alert_count"
        items.append((uid, KlereoAlertCountSensor(coordinator, system_id)))

    return items


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Klereo sensors."""
    setup_discovery(hass, entry, async_add_entities, _extract_sensors)


class KlereoSensor(KlereoEntity, SensorEntity):
    """Representation of a Klereo probe sensor."""

    def __init__(self, coordinator, system_id, sensor_data):
        """Initialize the sensor."""
        super().__init__(coordinator, system_id)
        self._index = sensor_data.get("index")
        self._type = sensor_data.get("type")

        sensor_def = SENSOR_TYPES.get(self._type, {})

        self._attr_unique_id = f"{system_id}_sensor_{self._index}"
        self._attr_name = sensor_def.get("name", f"Sensor {self._index}")
        self._attr_native_unit_of_measurement = sensor_def.get("unit")
        self._attr_device_class = sensor_def.get("device_class")

        state_class = sensor_def.get("state_class")
        if state_class:
            self._attr_state_class = SensorStateClass(state_class)

        self._update_from_data(sensor_data)

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        data = self._find_my_data()
        if data:
            self._attr_available = True
            self._update_from_data(data)
        else:
            self._attr_available = False
        super()._handle_coordinator_update()

    def _update_from_data(self, data):
        """Update state from probe data."""
        value = data.get("filteredValue")
        if value is None:
            value = data.get("directValue")
        self._attr_native_value = value
        self._attr_extra_state_attributes = {
            "type": data.get("type"),
            "status": data.get("status"),
            "threshold_min": data.get("seuilMin"),
            "threshold_max": data.get("seuilMax"),
        }

    def _find_my_data(self):
        """Find this probe's data in the coordinator data."""
        if self.system_id not in self.coordinator.data:
            return None
        details = self.coordinator.data[self.system_id].get("details", {})
        return details.get("_probe_index", {}).get(self._index)


class KlereoParamSensor(KlereoEntity, SensorEntity):
    """Representation of a Klereo regulation parameter as a sensor."""

    def __init__(self, coordinator, system_id, key, initial_value):
        """Initialize the parameter sensor."""
        super().__init__(coordinator, system_id)
        self._key = key

        self._attr_unique_id = f"{system_id}_param_{key}"
        self._attr_name = PARAM_NAMES.get(key, _humanize_key(key))
        self._attr_native_value = initial_value

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        if self.system_id not in self.coordinator.data:
            self._attr_available = False
            return super()._handle_coordinator_update()
        self._attr_available = True
        details = self.coordinator.data[self.system_id].get("details", {})
        regul = details.get("RegulModes", {})
        if self._key in regul:
            self._attr_native_value = regul[self._key]
        super()._handle_coordinator_update()


class KlereoParamInfoSensor(KlereoEntity, SensorEntity):
    """Read-only informational sensor sourced from details["params"]."""

    def __init__(self, coordinator, system_id, key):
        """Initialize the param info sensor."""
        super().__init__(coordinator, system_id)
        self._key = key
        meta = PARAM_INFO_SENSORS[key]

        self._attr_unique_id = f"{system_id}_paraminfo_{key}"
        self._attr_name = meta["name"]
        self._attr_native_unit_of_measurement = meta.get("unit")
        self._attr_device_class = meta.get("device_class")

        state_class = meta.get("state_class")
        if state_class:
            self._attr_state_class = SensorStateClass(state_class)

        self._update_from_params(coordinator.data.get(system_id, {}).get("details", {}))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        if self.system_id not in self.coordinator.data:
            self._attr_available = False
            return super()._handle_coordinator_update()
        self._attr_available = True
        details = self.coordinator.data[self.system_id].get("details", {})
        self._update_from_params(details)
        super()._handle_coordinator_update()

    def _update_from_params(self, details):
        """Update state from details["params"]."""
        params = details.get("params", {})
        if self._key in params:
            self._attr_native_value = params[self._key]


class KlereoPumpSensor(KlereoEntity, SensorEntity):
    """Variable-speed pump telemetry sensor from details["ExtraParams"]."""

    def __init__(self, coordinator, system_id, key):
        """Initialize the pump telemetry sensor."""
        super().__init__(coordinator, system_id)
        self._key = key
        meta = PUMP_TELEMETRY_SENSORS[key]

        self._attr_unique_id = f"{system_id}_pump_{key}"
        self._attr_name = meta["name"]
        self._attr_native_unit_of_measurement = meta.get("unit")
        self._attr_device_class = meta.get("device_class")

        state_class = meta.get("state_class")
        if state_class:
            self._attr_state_class = SensorStateClass(state_class)

        self._update_from_extra_params(coordinator.data.get(system_id, {}).get("details", {}))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        if self.system_id not in self.coordinator.data:
            self._attr_available = False
            return super()._handle_coordinator_update()
        self._attr_available = True
        details = self.coordinator.data[self.system_id].get("details", {})
        self._update_from_extra_params(details)
        super()._handle_coordinator_update()

    def _update_from_extra_params(self, details):
        """Update state from details["ExtraParams"]."""
        extra_params = details.get("ExtraParams", {})
        if self._key in extra_params:
            self._attr_native_value = extra_params[self._key]


class KlereoAlertCountSensor(KlereoEntity, SensorEntity):
    """Number of active alerts reported by the Klereo system."""

    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator, system_id):
        """Initialize the alert count sensor."""
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{system_id}_alert_count"
        self._attr_name = "Active Alerts"
        self._attr_native_unit_of_measurement = "alerts"
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
        self._attr_native_value = details.get("alertCount", len(alerts))
        self._attr_extra_state_attributes = {
            "notify_count": details.get("notifyCount"),
            "alerts": alerts,
        }
