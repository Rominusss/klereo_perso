"""Tests for the params-based setpoints, pump telemetry, and alert sensors."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.klereo_perso.binary_sensor import KlereoAlertBinarySensor
from custom_components.klereo_perso.number import KlereoNumber, _extract_numbers
from custom_components.klereo_perso.sensor import (
    KlereoAlertCountSensor,
    KlereoParamInfoSensor,
    KlereoPumpSensor,
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
    },
    "ExtraParams": {
        "PmpWatts": 244,
        "PmpFlow": 8,
        "PmpSpeed": 60,
        "PmpRPM": 0,
    },
    "probes": [],
    "outs": [],
    "alertCount": 0,
    "notifyCount": 1,
    "alerts": [{"index": 0, "code": 45, "param": 3, "level": 2}],
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


class TestParamInfoSensors:
    """Read-only informational sensors from details['params']."""

    def test_extract_sensors_includes_param_info(self, mock_coordinator):
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_paraminfo_VolumeEau" in keys
        assert "SYS1_paraminfo_Filtration_TotalTime" in keys

    def test_param_info_sensor_value(self, mock_coordinator):
        sensor = KlereoParamInfoSensor(mock_coordinator, "SYS1", "VolumeEau")
        assert sensor._attr_native_value == 44
        assert sensor._attr_name == "Pool Volume"


class TestPumpTelemetrySensors:
    """Variable-speed pump telemetry from details['ExtraParams']."""

    def test_extract_sensors_includes_pump_telemetry(self, mock_coordinator):
        details = mock_coordinator.data["SYS1"]["details"]
        items = _extract_sensors(mock_coordinator, "SYS1", details)
        keys = {uid for uid, _ in items}
        assert "SYS1_pump_PmpWatts" in keys

    def test_pump_sensor_value(self, mock_coordinator):
        sensor = KlereoPumpSensor(mock_coordinator, "SYS1", "PmpWatts")
        assert sensor._attr_native_value == 244
        assert sensor._attr_device_class == "power"


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
        """alertCount=0 but a real alert is present in 'alerts' -> should be ON.

        This mirrors real-world data where Klereo's own alertCount and the
        alerts list can disagree.
        """
        binary_sensor = KlereoAlertBinarySensor(mock_coordinator, "SYS1")
        assert binary_sensor._attr_is_on is True

    def test_binary_sensor_off_when_no_alerts(self, mock_coordinator):
        mock_coordinator.data["SYS1"]["details"] = {**REAL_WORLD_DETAILS, "alertCount": 0, "alerts": []}
        binary_sensor = KlereoAlertBinarySensor(mock_coordinator, "SYS1")
        assert binary_sensor._attr_is_on is False
