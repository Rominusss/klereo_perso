"""Tests for params-based setpoints, generic field sensors, and the raw
diagnostic fallback that surfaces every remaining scalar field from the
Klereo API."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.klereo_perso.binary_sensor import KlereoAlertBinarySensor
from custom_components.klereo_perso.number import KlereoNumber, _extract_numbers
from custom_components.klereo_perso.sensor import (
    KlereoAlertCountSensor,
    KlereoFieldSensor,
    KlereoSchedulePlansSensor,
    _extract_sensors,
)

# A trimmed-down version of a real GetPoolDetails payload (2026-07 firmware),
# where setpoints live under "params" rather than "RegulModes".
REAL_WORLD_DETAILS = {
    "RegulModes": {"PoolMode": 2, "TraitMode": 8, "pHMode": 1, "HeaterMode": 4},
    "params": {
        "ConsigneEau": 28,
        "ConsignePH": 7.3,
        "ConsigneRedox": 640,
        "ConsigneChlore": 1.5,
        "EauMin": 0,
        "EauMax": 40,
        "pHMin": 6.6,
        "pHMax": 8,
        "OrpMin": 500,
        "OrpMax": 850,
        "VolumeEau": 44,
        "DebitPompe": 11,
        "Filtration_TotalTime": 81907,
        "Filtration_TodayTime": 38339,
        "Elec_Throttle": 100,  # not curated -> should surface via raw fallback
    },
    "ExtraParams": {
        "PmpWatts": 244,
        "PmpFlow": 8,
        "PmpSpeed": 60,
        "PmpRPM": 0,
        "CellVoltage": 0,
        "CellIntensity": 0,
        "Debit1": {"CfgDeb1": 6722, "SecVolume1": 5},
        "AqOnOff": 0,  # not curated -> raw fallback
    },
    "register": {"pin": "0301-5854438-4933", "proID": 4933, "lastUpdate": 1777023317},
    "podinfo": {"app": 296, "pingSent": 2531, "pongRx": 2545, "pingFail": 4},
    "probes": [],
    "outs": [],
    "lastPing": 13,
    "HorsGel": 3,
    "status": 135006226,  # not curated -> raw fallback
    "alertCount": 0,
    "notifyCount": 1,
    "alerts": [{"index": 0, "code": 45, "param": 3, "level": 2}],
    "plans": [{"index": 0, "plan": "\x00\x00", "plan64": "AAA=", "updateTime": 149}],
}


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with real-world-shaped data."""
    coordinator = MagicMock()
    coordinator.async_set_param = AsyncMock()
    coordinator.data = {
        "SYS1": {
            "info": {"idSystem": "SYS1", "poolNickname": "My Pool"},
            "details": REAL_WORLD_DETAILS,
        }
    }
    return coordinator


class TestParamsBasedSetpoints:
    """Setpoints living under details['params'] (current firmware)."""

    def test_extract_numbers_finds_params_setpoints(self, mock_coordinator):
        """All four known setpoints should be discovered from 'params'."""
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_numbers(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_number_ConsigneEau" in keys
        assert "SYS1_number_ConsignePH" in keys
        assert "SYS1_number_ConsigneRedox" in keys
        assert "SYS1_number_ConsigneChlore" in keys

    def test_dynamic_bounds_from_params(self, mock_coordinator):
        """Number entity should use the installation's real min/max, not static defaults."""
        number = KlereoNumber(mock_coordinator, "SYS1", "ConsignePH", 7.3)
        assert number._attr_native_min_value == 6.6
        assert number._attr_native_max_value == 8

    def test_falls_back_to_static_bounds_without_min_max_key(self, mock_coordinator):
        """ConsigneChlore has no min_key/max_key -> falls back to static bounds."""
        number = KlereoNumber(mock_coordinator, "SYS1", "ConsigneChlore", 1.5)
        assert number._attr_native_min_value == 0
        assert number._attr_native_max_value == 5

    def test_value_read_from_params_not_regulmodes(self, mock_coordinator):
        """Value should come from 'params', which is where real firmware puts it."""
        number = KlereoNumber(mock_coordinator, "SYS1", "ConsigneEau", 28)
        mock_coordinator.data["SYS1"]["details"]["params"]["ConsigneEau"] = 30
        number._handle_coordinator_update()
        assert number._attr_native_value == 30


class TestKlereoFieldSensor:
    """The generic, path-based field sensor used for all curated sub-sections."""

    def test_reads_from_params(self, mock_coordinator):
        sensor = KlereoFieldSensor(
            mock_coordinator, "SYS1", ("params",), "VolumeEau",
            {"name": "Pool Volume", "unit": "m³"}, "SYS1_paraminfo_VolumeEau",
        )
        assert sensor._attr_native_value == 44
        assert sensor._attr_name == "Pool Volume"

    def test_reads_from_nested_extraparams_path(self, mock_coordinator):
        """Should be able to descend two levels (ExtraParams -> Debit1)."""
        sensor = KlereoFieldSensor(
            mock_coordinator, "SYS1", ("ExtraParams", "Debit1"), "CfgDeb1",
            {"name": "Debit1 CfgDeb1", "unit": None}, "SYS1_raw_extra_debit1_CfgDeb1",
        )
        assert sensor._attr_native_value == 6722

    def test_diagnostic_flag_sets_entity_category_and_disabled_default(self, mock_coordinator):
        sensor = KlereoFieldSensor(
            mock_coordinator, "SYS1", ("params",), "Elec_Throttle",
            {"name": "Raw: Elec Throttle", "unit": None, "diagnostic": True},
            "SYS1_raw_params_Elec_Throttle",
        )
        assert sensor._attr_entity_registry_enabled_default is False
        assert sensor._attr_entity_category is not None

    def test_becomes_unavailable_when_system_disappears(self, mock_coordinator):
        sensor = KlereoFieldSensor(
            mock_coordinator, "MISSING", ("params",), "VolumeEau",
            {"name": "Pool Volume", "unit": "m³"}, "MISSING_paraminfo_VolumeEau",
        )
        sensor._handle_coordinator_update()
        assert sensor._attr_available is False


class TestRawFallback:
    """The generic raw fallback that surfaces every remaining scalar field."""

    def test_extract_sensors_includes_uncurated_params_field(self, mock_coordinator):
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_raw_params_Elec_Throttle" in keys

    def test_extract_sensors_includes_uncurated_root_field(self, mock_coordinator):
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_raw_root_status" in keys

    def test_extract_sensors_includes_nested_extraparams_dict(self, mock_coordinator):
        """Debit1 is a nested dict inside ExtraParams -> flattened with a prefix."""
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_raw_extra_debit1_CfgDeb1" in keys

    def test_extract_sensors_includes_register_fields(self, mock_coordinator):
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_raw_register_pin" in keys

    def test_no_duplicate_entities_for_curated_fields(self, mock_coordinator):
        """A field curated elsewhere (e.g. PmpWatts) must not also appear as raw."""
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = [uid for uid, _ in items]
        assert keys.count("SYS1_pump_PmpWatts") == 1
        assert "SYS1_raw_extra_PmpWatts" not in keys

    def test_no_duplicate_uids_at_all(self, mock_coordinator):
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = [uid for uid, _ in items]
        assert len(keys) == len(set(keys))


class TestSchedulePlansSensor:
    """Schedule plan count + safe (plan64-only) attribute list."""

    def test_extract_sensors_includes_schedule_plans(self, mock_coordinator):
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_schedule_plans" in keys

    def test_value_is_plan_count_and_raw_binary_omitted(self, mock_coordinator):
        sensor = KlereoSchedulePlansSensor(mock_coordinator, "SYS1")
        assert sensor._attr_native_value == 1
        plan_attr = sensor._attr_extra_state_attributes["plans"][0]
        assert plan_attr["plan64"] == "AAA="
        assert "plan" not in plan_attr


class TestAlertSensors:
    """Alert count sensor and problem binary sensor."""

    def test_extract_sensors_includes_alert_count(self, mock_coordinator):
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_alert_count" in keys

    def test_alert_count_sensor_exposes_raw_alerts(self, mock_coordinator):
        sensor = KlereoAlertCountSensor(mock_coordinator, "SYS1")
        assert sensor._attr_extra_state_attributes["alerts"] == REAL_WORLD_DETAILS["alerts"]

    def test_binary_sensor_on_when_alerts_present_despite_zero_count(self, mock_coordinator):
        """alertCount=0 but a real alert is present in 'alerts' -> should be ON."""
        binary_sensor = KlereoAlertBinarySensor(mock_coordinator, "SYS1")
        assert binary_sensor._attr_is_on is True

    def test_binary_sensor_off_when_no_alerts(self, mock_coordinator):
        mock_coordinator.data["SYS1"]["details"] = {**REAL_WORLD_DETAILS, "alertCount": 0, "alerts": []}
        binary_sensor = KlereoAlertBinarySensor(mock_coordinator, "SYS1")
        assert binary_sensor._attr_is_on is False
