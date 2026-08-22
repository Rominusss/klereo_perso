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
    """Decode plan 254 as its three independent 96-bit masks.

    The API payload contains 36 bytes. The semantics of the three masks are
    not identified by the API, so they are intentionally exposed as mask_0,
    mask_1 and mask_2 rather than assigning undocumented names.
    """
    masks = []
    for mask_index in range(3):
        mask_raw = raw[mask_index * 12 : (mask_index + 1) * 12]
        bits = [(byte >> bit) & 1 for byte in mask_raw for bit in range(8)]
        masks.append(
            {
                "mask_index": mask_index,
                "slots": bits,
                "ranges": _ranges(bits),
                "active_slots": sum(bits),
                "raw_hex": mask_raw.hex(" "),
            }
        )

    return {
        "format": "3x96-bit-masks",
        "slot_count": SLOT_COUNT,
        "slot_minutes": SLOT_MINUTES,
        "masks": masks,
        "active_slots": sum(mask["active_slots"] for mask in masks),
    }


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
    if index == 254:
        return " | ".join(
            f"Mask {mask['mask_index']}: {mask['active_slots']} active slots"
            for mask in decoded.get("masks", [])
        )

    labels = decoded.get("ranges", [])
    if not labels:
        return ""

    if index == PLAN_FILTRATION:
        value_labels = {1: "V1", 2: "V2"}
    elif index == PLAN_ECREMAGE:
        value_labels = {0: "OFF", 1: "ON"}
    else:
        value_labels = {0: "OFF", 1: "ON"}

    return " | ".join(
        f"{value_labels.get(item['value'], str(item['value']))} "
        f"{item['start']}-{item['end']}"
        for item in labels
    )
