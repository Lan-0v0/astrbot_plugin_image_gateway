from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class GenerationError(Exception):
    """Raised when image generation fails."""


@dataclass
class ModelConfig:
    provider: str
    display_name: str
    url: str
    apikey: str
    model_name: str
    quality: str = "auto"
    size: str = "1024x1024"
    moderation: str = "auto"
    seed: str = ""
    priority: int = 0
    enabled: bool = True
    retry_count: int = -1
    max_generation_count: int = -1
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_template_entry(cls, entry: dict[str, Any]) -> ModelConfig:
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
            quality=str(entry.get("quality") or "auto"),
            size=str(entry.get("size") or "1024x1024"),
            moderation=str(entry.get("moderation") or "auto"),
            seed=str(entry.get("seed") or "").strip(),
            priority=int(entry.get("priority") or 0),
            enabled=bool(entry.get("enabled", True)),
            retry_count=int(entry.get("retry_count", -1)),
            max_generation_count=int(entry.get("max_generation_count", -1)),
            raw=entry,
        )

    def model_key(self) -> str:
        return f"{self.provider}|{self.display_name}|{self.url}|{self.model_name}"
