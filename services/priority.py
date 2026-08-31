from __future__ import annotations

import random
from typing import Any, Protocol, TypeVar

from ..utils.config import parse_int

# Every entry (API model or workflow) carries a single numeric priority.
# Larger wins; ``0`` opts the entry into the randomized group.
DEFAULT_PRIORITY = 1
RANDOM_PRIORITY = 0

# ``priority_preset`` was removed from the dashboard in v2.1.8. Legacy configs are
# migrated onto the numeric scale the old panel documented (最高=40 … 低=10), so a
# preset entry keeps its documented ordering against hand-typed custom values.
# ``lowest`` lands on 1 instead of 0 because 0 now means "random".
LEGACY_PRESET_PRIORITY_VALUES = {
    "highest": 40,
    "high": 30,
    "normal": 20,
    "low": 10,
    "lowest": 1,
}

# The old panel shipped the custom number box with this default. A stored value
# that differs from it is one the user typed on purpose, so migration keeps it
# even when the preset radio was never switched to "自定义数值".
LEGACY_CUSTOM_PRIORITY_DEFAULT = 10


class _HasPriority(Protocol):
    priority: int


TargetT = TypeVar("TargetT", bound=_HasPriority)


def normalize_priority_value(value: Any, *, default_priority: int = DEFAULT_PRIORITY) -> int:
    """Coerce a raw panel value into a priority number, clamping below 0 to random."""
    return max(RANDOM_PRIORITY, parse_int(value, default_priority))


def resolve_priority_value(
    entry: dict[str, Any],
    *,
    default_priority: int = DEFAULT_PRIORITY,
) -> int:
    """Resolve an entry's priority from the numeric field, honoring legacy presets.

    The numeric ``priority`` field always wins so a config the user has already
    migrated never falls back to a stale ``priority_preset`` left in the file.
    """
    raw_priority = entry.get("priority")
    if raw_priority not in (None, ""):
        return normalize_priority_value(raw_priority, default_priority=default_priority)

    legacy_preset = str(entry.get("priority_preset") or "").strip().lower()
    if legacy_preset in LEGACY_PRESET_PRIORITY_VALUES:
        return LEGACY_PRESET_PRIORITY_VALUES[legacy_preset]

    return max(RANDOM_PRIORITY, default_priority)


def is_random_priority(priority: int) -> bool:
    """Whether the entry joins the randomly ordered group."""
    return priority <= RANDOM_PRIORITY


def migrate_priority_entry(entry: dict[str, Any]) -> bool:
    """Rewrite a stored entry onto the numeric priority field in place.

    Returns ``True`` when the entry changed, so the caller can persist the config
    once instead of re-migrating on every request.
    """
    if not isinstance(entry, dict):
        return False

    if "priority_preset" not in entry:
        normalized_priority = resolve_priority_value(entry)
        if entry.get("priority") == normalized_priority:
            return False
        entry["priority"] = normalized_priority
        return True

    legacy_preset = str(entry.pop("priority_preset") or "").strip().lower()
    raw_priority = entry.get("priority")
    typed_priority = (
        None
        if raw_priority in (None, "")
        else normalize_priority_value(raw_priority)
    )

    if legacy_preset == "custom" and typed_priority is not None:
        # The number box was visible and authoritative.
        entry["priority"] = typed_priority
    elif (
        typed_priority is not None
        and typed_priority != LEGACY_CUSTOM_PRIORITY_DEFAULT
    ):
        # The v2.1.7 panel hid this box behind the radio, so a value that differs
        # from its default is what the user actually meant — honor it instead of
        # the preset that silently overrode it.
        entry["priority"] = typed_priority
    elif legacy_preset in LEGACY_PRESET_PRIORITY_VALUES:
        entry["priority"] = LEGACY_PRESET_PRIORITY_VALUES[legacy_preset]
    else:
        entry["priority"] = typed_priority if typed_priority is not None else DEFAULT_PRIORITY
    return True


def sort_targets_by_priority(
    targets: list[TargetT],
    *,
    randomize: bool = False,
) -> list[TargetT]:
    """Order every target by priority, highest first, across models and workflows.

    Models and workflows compete in one pool, so a high-priority workflow always
    outranks a lower-priority API model. Ties keep their configured order, which
    keeps the panel listing stable and reproducible.

    Entries at priority ``0`` form the random group: they are shuffled and placed
    after all ranked entries, so ``0`` everywhere means "pick a target at random"
    while a mix keeps ranked entries as the deterministic front of the chain.
    """
    ranked_targets = [target for target in targets if not is_random_priority(target.priority)]
    random_targets = [target for target in targets if is_random_priority(target.priority)]

    ranked_targets.sort(key=lambda target: target.priority, reverse=True)
    if randomize and len(random_targets) > 1:
        random_targets = random.sample(random_targets, len(random_targets))

    return ranked_targets + random_targets
