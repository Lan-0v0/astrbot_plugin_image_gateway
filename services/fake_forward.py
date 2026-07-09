from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FakeForwardMode(str, Enum):
    OFF = "off"
    BOT_SELF = "bot_self"
    REQUESTER = "requester"
    CUSTOM_QQ = "custom_qq"


FOLLOW_GLOBAL = "follow_global"

DEFAULT_GLOBAL_FAKE_FORWARD_MODE = FakeForwardMode.OFF

_VALID_GLOBAL_MODE_VALUES = {mode.value for mode in FakeForwardMode}
_VALID_ENTRY_MODE_VALUES = _VALID_GLOBAL_MODE_VALUES | {FOLLOW_GLOBAL}


@dataclass(slots=True)
class FakeForwardConfig:
    mode: str = FakeForwardMode.OFF.value
    custom_qq: str = ""

    @property
    def enabled(self) -> bool:
        return self.mode != FakeForwardMode.OFF.value


def parse_global_fake_forward(raw_value: Any) -> FakeForwardConfig:
    config_dict = raw_value if isinstance(raw_value, dict) else {}

    normalized_mode = str(
        config_dict.get("mode") or DEFAULT_GLOBAL_FAKE_FORWARD_MODE.value
    ).strip().lower()
    if normalized_mode not in _VALID_GLOBAL_MODE_VALUES:
        normalized_mode = DEFAULT_GLOBAL_FAKE_FORWARD_MODE.value

    custom_qq = _normalize_qq(config_dict.get("custom_qq"))
    if normalized_mode != FakeForwardMode.CUSTOM_QQ.value:
        custom_qq = ""

    return FakeForwardConfig(mode=normalized_mode, custom_qq=custom_qq)


def parse_entry_fake_forward_mode(raw_value: Any) -> str:
    normalized_mode = str(raw_value or FOLLOW_GLOBAL).strip().lower()
    if normalized_mode not in _VALID_ENTRY_MODE_VALUES:
        return FOLLOW_GLOBAL
    return normalized_mode


def resolve_effective_fake_forward(
    *,
    global_config: FakeForwardConfig,
    entry_mode: str,
    entry_custom_qq: str,
) -> FakeForwardConfig:
    if entry_mode == FOLLOW_GLOBAL:
        return FakeForwardConfig(
            mode=global_config.mode,
            custom_qq=global_config.custom_qq,
        )

    if entry_mode not in _VALID_GLOBAL_MODE_VALUES:
        return FakeForwardConfig(
            mode=global_config.mode,
            custom_qq=global_config.custom_qq,
        )

    custom_qq = _normalize_qq(entry_custom_qq)
    if entry_mode == FakeForwardMode.CUSTOM_QQ.value and not custom_qq:
        return FakeForwardConfig()

    return FakeForwardConfig(
        mode=entry_mode,
        custom_qq=(custom_qq if entry_mode == FakeForwardMode.CUSTOM_QQ.value else ""),
    )


def normalize_custom_qq(raw_value: Any) -> str:
    return _normalize_qq(raw_value)


def _normalize_qq(raw_value: Any) -> str:
    return "".join(ch for ch in str(raw_value or "").strip() if ch.isdigit())
