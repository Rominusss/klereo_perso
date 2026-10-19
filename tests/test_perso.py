"""Tests for the perso layer (fork-only entities).

🔴 The unique_ids asserted here are the ones the fork used BEFORE it was rebased on upstream
1.20. They carry the entity registry (entity IDs, history, automations such as the hybrid
chlorinator accumulation), so a change here is a breaking change for the user.
"""
from unittest.mock import MagicMock

from custom_components.klereo_perso.models import (
    KlereoPoolDetails,
    KlereoSystemData,
    KlereoSystemInfo,
)
from custom_components.klereo_perso.perso import (
    device_extra,
    extract_perso_binary_sensors,
    extract_perso_sensors,
    merged_details,
    output_extra_attributes,
    probe_extra_attributes,
)
from custom_components.klereo_perso.sensor import KlereoSensor, _extract_sensors

SYS = "SYS1"
# 12-byte plan64 (all zero) so decode_plan returns a decodable plan.
PLAN64 = "AAAAAAAAAAAAAAAA"

INDEX = {"idSystem": SYS, "poolNickname": "Ma piscine", "access": 10}
POOL = {
    "Now": 1790000000,
    "lastPing": 2,
    "HorsGel": 0,
    "alertCount": 0,
    "probes": [
        {"index": 0, "type": 5, "filteredValue": 28.5, "directValue": 28.4, "status": 0,
         "seuilMin": 1, "seuilMax": 40, "calib1": 0.1, "calib2": 0.2, "calib3": 0.3},
    ],
    "outs": [{"index": 0, "status": 1, "mode": 0, "type": 0, "totalTime": 42, "realStatus": 1,
              "recurMode": 0, "recurDate": 0}],
    "params": {"VolumeEau": 30, "Filtration_TotalTime": 100, "ElectroChlore_TotalTime": 5,
               "HybChl_TotalTime": 777, "SomethingNew": 1},
    "ExtraParams": {"PmpWatts": 80, "CellVoltage": 1.5, "HybChl_Today": 3,
                    "Debit1": {"Flow": 2}},
    "podinfo": {"pingSent": 1, "app": 120},
    "register": {"compta": "XX00000", "pin": "0000-0000000-0000"},
    "affSW": "000A",
    "podSerial": "POD00012345",
    "plans": [{"index": 255, "plan64": PLAN64, "updateTime": 1}],
}


def _coordinator():
    system = KlereoSystemData(
        info=KlereoSystemInfo.from_dict(INDEX),
        details=KlereoPoolDetails.from_dict({**INDEX, **POOL}, raw=POOL),
    )
    coord = MagicMock()
    coord.data = {SYS: system}
    return coord


def _uids(items):
    return {uid for uid, _ in items}


def test_merged_details_is_getindex_overlaid_by_pool_details():
    merged = merged_details(_coordinator(), SYS)
    assert merged["poolNickname"] == "Ma piscine"  # GetIndex half
    assert merged["Now"] == 1790000000  # GetPoolDetails half


def test_legacy_unique_ids_are_unchanged():
    uids = _uids(extract_perso_sensors(_coordinator(), SYS))
    expected = {
        f"{SYS}_paraminfo_VolumeEau",
        f"{SYS}_paraminfo_Filtration_TotalTime",
        f"{SYS}_pump_PmpWatts",
        f"{SYS}_cell_CellVoltage",
        f"{SYS}_sysdiag_lastPing",
        f"{SYS}_sys_HorsGel",
        f"{SYS}_podinfo_pingSent",
        # raw fallback: what the user's automations rely on
        f"{SYS}_raw_root_Now",
        f"{SYS}_raw_root_access",
        f"{SYS}_raw_params_HybChl_TotalTime",
        f"{SYS}_raw_params_SomethingNew",
        f"{SYS}_raw_extra_HybChl_Today",
        f"{SYS}_raw_extra_debit1_Flow",
        f"{SYS}_raw_podinfo_app",
        f"{SYS}_raw_register_compta",
        f"{SYS}_schedule_plans",
        f"{SYS}_plan_255",
        f"{SYS}_alert_count",
    }
    assert expected <= uids


def test_curated_keys_are_not_duplicated_as_raw():
    uids = _uids(extract_perso_sensors(_coordinator(), SYS))
    assert f"{SYS}_raw_params_VolumeEau" not in uids
    assert f"{SYS}_raw_extra_PmpWatts" not in uids
    assert f"{SYS}_raw_root_lastPing" not in uids
    assert f"{SYS}_raw_podinfo_pingSent" not in uids


def test_structural_keys_never_become_raw_sensors():
    uids = _uids(extract_perso_sensors(_coordinator(), SYS))
    for key in ("probes", "outs", "plans", "params", "alertCount", "poolNickname"):
        assert f"{SYS}_raw_root_{key}" not in uids


def test_raw_sensors_are_diagnostic_and_disabled_by_default():
    items = dict(extract_perso_sensors(_coordinator(), SYS))
    raw = items[f"{SYS}_raw_params_HybChl_TotalTime"]
    assert raw.entity_registry_enabled_default is False
    assert raw.entity_category is not None
    assert raw.name == "Raw: Hyb Chl_Total Time" or raw.name.startswith("Raw:")
    assert raw.native_value == 777


def test_raw_now_value_is_readable_for_the_reload_automation():
    items = dict(extract_perso_sensors(_coordinator(), SYS))
    assert items[f"{SYS}_raw_root_Now"].native_value == 1790000000


def test_plan_sensor_decodes_and_names_the_filtration_plan():
    items = dict(extract_perso_sensors(_coordinator(), SYS))
    plan = items[f"{SYS}_plan_255"]
    assert plan.name == "Filtration Schedule"
    assert plan.native_value is not None
    assert plan.available is True or plan.available is False  # property resolves


def test_alert_binary_sensor_unique_id_and_state():
    items = dict(extract_perso_binary_sensors(_coordinator(), SYS))
    assert list(items) == [f"{SYS}_alert_active"]
    assert items[f"{SYS}_alert_active"].is_on is False


def test_alert_binary_sensor_is_on_when_alerts_listed_even_if_count_is_zero():
    coord = _coordinator()
    coord.data[SYS].details.raw["alerts"] = [{"index": 0, "code": 29}]
    items = dict(extract_perso_binary_sensors(coord, SYS))
    assert items[f"{SYS}_alert_active"].is_on is True


def test_extra_attributes_and_device_extra():
    coord = _coordinator()
    assert probe_extra_attributes(coord, SYS, 0)["threshold_max"] == 40
    assert probe_extra_attributes(coord, SYS, 0)["calibration"] == [0.1, 0.2, 0.3]
    assert output_extra_attributes(coord, SYS, 0)["total_time"] == 42
    assert output_extra_attributes(coord, SYS, 0)["real_status"] == 1
    assert probe_extra_attributes(coord, SYS, 99) == {}
    assert device_extra(coord, SYS) == {"sw_version": "000A", "serial_number": "POD00012345"}


def test_probe_sensor_carries_the_extra_attributes_and_stable_unique_id():
    coord = _coordinator()
    probe = coord.data[SYS].details.probes[0]
    sensor = KlereoSensor(coord, SYS, probe)
    assert sensor.unique_id == f"{SYS}_sensor_0"
    assert sensor.extra_state_attributes["threshold_min"] == 1


def test_upstream_discovery_includes_the_perso_layer_and_keeps_upstream_ids():
    coord = _coordinator()
    uids = _uids(_extract_sensors(coord, SYS, coord.data[SYS].details))
    assert f"{SYS}_sensor_0" in uids  # upstream probe, same id as the fork's
    assert f"{SYS}_alerts" in uids  # upstream alert sensor
    assert f"{SYS}_raw_root_Now" in uids  # perso layer
    assert f"{SYS}_plan_255" in uids


def test_no_perso_entities_without_their_source_data():
    coord = _coordinator()
    coord.data[SYS].details.raw.clear()
    coord.data[SYS].info.raw.clear()
    uids = _uids(extract_perso_sensors(coord, SYS))
    assert not any("_plan_" in u or "_paraminfo_" in u for u in uids)
