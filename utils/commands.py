from __future__ import annotations

import re
from typing import Any


RESERVED_COMMANDS = {"生图", "改图"}
_COMMAND_PATTERN = re.compile(
    r"^(?:/|／)?\s*(?P<command>[^\s，,、:：;；。.!！？?]+)"
    r"(?:\s+|[，,、:：;；。.!！？?]+)?(?P<prompt>.*)$"
)


def normalize_dedicated_command(raw_value: Any) -> str:
    command = str(raw_value or "").strip()
    command = command.lstrip("/／").strip()
    if (
        not command
        or command in RESERVED_COMMANDS
        or re.search(r"\s|[，,、:：;；。.!！？?]", command)
    ):
        return ""
    return command


def parse_dedicated_command_text(text: str) -> tuple[str, str]:
    match = _COMMAND_PATTERN.match(str(text or "").strip())
    if not match:
        return "", ""
    return match.group("command"), match.group("prompt").strip()
