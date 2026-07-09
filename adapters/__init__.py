"""Image generation adapters."""

from .base import GenerationError, ModelConfig, SensitiveContentError

__all__ = [
    "GenerationError",
    "ModelConfig",
    "SensitiveContentError",
    "OpenAIAdapter",
    "GeminiAdapter",
    "DashScopeAdapter",
    "VolcengineAdapter",
    "MiniMaxAdapter",
    "ZhipuAdapter",
    "HunyuanAdapter",
    "get_adapter",
]


def __getattr__(name: str):
    if name == "OpenAIAdapter":
        from .openai import OpenAIAdapter

        return OpenAIAdapter
    if name == "GeminiAdapter":
        from .gemini import GeminiAdapter

        return GeminiAdapter
    if name == "DashScopeAdapter":
        from .dashscope import DashScopeAdapter

        return DashScopeAdapter
    if name == "VolcengineAdapter":
        from .volcengine import VolcengineAdapter

        return VolcengineAdapter
    if name == "MiniMaxAdapter":
        from .minimax import MiniMaxAdapter

        return MiniMaxAdapter
    if name == "ZhipuAdapter":
        from .zhipu import ZhipuAdapter

        return ZhipuAdapter
    if name == "HunyuanAdapter":
        from .hunyuan import HunyuanAdapter

        return HunyuanAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_adapter(provider: str):
    provider = (provider or "").strip().lower()
    if provider == "openai":
        from .openai import OpenAIAdapter

        return OpenAIAdapter()
    if provider == "gemini":
        from .gemini import GeminiAdapter

        return GeminiAdapter()
    if provider in {"dashscope", "bailian", "aliyun", "aliyun_bailian"}:
        from .dashscope import DashScopeAdapter

        return DashScopeAdapter()
    if provider in {"volcengine", "volcano", "ark", "bytedance"}:
        from .volcengine import VolcengineAdapter

        return VolcengineAdapter()
    if provider == "minimax":
        from .minimax import MiniMaxAdapter

        return MiniMaxAdapter()
    if provider in {"zhipu", "glm", "cogview"}:
        from .zhipu import ZhipuAdapter

        return ZhipuAdapter()
    if provider in {"hunyuan", "tencent", "tencent_hunyuan"}:
        from .hunyuan import HunyuanAdapter

        return HunyuanAdapter()
    raise GenerationError(f"不支持的提供商: {provider}")