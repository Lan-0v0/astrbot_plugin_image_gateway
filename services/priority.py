from __future__ import annotations

from typing import Any


PRIORITY_PRESET_VALUES = {
    "highest": 1000,
    "high": 300,
    "normal": 100,
    "low": 0,
    "lowest": -100,
}


def resolve_priority_value(entry: dict[str, Any], *, default_priority: int = 10) -> int:
    raw_priority_preset = str(entry.get("priority_preset") or "").strip().lower()

    if raw_priority_preset in PRIORITY_PRESET_VALUES:
        return PRIORITY_PRESET_VALUES[raw_priority_preset]

    if raw_priority_preset == "custom":
        return int(entry.get("priority") or default_priority)

    raw_priority = entry.get("priority")
    if raw_priority not in (None, ""):
        return int(raw_priority)

    return default_priority
