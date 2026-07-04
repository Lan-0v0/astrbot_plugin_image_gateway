from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def install_astrbot_test_stubs() -> None:
    """Provide the minimal AstrBot modules required by the plugin imports."""
    if "astrbot" in sys.modules:
        return

    logger_stub = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    astrbot_module = types.ModuleType("astrbot")
    astrbot_api_module = types.ModuleType("astrbot.api")
    astrbot_api_all_module = types.ModuleType("astrbot.api.all")
    astrbot_core_module = types.ModuleType("astrbot.core")
    astrbot_core_message_module = types.ModuleType("astrbot.core.message")
    astrbot_core_message_components_module = types.ModuleType(
        "astrbot.core.message.components"
    )

    class DummyImage:
        async def convert_to_base64(self) -> str:
            return "stub-image"

    class DummyReply:
        def __init__(self, chain=None):
            self.chain = chain or []

    astrbot_api_module.logger = logger_stub
    astrbot_api_all_module.Image = DummyImage
    astrbot_core_message_components_module.Reply = DummyReply

    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = astrbot_api_module
    sys.modules["astrbot.api.all"] = astrbot_api_all_module
    sys.modules["astrbot.core"] = astrbot_core_module
    sys.modules["astrbot.core.message"] = astrbot_core_message_module
    sys.modules["astrbot.core.message.components"] = astrbot_core_message_components_module


install_astrbot_test_stubs()

repository_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repository_root.parent))

from astrbot_plugin_image_gateway.adapters.base import GenerationError, ModelConfig  # noqa: E402
from astrbot_plugin_image_gateway.services.generation import GenerationService  # noqa: E402
from astrbot_plugin_image_gateway.utils.messages import parse_command_text  # noqa: E402


class FakeCounter:
    def __init__(self, initial_counts: dict[str, int] | None = None):
        self.counts = dict(initial_counts or {})

    async def get_count(self, model_key: str) -> int:
        return self.counts.get(model_key, 0)

    async def add_count(self, model_key: str, delta: int) -> int:
        updated_count = self.counts.get(model_key, 0) + delta
        self.counts[model_key] = updated_count
        return updated_count


class FakeClientSession:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeEvent:
    def __init__(self, message_text: str):
        self.message_str = message_text


class GenerationServiceRegressionTests(unittest.IsolatedAsyncioTestCase):
    def build_model(self, display_name: str, *, max_generation_count: int = -1) -> ModelConfig:
        return ModelConfig(
            provider="openai",
            display_name=display_name,
            url="https://example.com/v1",
            apikey="test-key",
            model_name="test-model",
            max_generation_count=max_generation_count,
        )

    async def test_returns_quota_error_only_when_all_models_are_exhausted(self) -> None:
        primary_model = self.build_model("Primary", max_generation_count=1)
        secondary_model = self.build_model("Secondary", max_generation_count=-1)
        counter = FakeCounter({primary_model.model_key(): 1})
        service = GenerationService(
            [primary_model, secondary_model],
            global_retry_count=1,
            global_max_generation_count=-1,
            output_dir=Path("."),
            counter=counter,
        )

        failing_adapter = types.SimpleNamespace(
            text_to_image=self.raise_backend_error,
            image_to_image=self.raise_backend_error,
        )

        with (
            patch(
                "astrbot_plugin_image_gateway.services.generation.get_adapter",
                return_value=failing_adapter,
            ),
            patch(
                "astrbot_plugin_image_gateway.services.generation.aiohttp.ClientSession",
                FakeClientSession,
            ),
        ):
            with self.assertRaises(GenerationError) as raised_error:
                await service.generate(mode="text_to_image", prompt="test prompt")

        self.assertEqual(str(raised_error.exception), "Secondary: 后端服务暂时不可用")

    async def test_returns_quota_error_when_every_model_is_exhausted(self) -> None:
        primary_model = self.build_model("Primary", max_generation_count=1)
        secondary_model = self.build_model("Secondary", max_generation_count=2)
        counter = FakeCounter(
            {
                primary_model.model_key(): 1,
                secondary_model.model_key(): 2,
            }
        )
        service = GenerationService(
            [primary_model, secondary_model],
            global_retry_count=1,
            global_max_generation_count=-1,
            output_dir=Path("."),
            counter=counter,
        )

        with patch(
            "astrbot_plugin_image_gateway.services.generation.aiohttp.ClientSession",
            FakeClientSession,
        ):
            with self.assertRaises(GenerationError) as raised_error:
                await service.generate(mode="text_to_image", prompt="test prompt")

        self.assertEqual(str(raised_error.exception), "超出生成张数上限")

    async def raise_backend_error(self, *args, **kwargs):
        raise GenerationError("后端服务暂时不可用")


class MessageParsingRegressionTests(unittest.TestCase):
    def test_parse_command_text_supports_punctuation_delimiters(self) -> None:
        event = FakeEvent("/改图：把这张图改成电影海报")
        self.assertEqual(parse_command_text(event, "改图"), "把这张图改成电影海报")

    def test_parse_command_text_does_not_capture_unrelated_commands(self) -> None:
        event = FakeEvent("/别的命令 只是路过")
        self.assertEqual(parse_command_text(event, "改图"), "")


if __name__ == "__main__":
    unittest.main()
