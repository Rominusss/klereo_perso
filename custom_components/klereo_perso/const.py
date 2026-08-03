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
# counters, pool volume, configured limits, etc. — previously never read by
# the integration). "diagnostic": True puts the entity in the Diagnostic
# section of the device page (hidden from the main dashboard by default)
# instead of cluttering the main entity list.
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
    # Configured bounds/limits — diagnostic (mirror the min/max already used
    # dynamically by the number entities, but exposed for visibility).
    "EauMin": {"name": "Water Temp Min Bound", "unit": "°C", "diagnostic": True},
    "EauMax": {"name": "Water Temp Max Bound", "unit": "°C", "diagnostic": True},
    "pHMin": {"name": "pH Min Bound", "unit": None, "diagnostic": True},
    "pHMax": {"name": "pH Max Bound", "unit": None, "diagnostic": True},
    "OrpMin": {"name": "Redox Min Bound", "unit": "mV", "diagnostic": True},
    "OrpMax": {"name": "Redox Max Bound", "unit": "mV", "diagnostic": True},
    "AirMin": {"name": "Air Temp Min Bound", "unit": "°C", "diagnostic": True},
    "AirMax": {"name": "Air Temp Max Bound", "unit": "°C", "diagnostic": True},
    "PressureMin": {"name": "Filter Pressure Min Bound", "unit": "mbar", "diagnostic": True},
    "PressureMax": {"name": "Filter Pressure Max Bound", "unit": "mbar", "diagnostic": True},
    "ChlMin": {"name": "Chlorine Min Bound", "unit": "mg/L", "diagnostic": True},
    "ChlMax": {"name": "Chlorine Max Bound", "unit": "mg/L", "diagnostic": True},
    "MaxFilterTime": {"name": "Max Filtration Time Setting", "unit": None, "diagnostic": True},
    "CleanFilter": {"name": "Filter Cleaning Threshold", "unit": "mbar", "diagnostic": True},
    "SeuilHorsGel": {"name": "Frost Protection Threshold", "unit": "°C", "diagnostic": True},
    "VolumePH_PerDay": {"name": "pH- Max Daily Volume", "unit": "mL", "diagnostic": True},
    "VolumeTrait_PerDay": {"name": "Disinfectant Max Daily Volume", "unit": "mL", "diagnostic": True},
    "VolumeFloc_PerDay": {"name": "Flocculant Max Daily Volume", "unit": "mL", "diagnostic": True},
    "PHMinus_MaxDay": {"name": "pH- Max Daily Dosing Time", "unit": "s", "diagnostic": True},
    "ElectroChlore_MaxDay": {"name": "Chlorinator Max Daily Runtime", "unit": "s", "diagnostic": True},
    "HeatControlTime": {"name": "Heating Control Time", "unit": None, "diagnostic": True},
}

# Variable-speed pump telemetry, sourced from details["ExtraParams"].
PUMP_TELEMETRY_SENSORS = {
    "PmpWatts": {"name": "Pump Power", "unit": "W", "device_class": "power", "state_class": "measurement"},
    "PmpFlow": {"name": "Pump Flow", "unit": "m³/h", "device_class": None, "state_class": "measurement"},
    "PmpSpeed": {"name": "Pump Speed", "unit": "%", "device_class": None, "state_class": "measurement"},
    "PmpRPM": {"name": "Pump RPM", "unit": "rpm", "device_class": None, "state_class": "measurement"},
}

# Salt-water chlorinator cell telemetry, sourced from details["ExtraParams"].
# All-zero on installations without a salt cell — entities are still created
# (they'll just read 0) since we can't reliably detect cell presence.
CELL_TELEMETRY_SENSORS = {
    "CellVoltage": {"name": "Chlorinator Cell Voltage", "unit": "V", "device_class": "voltage", "diagnostic": True},
    "CellIntensity": {"name": "Chlorinator Cell Current", "unit": "A", "device_class": "current", "diagnostic": True},
    "CellLifetimeNormal": {"name": "Chlorinator Cell Lifetime (Normal)", "unit": "h", "diagnostic": True},
    "CellLifetimeReverse": {"name": "Chlorinator Cell Lifetime (Reverse)", "unit": "h", "diagnostic": True},
}

# Top-level installation/connectivity fields from details (not nested under
# probes/outs/params/ExtraParams). All diagnostic: useful for troubleshooting
# rather than day-to-day monitoring.
SYSTEM_DIAGNOSTIC_SENSORS = {
    "lastPing": {"name": "Last Ping", "unit": "s"},
    "infosTime": {"name": "Info Age", "unit": "s"},
    "rfSent": {"name": "RF Frames Sent", "unit": None},
    "rfErr": {"name": "RF Frame Errors", "unit": None},
    "PumpMaxSpeed": {"name": "Pump Max Speed Setting", "unit": None},
}

# Fields kept outside the "diagnostic" bucket because they're useful at a
# glance rather than just for troubleshooting.
SYSTEM_SENSORS = {
    "HorsGel": {"name": "Frost Protection Level", "unit": None},
}

# Pod connectivity telemetry, sourced from details["podinfo"].
PODINFO_SENSORS = {
    "pingSent": {"name": "Pod Pings Sent", "unit": None, "diagnostic": True},
    "pongRx": {"name": "Pod Pings Acknowledged", "unit": None, "diagnostic": True},
    "pingFail": {"name": "Pod Ping Failures", "unit": None, "diagnostic": True},
}
