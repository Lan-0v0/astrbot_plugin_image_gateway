"""Image generation adapters."""

from .base import GenerationError, ModelConfig, SensitiveContentError
from .gemini import GeminiAdapter
from .openai import OpenAIAdapter

__all__ = [
    "GenerationError",
    "ModelConfig",
    "SensitiveContentError",
    "OpenAIAdapter",
    "GeminiAdapter",
    "get_adapter",
]


def get_adapter(provider: str):
    provider = (provider or "").strip().lower()
    if provider == "openai":
        return OpenAIAdapter()
    if provider == "gemini":
        return GeminiAdapter()
    raise GenerationError(f"不支持的提供商: {provider}")
