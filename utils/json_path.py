from __future__ import annotations

from typing import Any


def get_by_dot_path(data: Any, field_path: str) -> Any:
    """Read a value from nested dict/list data using a dot-separated path.

    Supports both dict keys and list indices, e.g. ``inputs.text`` or
    ``inputs.texts.0``.
    """
    current = data
    for segment in _split_dot_path(field_path):
        current = _get_segment(current, segment)
    return current


def set_by_dot_path(data: Any, field_path: str, value: Any) -> None:
    """Overwrite a value in nested dict/list data using a dot-separated path.

    The parent container addressed by all but the last path segment must
    already exist; only the final segment's value is replaced in place.
    """
    segments = _split_dot_path(field_path)
    parent = data
    for segment in segments[:-1]:
        parent = _get_segment(parent, segment)

    last_segment = segments[-1]

    if isinstance(parent, list):
        index = _parse_index(last_segment)
        if index >= len(parent):
            raise IndexError(f"列表索引超出范围: {last_segment}")
        parent[index] = value
        return

    if isinstance(parent, dict):
        if last_segment not in parent:
            raise KeyError(f"字段不存在，无法覆盖: {last_segment}")
        parent[last_segment] = value
        return

    raise TypeError(f"无法在类型 {type(parent).__name__} 上设置字段 {last_segment}")


def _split_dot_path(field_path: str) -> list[str]:
    normalized_path = (field_path or "").strip()
    if not normalized_path:
        raise KeyError("字段路径不能为空")
    return normalized_path.split(".")


def _get_segment(current: Any, segment: str) -> Any:
    if isinstance(current, list):
        index = _parse_index(segment)
        if index >= len(current):
            raise IndexError(f"列表索引超出范围: {segment}")
        return current[index]

    if isinstance(current, dict):
        if segment not in current:
            raise KeyError(f"字段不存在: {segment}")
        return current[segment]

    raise TypeError(f"无法在类型 {type(current).__name__} 上访问字段 {segment}")


def _parse_index(segment: str) -> int:
    try:
        return int(segment)
    except ValueError as exc:
        raise KeyError(f"无效的列表索引: {segment}") from exc
