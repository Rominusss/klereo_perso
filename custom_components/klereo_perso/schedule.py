"""Decode Klereo time-slot plans."""
from __future__ import annotations

import base64
import binascii
from typing import Any

SLOT_COUNT = 96
SLOT_MINUTES = 15
PLAN_FILTRATION = 255
PLAN_ECREMAGE = 18


def _slot_time(slot: int) -> str:
    """Return the HH:MM representation of a 15-minute slot."""
    if slot == SLOT_COUNT:
        return "00:00"
    minutes = slot * SLOT_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _ranges(values: list[int]) -> list[dict[str, Any]]:
    """Compress 96 slot values into contiguous ranges."""
    if not values:
        return []

    result: list[dict[str, Any]] = []
    start = 0
    current = values[0]

    for index in range(1, len(values) + 1):
        if index == len(values) or values[index] != current:
            result.append(
                {
                    "start": _slot_time(start),
                    "end": _slot_time(index),
                    "value": current,
                    "start_slot": start,
                    "end_slot_exclusive": index,
                }
            )
            if index < len(values):
                start = index
                current = values[index]

    return result


def _decode_12_bytes(raw: bytes, index: int) -> dict[str, Any]:
    """Decode a normal Klereo 12-byte / 96-slot plan.

    Klereo stores one boolean bit per 15-minute slot, LSB first in each byte.
    Plan 255 is special: bit 0 means filtration speed 1 and bit 1 means
    filtration speed 2, so its exposed values are 1/2 instead of 0/1.
    """
    bits = [(byte >> bit) & 1 for byte in raw for bit in range(8)]
    values = [bit + 1 for bit in bits] if index == PLAN_FILTRATION else bits
    decoded = {
        "format": "96-bit",
        "slot_count": SLOT_COUNT,
        "slot_minutes": SLOT_MINUTES,
        "slots": values,
        "ranges": _ranges(values),
        "active_slots": sum(bits),
    }
    if index == PLAN_FILTRATION:
        decoded["active_slots"] = SLOT_COUNT
        decoded["speed_1_slots"] = bits.count(0)
        decoded["speed_2_slots"] = bits.count(1)
    return decoded


def _decode_254(raw: bytes) -> dict[str, Any]:
    """Decode plan 254: the time-slot filtration plan.

    The payload is 36 bytes = 96 slots x 3 bits (little-endian bit stream, LSB first in
    each byte). The 3-bit value of a slot is the filtration speed: 0 = off, 1 = speed 1,
    2 = speed 2, ... Verified against the official Klereo app (speed 1 from 23:15 to 07:00
    decodes to slots 0-27 and 93-95 = 1). An earlier version of this decoder read the
    payload as three independent 96-bit masks, which is wrong.
    """
    bits = [(byte >> bit) & 1 for byte in raw for bit in range(8)]
    values = [
        bits[3 * i] | (bits[3 * i + 1] << 1) | (bits[3 * i + 2] << 2)
        for i in range(SLOT_COUNT)
    ]
    return {
        "format": "96x3-bit-speed",
        "slot_count": SLOT_COUNT,
        "slot_minutes": SLOT_MINUTES,
        "slots": values,
        "ranges": _ranges(values),
        "wrapped_ranges": _wrap_ranges(_ranges(values)),
        "active_slots": sum(1 for value in values if value),
        "speed_1_slots": values.count(1),
        "speed_2_slots": values.count(2),
        "speed_3_slots": values.count(3),
        "speed_4_slots": values.count(4),
        "speed_slots": {n: values.count(n) for n in range(1, 8) if n in values},
    }


def _wrap_ranges(ranges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge the last and first range when they are the same value across midnight.

    23:15-00:00 followed by 00:00-07:00 is one 23:15-07:00 run to a human.
    """
    if len(ranges) < 2 or ranges[0]["value"] != ranges[-1]["value"]:
        return ranges
    first, last = ranges[0], ranges[-1]
    merged = {
        "start": last["start"],
        "end": first["end"],
        "value": first["value"],
        "start_slot": last["start_slot"],
        "end_slot_exclusive": first["end_slot_exclusive"],
    }
    return [merged, *ranges[1:-1]]


def decode_plan(index: int, plan64: str) -> dict[str, Any] | None:
    """Decode one Klereo plan from its base64 representation."""
    if not plan64:
        return None

    try:
        raw = base64.b64decode(plan64, validate=True)
    except (binascii.Error, ValueError):
        return None

    if len(raw) == 12:
        decoded = _decode_12_bytes(raw, index)
    elif index == 254 and len(raw) == 36:
        decoded = _decode_254(raw)
    else:
        return {
            "format": f"unsupported-{len(raw)}-bytes",
            "raw_hex": raw.hex(" "),
            "byte_count": len(raw),
        }

    decoded.update(
        {
            "index": index,
            "plan64": plan64,
            "raw_hex": raw.hex(" "),
        }
    )
    return decoded


def schedule_text(decoded: dict[str, Any], index: int) -> str:
    """Create a compact human-readable representation for an HA state."""
    labels = decoded.get("wrapped_ranges") or decoded.get("ranges", [])
    if not labels:
        return ""

    if index == PLAN_FILTRATION:
        value_labels = {1: "V1", 2: "V2"}
    elif index == 254:
        # Speed 0 = off, any other value is a filtration speed (V1..V7, 3 bits).
        value_labels = {0: "OFF", **{n: f"V{n}" for n in range(1, 8)}}
    elif index == PLAN_ECREMAGE:
        value_labels = {0: "OFF", 1: "ON"}
    else:
        value_labels = {0: "OFF", 1: "ON"}

    return " | ".join(
        f"{value_labels.get(item['value'], str(item['value']))} "
        f"{item['start']}-{item['end']}"
        for item in labels
    )
