"""Image generation adapters."""

from .base import GenerationError, ModelConfig, SensitiveContentError

__all__ = [
    "GenerationError",
    "ModelConfig",
    "SensitiveContentError",
    "OpenAIAdapter",
    "GeminiAdapter",
    "get_adapter",
]


def __getattr__(name: str):
    if name == "OpenAIAdapter":
        from .openai import OpenAIAdapter

        return OpenAIAdapter
    if name == "GeminiAdapter":
        from .gemini import GeminiAdapter

        return GeminiAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_adapter(provider: str):
    provider = (provider or "").strip().lower()
    if provider == "openai":
        from .openai import OpenAIAdapter

        return OpenAIAdapter()
    if provider == "gemini":
        from .gemini import GeminiAdapter

        return GeminiAdapter()
    raise GenerationError(f"不支持的提供商: {provider}")
