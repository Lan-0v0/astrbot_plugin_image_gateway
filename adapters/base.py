from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, NoReturn

from ..utils.commands import normalize_dedicated_command
from ..utils.config import parse_bool, parse_int

Mode = Literal["text_to_image", "image_to_image"]

# Content/safety signals. Avoid bare tokens like "安全"/"harm"/"moderation"
# (the latter also appears in "Unknown parameter: moderation").
_SAFETY_ERROR_PATTERN = re.compile(
    r"content[_\s-]?(?:policy|moderation|filter)|"
    r"moderation[_\s-]?(?:error|failed|filter|check|block|rejected)|"
    r"safety[_\s-]?(?:filter|setting|system|check|block|violation)|"
    r"blocked due to safety|"
    r"sensitive(?:\s+content)?|"
    r"sexually[_\s-]?explicit|"
    r"inappropriate|"
    r"prohibited[_\s-]?content|"
    r"image[_\s-]?safety|"
    r"blockreason|"
    r"promptfeedback|"
    r"违反|"
    r"敏感|"
    r"审核|"
    r"内容安全|"
    r"安全过滤|"
    r"安全策略|"
    r"安全拦截|"
    r"色情",
    re.IGNORECASE,
)

_PARAM_UNSUPPORTED_PATTERN = re.compile(
    r"unknown[_\s-]?(?:field|parameter|argument|property)|"
    r"invalid[_\s-]?(?:parameter|value|argument|field|request)|"
    r"unexpected[_\s-]?(?:keyword|field|argument)|"
    r"does not support|"
    r"unsupported|"
    r"not (?:a )?valid|"
    r"未支持|"
    r"不支持的?参数|"
    r"非法参数|"
    r"无效参数|"
    r"参数错误",
    re.IGNORECASE,
)

_AUTH_OR_QUOTA_PATTERN = re.compile(
    r"unauthorized|"
    r"forbidden|"
    r"invalid[_\s-]?api[_\s-]?key|"
    r"authentication|"
    r"permission|"
    r"rate[_\s-]?limit|"
    r"too many requests|"
    r"quota|"
    r"insufficient|"
    r"billing|"
    r"余额|"
    r"额度|"
    r"鉴权|"
    r"未授权|"
    r"权限|"
    r"配额|"
    r"超限|"
    r"频率",
    re.IGNORECASE,
)


class FailureClass(Enum):
    """Classification of generation failures for bypass-chain recovery edges."""

    CONTENT_BLOCKED = "content_blocked"
    PARAM_UNSUPPORTED = "param_unsupported"
    AUTH_OR_QUOTA = "auth_or_quota"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"


class GenerationError(Exception):
    """Raised when image generation fails."""


class SensitiveContentError(GenerationError):
    """Raised when content remains blocked after the full bypass chain is exhausted."""

    def __init__(self, mode: Mode):
        super().__init__(sensitive_content_message(mode))
        self.mode = mode


def is_safety_moderation_error(message: str) -> bool:
    return classify_generation_failure(message) == FailureClass.CONTENT_BLOCKED


def classify_generation_failure(
    message: str,
    *,
    status: int | None = None,
) -> FailureClass:
    """Classify an upstream failure so adapters can pick the right recovery edge."""
    text = (message or "").strip()
    if status == 429:
        return FailureClass.AUTH_OR_QUOTA
    if status in {401, 403}:
        # Some gateways reuse 403 for content policy; prefer safety signal when present.
        if text and _SAFETY_ERROR_PATTERN.search(text):
            return FailureClass.CONTENT_BLOCKED
        return FailureClass.AUTH_OR_QUOTA
    if status is not None and status >= 500:
        return FailureClass.TRANSIENT

    if not text:
        return FailureClass.UNKNOWN

    # Prefer explicit param-unsupported phrasing over bare keyword overlap.
    if _PARAM_UNSUPPORTED_PATTERN.search(text):
        return FailureClass.PARAM_UNSUPPORTED
    if _SAFETY_ERROR_PATTERN.search(text):
        return FailureClass.CONTENT_BLOCKED
    if _AUTH_OR_QUOTA_PATTERN.search(text):
        return FailureClass.AUTH_OR_QUOTA
    if status is not None and 400 <= status < 500:
        return FailureClass.PARAM_UNSUPPORTED
    return FailureClass.UNKNOWN


def sensitive_content_message(mode: Mode) -> str:
    if mode == "image_to_image":
        return "包含敏感内容，改图失败"
    return "包含敏感内容，生图失败"


def moderation_bypass_enabled(level: str, *, default: str = "auto") -> bool:
    return (level or default).lower() == "none"


def raise_exhausted_generation_error(
    mode: Mode,
    last_error: str,
    *,
    content_blocked: bool,
) -> NoReturn:
    """Raise the final error after a generation attempt chain is exhausted."""
    if content_blocked:
        raise SensitiveContentError(mode)
    raise GenerationError(last_error or "生成失败")


@dataclass
class ModelConfig:
    provider: str
    display_name: str
    url: str
    apikey: str
    model_name: str
    quality: str = "high"
    size: str = "auto"
    moderation: str = "auto"
    supported_modes: list[str] = field(default_factory=lambda: ["text_to_image", "image_to_image"])
    seed: str = ""
    priority: int = 0
    enabled: bool = True
    retry_count: int = -1
    max_generation_count: int = -1
    send_strategy: str = "follow_global"
    dedicated_command: str = ""
    fake_forward_mode: str = "follow_global"
    fake_forward_custom_qq: str = ""
    kind: str = "model"
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_template_entry(cls, entry: dict[str, Any]) -> ModelConfig:
        # Imported lazily to avoid a hard import-time dependency from the
        # adapters package onto the services package.
        from ..services.priority import resolve_priority_value
        from ..services.fake_forward import normalize_custom_qq, parse_entry_fake_forward_mode
        from ..services.send_strategy import parse_entry_send_strategy
        from ..services.workflow_config import normalize_supported_modes

        template = str(
            entry.get("__template_key")
            or entry.get("_template")
            or entry.get("template")
            or entry.get("provider")
            or ""
        ).lower()
        return cls(
            provider=template,
            display_name=str(entry.get("display_name") or template or "未命名模型"),
            url=str(entry.get("url") or "").strip(),
            apikey=str(entry.get("apikey") or "").strip(),
            model_name=str(entry.get("model_name") or "").strip(),
            quality=str(entry.get("quality") or "high"),
            size=str(entry.get("size") or "auto"),
            moderation=str(entry.get("moderation") or "auto"),
            supported_modes=normalize_supported_modes(
                entry.get("supported_modes"),
                default_modes=["text_to_image", "image_to_image"],
            ),
            seed=str(entry.get("seed") or "").strip(),
            priority=resolve_priority_value(entry, default_priority=10),
            enabled=parse_bool(entry.get("enabled"), True),
            retry_count=parse_int(entry.get("retry_count"), -1),
            max_generation_count=parse_int(entry.get("max_generation_count"), -1),
            send_strategy=parse_entry_send_strategy(entry.get("send_strategy")),
            dedicated_command=normalize_dedicated_command(entry.get("dedicated_command")),
            fake_forward_mode=parse_entry_fake_forward_mode(entry.get("fake_forward_mode")),
            fake_forward_custom_qq=normalize_custom_qq(entry.get("fake_forward_custom_qq")),
            raw=entry,
        )

    def model_key(self) -> str:
        return f"{self.provider}|{self.display_name}|{self.url}|{self.model_name}"

    def supports_mode(self, mode: str) -> bool:
        return mode in self.supported_modes
