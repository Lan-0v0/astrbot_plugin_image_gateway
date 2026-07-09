from __future__ import annotations

from enum import Enum
from typing import Any


class SendStrategy(str, Enum):
    """Ordered list of delivery channels attempted before the result pipeline.

    ``DIRECT_FIRST`` is the recommended default and mirrors the plugin's
    historical behaviour. Change this when a generation succeeds but the
    resulting image fails to reach the user.
    """

    DIRECT_FIRST = "direct_first"
    EVENT_SEND_FIRST = "event_send_first"
    CONTEXT_SEND_FIRST = "context_send_first"
    PLATFORM_CLIENT_FIRST = "platform_client_first"
    RESULT_PIPELINE_ONLY = "result_pipeline_only"


FOLLOW_GLOBAL = "follow_global"

DEFAULT_GLOBAL_SEND_STRATEGY = SendStrategy.DIRECT_FIRST

_VALID_STRATEGY_VALUES = {strategy.value for strategy in SendStrategy}

_DELIVERY_SENDER_ORDER_BY_STRATEGY: dict[SendStrategy, list[str]] = {
    SendStrategy.DIRECT_FIRST: ["event_send", "context_send_message", "platform_client"],
    SendStrategy.EVENT_SEND_FIRST: ["event_send"],
    SendStrategy.CONTEXT_SEND_FIRST: ["context_send_message"],
    SendStrategy.PLATFORM_CLIENT_FIRST: ["platform_client"],
    SendStrategy.RESULT_PIPELINE_ONLY: [],
}

_START_MESSAGE_SENDER_ORDER_BY_STRATEGY: dict[SendStrategy, list[str]] = {
    # 开始提示需要尽量拿到 message_id 才能在生成完成后撤回，
    # 因此 direct_first 下优先尝试 platform_client。
    SendStrategy.DIRECT_FIRST: ["platform_client", "event_send", "context_send_message"],
    SendStrategy.EVENT_SEND_FIRST: ["event_send"],
    SendStrategy.CONTEXT_SEND_FIRST: ["context_send_message"],
    SendStrategy.PLATFORM_CLIENT_FIRST: ["platform_client"],
    SendStrategy.RESULT_PIPELINE_ONLY: [],
}


def parse_global_send_strategy(raw_value: Any) -> SendStrategy:
    """Parse the plugin-wide default send strategy, falling back to direct_first."""
    normalized_value = str(raw_value or DEFAULT_GLOBAL_SEND_STRATEGY.value).strip().lower()
    if normalized_value not in _VALID_STRATEGY_VALUES:
        return DEFAULT_GLOBAL_SEND_STRATEGY
    return SendStrategy(normalized_value)


def parse_entry_send_strategy(raw_value: Any) -> str:
    """Parse a per-model/per-workflow send strategy override.

    Returns either ``follow_global`` or one of the ``SendStrategy`` values.
    """
    normalized_value = str(raw_value or FOLLOW_GLOBAL).strip().lower()
    if normalized_value == FOLLOW_GLOBAL:
        return FOLLOW_GLOBAL
    if normalized_value not in _VALID_STRATEGY_VALUES:
        return FOLLOW_GLOBAL
    return normalized_value


def resolve_effective_send_strategy(
    *,
    global_strategy: SendStrategy,
    entry_strategy: str,
) -> SendStrategy:
    """Resolve an entry's effective strategy, honoring the global default."""
    if entry_strategy == FOLLOW_GLOBAL:
        return global_strategy
    if entry_strategy not in _VALID_STRATEGY_VALUES:
        return global_strategy
    return SendStrategy(entry_strategy)


def get_sender_order(strategy: SendStrategy, *, for_start_message: bool = False) -> list[str]:
    """Return the ordered list of direct-send channels to attempt.

    An empty list means the result pipeline should be used immediately,
    which is what ``RESULT_PIPELINE_ONLY`` requests.
    """
    table = _START_MESSAGE_SENDER_ORDER_BY_STRATEGY if for_start_message else _DELIVERY_SENDER_ORDER_BY_STRATEGY
    return list(table.get(strategy, _DELIVERY_SENDER_ORDER_BY_STRATEGY[SendStrategy.DIRECT_FIRST]))
