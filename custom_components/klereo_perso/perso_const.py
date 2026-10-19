"""Constants for the perso layer (entities that exist only in this fork).

Kept out of const.py so that merging a new upstream release never conflicts with them.
"""

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
