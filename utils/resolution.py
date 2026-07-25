from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..adapters.base import ModelConfig

# Practical pixel bounds for image generation APIs.
_MIN_DIM = 64
_MAX_DIM = 8192

# Separators commonly used between width and height.
_SEP = r"(?:x|X|×|✕|╳|\*|＊|✖|乘|乘以)"

# Bare or lightly labeled WxH pairs, e.g. 1024x1024 / 1024*1024 / 1024×768分辨率
_PAIR_PATTERN = re.compile(
    rf"(?P<w>\d{{2,5}})\s*{_SEP}\s*(?P<h>\d{{2,5}})"
    rf"(?:\s*(?:px|像素|分辨率|尺寸|大小|size|resolution))?",
    re.IGNORECASE,
)

# Keyword first, then pair: 分辨率1024x1024 / size: 1024*768 / 尺寸为 512 x 512
_KEYWORD_PAIR_PATTERN = re.compile(
    rf"(?:分辨率|尺寸|大小|画幅|宽高|像素|resolution|size|dimension|dimensions)"
    rf"\s*[:：=为是]?\s*"
    rf"(?P<w>\d{{2,5}})\s*{_SEP}\s*(?P<h>\d{{2,5}})",
    re.IGNORECASE,
)

# Split Chinese width/height: 宽1024高768 / 宽度 1024 高度 768
_CN_WH_PATTERN = re.compile(
    r"(?:宽(?:度)?|宽度)\s*[:：=]?\s*(?P<w>\d{2,5})\s*"
    r"(?:高(?:度)?|高度)\s*[:：=]?\s*(?P<h>\d{2,5})",
    re.IGNORECASE,
)

# Split English width/height: width:1024 height:768 / w=1024,h=768
_EN_WH_PATTERN = re.compile(
    r"(?:width|w)\s*[:：=]?\s*(?P<w>\d{2,5})\s*[,，/\s]+"
    r"(?:height|h)\s*[:：=]?\s*(?P<h>\d{2,5})",
    re.IGNORECASE,
)

# Reverse order: height 768 width 1024 / 高768宽1024
_EN_HW_PATTERN = re.compile(
    r"(?:height|h)\s*[:：=]?\s*(?P<h>\d{2,5})\s*[,，/\s]+"
    r"(?:width|w)\s*[:：=]?\s*(?P<w>\d{2,5})",
    re.IGNORECASE,
)
_CN_HW_PATTERN = re.compile(
    r"(?:高(?:度)?|高度)\s*[:：=]?\s*(?P<h>\d{2,5})\s*"
    r"(?:宽(?:度)?|宽度)\s*[:：=]?\s*(?P<w>\d{2,5})",
    re.IGNORECASE,
)

# Square shorthand with keyword: 1024分辨率 / 分辨率1024 / size 1024
_SQUARE_KEYWORD_PATTERN = re.compile(
    r"(?:"
    r"(?P<n1>\d{2,5})\s*(?:px|像素)?\s*(?:分辨率|尺寸|大小|画幅)"
    r"|"
    r"(?:分辨率|尺寸|大小|画幅|resolution|size)\s*[:：=为是]?\s*(?P<n2>\d{2,5})"
    r"(?:\s*(?:px|像素))?"
    r")",
    re.IGNORECASE,
)

_PATTERNS: tuple[re.Pattern[str], ...] = (
    _KEYWORD_PAIR_PATTERN,
    _CN_WH_PATTERN,
    _CN_HW_PATTERN,
    _EN_WH_PATTERN,
    _EN_HW_PATTERN,
    _PAIR_PATTERN,
)

_NONE_PATTERN = re.compile(
    r"^(?:none|null|nil|n/a|na|no|false|无|没有|未指定|不需要|不要求|无要求|未知)[.。!！?？]*$",
    re.IGNORECASE,
)

_LLM_PAIR_PATTERN = re.compile(
    rf"(?P<w>\d{{2,5}})\s*{_SEP}\s*(?P<h>\d{{2,5}})",
    re.IGNORECASE,
)


def _valid_dimension(value: int) -> bool:
    return _MIN_DIM <= value <= _MAX_DIM


def _format_size(width: int, height: int) -> str | None:
    if not (_valid_dimension(width) and _valid_dimension(height)):
        return None
    return f"{width}x{height}"


def _pair_from_match(match: re.Match[str]) -> str | None:
    try:
        width = int(match.group("w"))
        height = int(match.group("h"))
    except (IndexError, TypeError, ValueError):
        return None
    return _format_size(width, height)


def parse_resolution_from_prompt(prompt: str) -> str | None:
    """Extract an explicit output resolution from free-form prompt text.

    Returns a canonical ``WIDTHxHEIGHT`` string when a resolution request is
    detected; otherwise ``None`` so callers can keep the model ``size=auto``
    behavior unchanged.

    This is a deterministic fast path for common spellings. Ambiguous or
    natural-language requests should be handled by an LLM and then passed
    through :func:`normalize_resolution_value`.
    """
    text = str(prompt or "").strip()
    if not text:
        return None

    # Prefer more explicit keyword / labeled forms first.
    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            resolved = _pair_from_match(match)
            if resolved:
                return resolved

    for match in _SQUARE_KEYWORD_PATTERN.finditer(text):
        raw = match.group("n1") or match.group("n2")
        if not raw:
            continue
        try:
            side = int(raw)
        except ValueError:
            continue
        resolved = _format_size(side, side)
        if resolved:
            return resolved

    return None


def normalize_resolution_value(raw: str | None) -> str | None:
    """Normalize model/user free text into ``WIDTHxHEIGHT`` or ``None``."""
    text = str(raw or "").strip()
    if not text:
        return None

    # Strip common wrapping noise from LLM replies.
    text = text.strip("`\"' \t\r\n")
    text = re.sub(r"^(?:答案|结果|输出|resolution|size)\s*[:：=]\s*", "", text, flags=re.IGNORECASE)
    text = text.strip()
    if not text:
        return None

    first_line = text.splitlines()[0].strip().strip("`\"'")
    if _NONE_PATTERN.fullmatch(first_line):
        return None

    match = _LLM_PAIR_PATTERN.search(first_line) or _LLM_PAIR_PATTERN.search(text)
    if not match:
        # Square-only digit reply, e.g. "1024"
        if first_line.isdigit():
            return _format_size(int(first_line), int(first_line))
        return None
    return _pair_from_match(match)


def apply_prompt_resolution_if_auto(
    model: ModelConfig,
    prompt: str,
    *,
    size_override: str | None = None,
) -> ModelConfig:
    """When model size is ``auto``, apply an explicit resolution if available.

    ``size_override`` is preferred (regex/LLM pre-resolution from the request
    layer). If absent, fall back to deterministic prompt parsing.
    """
    current = str(getattr(model, "size", "") or "auto").strip()
    if current.lower() != "auto":
        return model

    resolved = normalize_resolution_value(size_override) if size_override else None
    if not resolved:
        resolved = parse_resolution_from_prompt(prompt)
    if not resolved:
        return model

    return replace(model, size=resolved)
