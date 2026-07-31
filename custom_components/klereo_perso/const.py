"""Constants for the Klereo integration."""
import hashlib

DOMAIN = "klereo_perso"


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password with SHA-1 for the Klereo API."""
    return hashlib.sha1(plaintext.encode("utf-8")).hexdigest()

# Default update interval
SCAN_INTERVAL_MINUTES = 5

# Probe type to sensor metadata mapping (from Jeedom _PROBE_TYPE_* constants)
# state_class: "measurement" for continuous readings, None for positional/unknown values
SENSOR_TYPES = {
    0: {
        "name": "Technical Room Temperature", "unit": "°C",
        "device_class": "temperature", "state_class": "measurement",
    },
    1: {"name": "Air Temperature", "unit": "°C", "device_class": "temperature", "state_class": "measurement"},
    2: {"name": "Water Level", "unit": "%", "device_class": None, "state_class": "measurement"},
    3: {"name": "pH", "unit": None, "device_class": None, "state_class": "measurement"},
    4: {"name": "Redox", "unit": "mV", "device_class": "voltage", "state_class": "measurement"},
    5: {"name": "Water Temperature", "unit": "°C", "device_class": "temperature", "state_class": "measurement"},
    6: {"name": "Filter Pressure", "unit": "mbar", "device_class": "pressure", "state_class": "measurement"},
    10: {"name": "Generic", "unit": "%", "device_class": None, "state_class": None},
    11: {"name": "Flow", "unit": "m³/h", "device_class": None, "state_class": "measurement"},
    12: {"name": "Container Level", "unit": "%", "device_class": None, "state_class": "measurement"},
    13: {"name": "Cover Position", "unit": "%", "device_class": None, "state_class": None},
    14: {"name": "Chlorine", "unit": "mg/L", "device_class": None, "state_class": "measurement"},
}

OUTPUT_NAMES = {
    0: "Lighting",
    1: "Filtration",
    2: "pH Corrector",
    3: "Disinfectant",
    4: "Heating",
    5: "Aux 1",
    6: "Aux 2",
    7: "Aux 3",
    8: "Flocculant",
    9: "Aux 4",
    10: "Aux 5",
    11: "Aux 6",
    12: "Aux 7",
    13: "Aux 8",
    14: "Aux 9",
    15: "Hybrid Disinfectant",
}

# Friendly names for RegulModes keys exposed as read-only param sensors.
# Keys in PARAM_TYPES are excluded (they become number entities instead).
#
# NOTE: the content of "RegulModes" differs across firmware/API versions.
# Older/newer payloads have been observed with either naming scheme below,
# so both are kept for compatibility. Real-world diagnostics (2026-07) show
# {"PoolMode", "TraitMode", "pHMode", "HeaterMode"} rather than the
# "ModeFiltration"/"ModeRegulPH"/... names originally assumed.
PARAM_NAMES = {
    # Observed on 2026-07 firmware (390-series pods)
    "PoolMode": "Filtration Mode",
    "TraitMode": "Disinfection Mode",
    "pHMode": "pH Regulation Mode",
    "HeaterMode": "Heater Mode",
    # Names assumed from the original Jeedom plugin / older firmware
    "ModeFiltration": "Filtration Mode",
    "ModeRegulPH": "pH Regulation Mode",
    "ModeRegulRedox": "Redox Regulation Mode",
    "ModeRegulChlore": "Chlorine Regulation Mode",
    "ModeRegulTemp": "Temperature Regulation Mode",
    "DureeTimerFiltration": "Filtration Timer Duration",
}

# Writable setpoints. On current firmware these live under details["params"],
# not details["RegulModes"] as previously assumed — the water setpoint number
# entity was silently never created because of this mismatch.
# "min_key"/"max_key" let us read the *actual* configured bounds for this
# installation from details["params"] (e.g. "pHMin"/"pHMax"); if absent, the
# static "min"/"max" below are used as a fallback.
PARAM_TYPES = {
    "ConsigneEau": {
        "name": "Water Setpoint", "unit": "°C",
        "min": 10, "max": 40, "step": 0.5,
        "min_key": "EauMin", "max_key": "EauMax",
    },
    "ConsignePH": {
        "name": "pH Setpoint", "unit": None,
        "min": 6.5, "max": 8.0, "step": 0.1,
        "min_key": "pHMin", "max_key": "pHMax",
    },
    "ConsigneRedox": {
        "name": "Redox Setpoint", "unit": "mV",
        "min": 400, "max": 900, "step": 5,
        "min_key": "OrpMin", "max_key": "OrpMax",
    },
    "ConsigneChlore": {
        "name": "Chlorine Setpoint", "unit": "mg/L",
        "min": 0, "max": 5, "step": 0.1,
        "min_key": None, "max_key": None,
    },
}

# Read-only informational sensors sourced from details["params"] (runtime
# counters, pool volume, etc. — previously never read by the integration).
PARAM_INFO_SENSORS = {
    "VolumeEau": {"name": "Pool Volume", "unit": "m³", "device_class": None, "state_class": None},
    "DebitPompe": {"name": "Nominal Pump Flow", "unit": "m³/h", "device_class": None, "state_class": None},
    "Filtration_TotalTime": {
        "name": "Filtration Total Runtime", "unit": "s",
        "device_class": "duration", "state_class": "total_increasing",
    },
    "Filtration_TodayTime": {
        "name": "Filtration Runtime Today", "unit": "s",
        "device_class": "duration", "state_class": "total_increasing",
    },
    "PHMinus_TotalTime": {
        "name": "pH- Dosing Total Time", "unit": "s",
        "device_class": "duration", "state_class": "total_increasing",
    },
    "PHMinus_TodayTime": {
        "name": "pH- Dosing Time Today", "unit": "s",
        "device_class": "duration", "state_class": "total_increasing",
    },
    "ElectroChlore_TotalTime": {
        "name": "Chlorinator Total Runtime", "unit": "s",
        "device_class": "duration", "state_class": "total_increasing",
    },
    "ElectroChlore_TodayTime": {
        "name": "Chlorinator Runtime Today", "unit": "s",
        "device_class": "duration", "state_class": "total_increasing",
    },
}

# Variable-speed pump telemetry, sourced from details["ExtraParams"].
PUMP_TELEMETRY_SENSORS = {
    "PmpWatts": {"name": "Pump Power", "unit": "W", "device_class": "power", "state_class": "measurement"},
    "PmpFlow": {"name": "Pump Flow", "unit": "m³/h", "device_class": None, "state_class": "measurement"},
    "PmpSpeed": {"name": "Pump Speed", "unit": "%", "device_class": None, "state_class": "measurement"},
    "PmpRPM": {"name": "Pump RPM", "unit": "rpm", "device_class": None, "state_class": "measurement"},
}
