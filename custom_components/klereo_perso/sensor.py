"""Sensor platform for Klereo."""
import logging
import re

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CELL_TELEMETRY_SENSORS,
    PARAM_INFO_SENSORS,
    PARAM_NAMES,
    PARAM_TYPES,
    PODINFO_SENSORS,
    PUMP_TELEMETRY_SENSORS,
    SENSOR_TYPES,
    SYSTEM_DIAGNOSTIC_SENSORS,
    SYSTEM_SENSORS,
)
from .entity import KlereoEntity, setup_discovery

_LOGGER = logging.getLogger(__name__)

# Keys structurally handled elsewhere (lists that become their own entities,
# or dicts consumed by dedicated logic below) — never surfaced by the
# generic raw-field fallback, to avoid duplicating entities.
_ROOT_STRUCTURAL_KEYS = {
    "probes", "outs", "alerts", "plans", "RegulModes", "params",
    "ExtraParams", "IORename", "podinfo", "register",
    "_probe_index", "_output_index",
    "idSystem", "poolNickname", "idLinked",
    "alertCount", "notifyCount",  # already covered by KlereoAlertCountSensor
}
_EXTRAPARAMS_NESTED_DICT_KEYS = {"Debit1", "Debit2"}


def _humanize_key(key: str) -> str:
    """Convert a camelCase API key to a human-readable name."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key).strip()


def _curated_keys() -> set:
    """All keys already surfaced by a curated (named, typed) entity.

    Excluded from the generic raw-field fallback so nothing is duplicated.
    """
    return (
        set(PARAM_TYPES)
        | set(PARAM_INFO_SENSORS)
        | set(PUMP_TELEMETRY_SENSORS)
        | set(CELL_TELEMETRY_SENSORS)
        | set(SYSTEM_DIAGNOSTIC_SENSORS)
        | set(SYSTEM_SENSORS)
        | set(PODINFO_SENSORS)
    )


def _extract_sensors(coordinator, system_id, details):
    """Extract all sensor entities from system details."""
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

    # --- Curated sensors from named sub-sections ---
    for key in details.get("params", {}):
        if key not in PARAM_INFO_SENSORS:
            continue
        uid = f"{system_id}_paraminfo_{key}"
        items.append(
            (uid, KlereoFieldSensor(coordinator, system_id, ("params",), key, PARAM_INFO_SENSORS[key], uid))
        )

    extra_params = details.get("ExtraParams", {})
    for key in extra_params:
        if key in PUMP_TELEMETRY_SENSORS:
            uid = f"{system_id}_pump_{key}"
            items.append(
                (uid, KlereoFieldSensor(coordinator, system_id, ("ExtraParams",), key, PUMP_TELEMETRY_SENSORS[key], uid))
            )
        elif key in CELL_TELEMETRY_SENSORS:
            uid = f"{system_id}_cell_{key}"
            items.append(
                (uid, KlereoFieldSensor(coordinator, system_id, ("ExtraParams",), key, CELL_TELEMETRY_SENSORS[key], uid))
            )

    for key in SYSTEM_DIAGNOSTIC_SENSORS:
        if key in details:
            uid = f"{system_id}_sysdiag_{key}"
            meta = {**SYSTEM_DIAGNOSTIC_SENSORS[key], "diagnostic": True}
            items.append((uid, KlereoFieldSensor(coordinator, system_id, (), key, meta, uid)))

    for key in SYSTEM_SENSORS:
        if key in details:
            uid = f"{system_id}_sys_{key}"
            items.append((uid, KlereoFieldSensor(coordinator, system_id, (), key, SYSTEM_SENSORS[key], uid)))

    podinfo = details.get("podinfo", {})
    for key in PODINFO_SENSORS:
        if key in podinfo:
            uid = f"{system_id}_podinfo_{key}"
            meta = {**PODINFO_SENSORS[key], "diagnostic": True}
            items.append((uid, KlereoFieldSensor(coordinator, system_id, ("podinfo",), key, meta, uid)))

    # --- Generic raw fallback ---
    # Every remaining scalar field, anywhere in the payload, not already
    # surfaced above. Diagnostic category + disabled by default so it
    # doesn't clutter the entity list, but nothing from the Klereo API is
    # silently dropped — enable individual fields from the entity registry
    # if you need one that isn't curated above.
    curated = _curated_keys()

    def _add_raw(source_path, source_dict, uid_prefix):
        for key, value in source_dict.items():
            if key in curated or isinstance(value, (dict, list)):
                continue
            uid = f"{system_id}_raw_{uid_prefix}_{key}"
            meta = {"name": f"Raw: {_humanize_key(key)}", "unit": None, "diagnostic": True}
            items.append((uid, KlereoFieldSensor(coordinator, system_id, source_path, key, meta, uid)))

    _add_raw((), {k: v for k, v in details.items() if k not in _ROOT_STRUCTURAL_KEYS}, "root")
    _add_raw(("params",), details.get("params", {}), "params")

    extra_scan = {k: v for k, v in extra_params.items() if k not in _EXTRAPARAMS_NESTED_DICT_KEYS}
    _add_raw(("ExtraParams",), extra_scan, "extra")
    for nested_key in _EXTRAPARAMS_NESTED_DICT_KEYS:
        nested = extra_params.get(nested_key, {})
        if isinstance(nested, dict):
            _add_raw(("ExtraParams", nested_key), nested, f"extra_{nested_key.lower()}")

    _add_raw(("register",), details.get("register", {}), "register")
    _add_raw(("podinfo",), {k: v for k, v in podinfo.items() if k not in PODINFO_SENSORS}, "podinfo")

    # Schedule plans (opaque binary blobs) — exposed as a count + attribute
    # list of base64 payloads, rather than one entity per plan/field.
    if "plans" in details:
        uid = f"{system_id}_schedule_plans"
        items.append((uid, KlereoSchedulePlansSensor(coordinator, system_id)))

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
            "updated": data.get("updated"),
            "filtered_time": data.get("filteredTime"),
            "direct_time": data.get("directTime"),
            "update_time": data.get("updateTime"),
            "calibration": [data.get("calib1"), data.get("calib2"), data.get("calib3")],
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


class KlereoFieldSensor(KlereoEntity, SensorEntity):
    """Generic sensor that reads a single field from a nested details path.

    `source_path` is a tuple of dict keys to descend into `details` before
    looking up `field_key` — e.g. `()` for the details root, `("params",)`,
    or `("ExtraParams", "Debit1")`. Used both for curated, named sensors
    (pump telemetry, pool volume...) and for the generic raw-field fallback
    that surfaces every remaining scalar value reported by the Klereo API,
    so nothing is silently dropped.
    """

    def __init__(self, coordinator, system_id, source_path, field_key, meta, unique_id):
        """Initialize the field sensor."""
        super().__init__(coordinator, system_id)
        self._source_path = source_path
        self._field_key = field_key

        self._attr_unique_id = unique_id
        self._attr_name = meta["name"]
        self._attr_native_unit_of_measurement = meta.get("unit")
        self._attr_device_class = meta.get("device_class")

        state_class = meta.get("state_class")
        if state_class:
            self._attr_state_class = SensorStateClass(state_class)

        if meta.get("diagnostic"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

        self._update_value(coordinator.data.get(system_id, {}).get("details", {}))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        if self.system_id not in self.coordinator.data:
            self._attr_available = False
            return super()._handle_coordinator_update()
        self._attr_available = True
        details = self.coordinator.data[self.system_id].get("details", {})
        self._update_value(details)
        super()._handle_coordinator_update()

    def _update_value(self, details):
        """Descend `source_path` from `details` and read `field_key`."""
        node = details
        for part in self._source_path:
            node = node.get(part, {}) if isinstance(node, dict) else {}
        if isinstance(node, dict) and self._field_key in node:
            self._attr_native_value = node[self._field_key]


class KlereoSchedulePlansSensor(KlereoEntity, SensorEntity):
    """Number of schedule ("plans") entries reported by the system.

    The plan encoding is undocumented/opaque (raw binary time-slot data).
    Rather than trying to decode it, this exposes a count as the state and
    the base64 form (`plan64`, safe to store/print) as an attribute per
    plan, for anyone who wants to dig further. The original binary `plan`
    field is intentionally omitted from the attribute since it can contain
    non-printable control characters.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, system_id):
        """Initialize the schedule plans sensor."""
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{system_id}_schedule_plans"
        self._attr_name = "Schedule Plans"
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
        """Update state from the system's schedule plan data."""
        plans = details.get("plans", [])
        self._attr_native_value = len(plans)
        self._attr_extra_state_attributes = {
            "plans": [
                {"index": p.get("index"), "plan64": p.get("plan64"), "updateTime": p.get("updateTime")}
                for p in plans
            ]
        }


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
