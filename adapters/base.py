from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

Mode = Literal["text_to_image", "image_to_image"]

_SAFETY_ERROR_PATTERN = re.compile(
    r"content[_\s-]?policy|moderation|safety|sensitive|sexual|"
    r"sexually[_\s-]?explicit|blocked|harm|inappropriate|"
    r"违反|敏感|审核|安全|色情",
    re.IGNORECASE,
)


class GenerationError(Exception):
    """Raised when image generation fails."""


class SensitiveContentError(GenerationError):
    """Raised when content is blocked after moderation none→low fallback."""

    def __init__(self, mode: Mode):
        super().__init__(sensitive_content_message(mode))
        self.mode = mode


def is_safety_moderation_error(message: str) -> bool:
    return bool(_SAFETY_ERROR_PATTERN.search(message or ""))


def sensitive_content_message(mode: Mode) -> str:
    if mode == "image_to_image":
        return "包含敏感内容，改图失败"
    return "包含敏感内容，生图失败"


def moderation_bypass_enabled(level: str, *, default: str = "auto") -> bool:
    return (level or default).lower() == "none"


@dataclass
class ModelConfig:
    provider: str
    display_name: str
    url: str
    apikey: str
    model_name: str
    quality: str = "high"
    size: str = "1024x1024"
    moderation: str = "auto"
    seed: str = ""
    priority: int = 0
    enabled: bool = True
    retry_count: int = -1
    max_generation_count: int = -1
    send_strategy: str = "follow_global"
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
            size=str(entry.get("size") or "1024x1024"),
            moderation=str(entry.get("moderation") or "auto"),
            seed=str(entry.get("seed") or "").strip(),
            priority=resolve_priority_value(entry, default_priority=10),
            enabled=bool(entry.get("enabled", True)),
            retry_count=int(entry.get("retry_count", -1)),
            max_generation_count=int(entry.get("max_generation_count", -1)),
            send_strategy=parse_entry_send_strategy(entry.get("send_strategy")),
            fake_forward_mode=parse_entry_fake_forward_mode(entry.get("fake_forward_mode")),
            fake_forward_custom_qq=normalize_custom_qq(entry.get("fake_forward_custom_qq")),
            raw=entry,
        )

    def model_key(self) -> str:
        return f"{self.provider}|{self.display_name}|{self.url}|{self.model_name}"
