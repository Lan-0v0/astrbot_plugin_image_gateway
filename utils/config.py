from __future__ import annotations

from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    return default


def parse_int(value: Any, default: int) -> int:
    if value in (None, "") or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def parse_float(value: Any, default: float) -> float:
    if value in (None, "") or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def parse_positive_int(value: Any, default: int) -> int:
    parsed_value = parse_int(value, default)
    return parsed_value if parsed_value > 0 else default


def parse_positive_float(value: Any, default: float) -> float:
    parsed_value = parse_float(value, default)
    return parsed_value if parsed_value > 0 else default
