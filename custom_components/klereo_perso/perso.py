"""Perso layer: the entities and attributes that exist only in this fork.

Upstream (JonBasse/ha-klereo) hands the platforms typed models and drops every payload
field it does not read. This fork additionally exposes *everything* the Klereo API sends:

* curated sensors from `params` / `ExtraParams` / `podinfo` / root fields,
* a generic "raw" diagnostic sensor for every remaining scalar (disabled by default),
* decoded schedule plans (`schedule.py`),
* an alert counter sensor and an "Alert Active" binary sensor,
* extra attributes on probe sensors and output switches,
* firmware / serial number on the device.

All of it reads `KlereoPoolDetails.raw` (the verbatim `GetPoolDetails` element) laid over
`KlereoSystemInfo.raw` (the `GetIndex` entry) — the same merged view the pre-2.0 fork used.

🔴 The `unique_id` of every entity below is IDENTICAL to the one the fork used before it
was rebased on upstream 1.20. Do not change them: they carry the entity registry (entity
IDs, history, dashboards and automations such as the hybrid chlorinator accumulation).

Kept in its own module so that merging a new upstream release only touches the few
hook lines in `sensor.py`, `binary_sensor.py`, `switch.py` and `entity.py`.
"""
from __future__ import annotations

import re
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory

from .const import PARAM_TYPES
from .entity import KlereoEntity
from .perso_const import (
    CELL_TELEMETRY_SENSORS,
    PARAM_INFO_SENSORS,
    PODINFO_SENSORS,
    PUMP_TELEMETRY_SENSORS,
    SYSTEM_DIAGNOSTIC_SENSORS,
    SYSTEM_SENSORS,
)
from .schedule import PLAN_ECREMAGE, PLAN_FILTRATION, decode_plan, schedule_text

# Keys structurally handled elsewhere (lists that become their own entities, or dicts
# consumed by dedicated logic) — never surfaced by the generic raw-field fallback.
_ROOT_STRUCTURAL_KEYS = {
    "probes", "outs", "alerts", "plans", "RegulModes", "params",
    "ExtraParams", "IORename", "podinfo", "register",
    "_probe_index", "_output_index",
    "idSystem", "poolNickname", "idLinked",
    "alertCount", "notifyCount",  # already covered by KlereoAlertCountSensor
}
_EXTRAPARAMS_NESTED_DICT_KEYS = {"Debit1", "Debit2"}


# --------------------------------------------------------------------------- helpers


def merged_details(coordinator, system_id: str) -> dict[str, Any]:
    """Return the legacy merged payload: `GetIndex` entry + `GetPoolDetails` element."""
    system = coordinator.data.get(system_id)
    if system is None:
        return {}
    return {**system.info.raw, **system.details.raw}


def probe_extra_attributes(coordinator, system_id: str, index: int) -> dict[str, Any]:
    """Extra attributes for a probe sensor (every field the API sends for a probe)."""
    for probe in merged_details(coordinator, system_id).get("probes", []):
        if probe.get("index") == index:
            return {
                "threshold_min": probe.get("seuilMin"),
                "threshold_max": probe.get("seuilMax"),
                "updated": probe.get("updated"),
                "filtered_time": probe.get("filteredTime"),
                "direct_time": probe.get("directTime"),
                "update_time": probe.get("updateTime"),
                "calibration": [probe.get("calib1"), probe.get("calib2"), probe.get("calib3")],
            }
    return {}


def output_extra_attributes(coordinator, system_id: str, index: int) -> dict[str, Any]:
    """Extra attributes for an output switch (every field the API sends for an output)."""
    for out in merged_details(coordinator, system_id).get("outs", []):
        if out.get("index") == index:
            return {
                "total_time": out.get("totalTime"),
                "off_delay": out.get("offDelay"),
                "flags": out.get("flags"),
                "map": out.get("map"),
                "clone_src": out.get("cloneSrc"),
                "update_time": out.get("updateTime"),
                "real_status": out.get("realStatus"),
                "recur_mode": out.get("recurMode"),
                "recur_date": out.get("recurDate"),
            }
    return {}


def device_extra(coordinator, system_id: str) -> dict[str, Any]:
    """Firmware version and serial number for DeviceInfo (only in the detailed payload)."""
    details = merged_details(coordinator, system_id)
    return {
        "sw_version": details.get("affSW") or details.get("tabSW"),
        "serial_number": details.get("podSerial"),
    }


def _humanize_key(key: str) -> str:
    """Convert a camelCase API key to a human-readable name."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key).strip()


def _curated_keys() -> set:
    """All keys already surfaced by a curated (named, typed) entity."""
    return (
        set(PARAM_TYPES)
        | set(PARAM_INFO_SENSORS)
        | set(PUMP_TELEMETRY_SENSORS)
        | set(CELL_TELEMETRY_SENSORS)
        | set(SYSTEM_DIAGNOSTIC_SENSORS)
        | set(SYSTEM_SENSORS)
        | set(PODINFO_SENSORS)
    )


# --------------------------------------------------------------------------- discovery


def extract_perso_sensors(coordinator, system_id: str) -> list:
    """Return (unique_id, entity) tuples for every perso-only sensor."""
    details = merged_details(coordinator, system_id)
    items: list = []

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
    # Every remaining scalar field, anywhere in the payload, not already surfaced above.
    # Diagnostic category + disabled by default; nothing from the API is silently dropped.
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

    # --- Schedule plans: overview + one decoded sensor per plan ---
    if "plans" in details:
        items.append((f"{system_id}_schedule_plans", KlereoSchedulePlansSensor(coordinator, system_id)))
        for plan in details.get("plans", []):
            if plan.get("index") is None:
                continue
            plan_index = int(plan["index"])
            items.append(
                (f"{system_id}_plan_{plan_index}", KlereoSchedulePlanSensor(coordinator, system_id, plan_index))
            )

    # --- Alert counter (Klereo's own alertCount, falling back to len(alerts)) ---
    if "alertCount" in details or "alerts" in details:
        items.append((f"{system_id}_alert_count", KlereoAlertCountSensor(coordinator, system_id)))

    return items


def extract_perso_binary_sensors(coordinator, system_id: str) -> list:
    """Return (unique_id, entity) tuples for every perso-only binary sensor."""
    details = merged_details(coordinator, system_id)
    items: list = []
    if "alertCount" in details or "alerts" in details:
        uid = f"{system_id}_alert_active"
        items.append((uid, KlereoAlertBinarySensor(coordinator, system_id)))
    return items


# --------------------------------------------------------------------------- entities


class KlereoFieldSensor(KlereoEntity, SensorEntity):
    """Generic sensor that reads a single field from a nested details path.

    `source_path` is a tuple of dict keys to descend into the merged payload before looking
    up `field_key` — e.g. `()` for the root, `("params",)`, or `("ExtraParams", "Debit1")`.
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

        self._update_value(merged_details(coordinator, system_id))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._update_value(merged_details(self.coordinator, self.system_id))
        super()._handle_coordinator_update()

    def _update_value(self, details):
        """Descend `source_path` from `details` and read `field_key`.

        The last value is kept when the key disappears (same behaviour as before 2.0).
        """
        node = details
        for part in self._source_path:
            node = node.get(part, {}) if isinstance(node, dict) else {}
        if isinstance(node, dict) and self._field_key in node:
            self._attr_native_value = node[self._field_key]


class KlereoSchedulePlansSensor(KlereoEntity, SensorEntity):
    """Overview of all schedule plans returned by Klereo."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, system_id):
        """Initialize the schedule plans overview sensor."""
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{system_id}_schedule_plans"
        self._attr_name = "Schedule Plans"
        self._update_from_data(merged_details(coordinator, system_id))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._update_from_data(merged_details(self.coordinator, self.system_id))
        super()._handle_coordinator_update()

    def _update_from_data(self, details):
        """Update the overview with decoded plans."""
        decoded_plans = []
        for plan in details.get("plans", []):
            index = plan.get("index")
            if index is None:
                continue
            decoded = decode_plan(int(index), plan.get("plan64", ""))
            if decoded is None:
                continue
            decoded_plans.append(
                {
                    "index": int(index),
                    "plan64": plan.get("plan64"),
                    "updateTime": plan.get("updateTime"),
                    "format": decoded.get("format"),
                    "active_slots": decoded.get("active_slots"),
                    "schedule": schedule_text(decoded, int(index)),
                }
            )
        self._attr_native_value = len(decoded_plans)
        self._attr_extra_state_attributes = {"plans": decoded_plans}


class KlereoSchedulePlanSensor(KlereoEntity, SensorEntity):
    """Decoded 15-minute Klereo schedule plan."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, system_id, plan_index):
        """Initialize a decoded schedule plan sensor."""
        super().__init__(coordinator, system_id)
        self._plan_index = plan_index
        self._attr_unique_id = f"{system_id}_plan_{plan_index}"
        self._attr_name = self._name_for_index(plan_index)
        self._available_plan = False
        self._update_from_data(merged_details(coordinator, system_id))

    @staticmethod
    def _name_for_index(plan_index: int) -> str:
        """Return a useful name for known Klereo plan indexes."""
        if plan_index == PLAN_FILTRATION:
            return "Filtration Schedule"
        if plan_index == PLAN_ECREMAGE:
            return "Skimming Schedule"
        if plan_index == 254:
            return "Plan 254 (3 Masks)"
        return f"Plan {plan_index}"

    @property
    def available(self) -> bool:
        """Unavailable once the payload stops carrying (or can't decode) this plan."""
        return super().available and self._available_plan

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._available_plan = self._update_from_data(merged_details(self.coordinator, self.system_id))
        super()._handle_coordinator_update()

    def _find_plan(self, details):
        """Find this plan in the API payload."""
        for plan in details.get("plans", []):
            if plan.get("index") == self._plan_index:
                return plan
        return None

    def _update_from_data(self, details) -> bool:
        """Decode the plan and update state/attributes."""
        plan = self._find_plan(details)
        if not plan:
            self._available_plan = False
            return False

        decoded = decode_plan(self._plan_index, plan.get("plan64", ""))
        if decoded is None:
            self._available_plan = False
            return False

        self._attr_native_value = schedule_text(decoded, self._plan_index)
        attributes = {
            "plan_index": self._plan_index,
            "plan64": decoded.get("plan64"),
            "raw_hex": decoded.get("raw_hex"),
            "format": decoded.get("format"),
            "slot_count": decoded.get("slot_count"),
            "slot_minutes": decoded.get("slot_minutes"),
            "active_slots": decoded.get("active_slots"),
            "schedule": decoded.get("ranges", []),
            "update_time": plan.get("updateTime"),
        }

        if self._plan_index == 254:
            attributes["masks"] = decoded.get("masks", [])
        else:
            attributes["slots"] = decoded.get("slots", [])
            if self._plan_index == PLAN_FILTRATION:
                attributes["speed_1_slots"] = decoded.get("speed_1_slots")
                attributes["speed_2_slots"] = decoded.get("speed_2_slots")

        self._attr_extra_state_attributes = attributes
        self._available_plan = True
        return True


class KlereoAlertCountSensor(KlereoEntity, SensorEntity):
    """Number of active alerts reported by the Klereo system."""

    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator, system_id):
        """Initialize the alert count sensor."""
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{system_id}_alert_count"
        self._attr_name = "Active Alerts"
        self._attr_native_unit_of_measurement = "alerts"
        self._update_from_data(merged_details(coordinator, system_id))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._update_from_data(merged_details(self.coordinator, self.system_id))
        super()._handle_coordinator_update()

    def _update_from_data(self, details):
        """Update state from the system's alert data."""
        alerts = details.get("alerts", [])
        self._attr_native_value = details.get("alertCount", len(alerts))
        self._attr_extra_state_attributes = {
            "notify_count": details.get("notifyCount"),
            "alerts": alerts,
        }


class KlereoAlertBinarySensor(KlereoEntity, BinarySensorEntity):
    """Whether the Klereo system currently reports an active alert.

    Klereo's own `alertCount` and the length of `alerts` can disagree in practice
    (alertCount=0 while an alert is still listed), so an alert is active if EITHER
    signal indicates one.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, system_id):
        """Initialize the alert binary sensor."""
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{system_id}_alert_active"
        self._attr_name = "Alert Active"
        self._update_from_data(merged_details(coordinator, system_id))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._update_from_data(merged_details(self.coordinator, self.system_id))
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
