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
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    astrbot_module = types.ModuleType("astrbot")
    astrbot_api_module = types.ModuleType("astrbot.api")
    astrbot_api_all_module = types.ModuleType("astrbot.api.all")
    astrbot_api_event_module = types.ModuleType("astrbot.api.event")
    astrbot_api_message_components_module = types.ModuleType("astrbot.api.message_components")
    astrbot_api_star_module = types.ModuleType("astrbot.api.star")
    astrbot_core_module = types.ModuleType("astrbot.core")
    astrbot_core_message_module = types.ModuleType("astrbot.core.message")
    astrbot_core_message_event_result_module = types.ModuleType(
        "astrbot.core.message.message_event_result"
    )
    astrbot_core_message_components_module = types.ModuleType(
        "astrbot.core.message.components"
    )

    class DummyImage:
        async def convert_to_base64(self) -> str:
            return "stub-image"

    class DummyPlain:
        def __init__(self, text: str):
            self.text = text

    class DummyNode:
        def __init__(self, uin=None, name=None, content=None):
            self.uin = uin
            self.name = name
            self.content = content or []

    class DummyNodes:
        def __init__(self, nodes=None):
            self.nodes = nodes or []

    class DummyReply:
        def __init__(self, chain=None):
            self.chain = chain or []

    class DummyAstrBotConfig(dict):
        pass

    class DummyAstrMessageEvent:
        pass

    class DummyContext:
        pass

    class DummyStar:
        def __init__(self, context=None):
            self.context = context

    class DummyStarTools:
        @staticmethod
        def get_data_dir(plugin_name: str) -> Path:
            return Path(".")

    class DummyMessageChain(list):
        def __init__(self, components):
            super().__init__(components)
            self.chain = components

    def dummy_register(*args, **kwargs):
        def decorator(cls):
            return cls

        return decorator

    class DummyFilterProxy:
        def __getattr__(self, name):
            def decorator_factory(*args, **kwargs):
                def decorator(target):
                    return target

                return decorator

            return decorator_factory

    astrbot_api_module.logger = logger_stub
    astrbot_api_module.AstrBotConfig = DummyAstrBotConfig
    astrbot_api_all_module.Image = DummyImage
    astrbot_api_event_module.AstrMessageEvent = DummyAstrMessageEvent
    astrbot_api_event_module.filter = DummyFilterProxy()
    astrbot_api_message_components_module.Plain = DummyPlain
    astrbot_api_message_components_module.Node = DummyNode
    astrbot_api_message_components_module.Nodes = DummyNodes
    astrbot_api_star_module.Context = DummyContext
    astrbot_api_star_module.Star = DummyStar
    astrbot_api_star_module.StarTools = DummyStarTools
    astrbot_api_star_module.register = dummy_register
    astrbot_core_message_event_result_module.MessageChain = DummyMessageChain
    astrbot_core_message_components_module.Reply = DummyReply

    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = astrbot_api_module
    sys.modules["astrbot.api.all"] = astrbot_api_all_module
    sys.modules["astrbot.api.event"] = astrbot_api_event_module
    sys.modules["astrbot.api.message_components"] = astrbot_api_message_components_module
    sys.modules["astrbot.api.star"] = astrbot_api_star_module
    sys.modules["astrbot.core"] = astrbot_core_module
    sys.modules["astrbot.core.message"] = astrbot_core_message_module
    sys.modules["astrbot.core.message.message_event_result"] = (
        astrbot_core_message_event_result_module
    )
    sys.modules["astrbot.core.message.components"] = astrbot_core_message_components_module


install_astrbot_test_stubs()

repository_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repository_root.parent))

from astrbot_plugin_image_gateway.adapters.base import GenerationError, ModelConfig  # noqa: E402
from astrbot_plugin_image_gateway.adapters.gemini import GeminiAdapter  # noqa: E402
from astrbot_plugin_image_gateway.adapters.openai import OpenAIAdapter  # noqa: E402
from astrbot_plugin_image_gateway.main import (  # noqa: E402
    DEFAULT_LLM_CUSTOM_PERSONA_PROMPT,
    GenerationStartMessageConfig,
    ImageGatewayPlugin,
    StartMessageDispatchResult,
)
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
    def __init__(
        self,
        message_text: str,
        *,
        group_id: str = "123456",
        sender_id: str = "654321",
        platform_id: str = "test-platform",
        platform_name: str = "aiocqhttp",
    ):
        self.message_str = message_text
        self.unified_msg_origin = "test-origin"
        self._group_id = group_id
        self._sender_id = sender_id
        self._platform_id = platform_id
        self._platform_name = platform_name

    def plain_result(self, text: str):
        return text

    def chain_result(self, chain):
        return chain

    def get_group_id(self):
        return self._group_id

    def get_sender_id(self):
        return self._sender_id

    def get_platform_id(self):
        return self._platform_id

    def get_platform_name(self):
        return self._platform_name


class FakePlatformClient:
    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = dict(responses or {})
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_action(self, action: str, **kwargs):
        self.calls.append((action, kwargs))
        response = self.responses.get(action)
        if callable(response):
            return response(**kwargs)
        return response


class FakePlatform:
    def __init__(self, client: FakePlatformClient):
        self._client = client

    def get_client(self):
        return self._client


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
                await service.generate(mode="text_to_image", prompt="test prompt", count=3)

        self.assertEqual(str(raised_error.exception), "超出生成张数上限")

    async def test_historical_generation_count_does_not_trigger_single_request_limit(self) -> None:
        model = self.build_model("Primary", max_generation_count=2)
        counter = FakeCounter({model.model_key(): 999})
        service = GenerationService(
            [model],
            global_retry_count=1,
            global_max_generation_count=2,
            output_dir=Path("."),
            counter=counter,
        )

        successful_adapter = types.SimpleNamespace(
            text_to_image=self.return_generated_path,
            image_to_image=self.return_generated_path,
        )

        with (
            patch(
                "astrbot_plugin_image_gateway.services.generation.get_adapter",
                return_value=successful_adapter,
            ),
            patch(
                "astrbot_plugin_image_gateway.services.generation.aiohttp.ClientSession",
                FakeClientSession,
            ),
        ):
            paths, model_name = await service.generate(mode="image_to_image", prompt="test prompt")

        self.assertEqual(model_name, "Primary")
        self.assertEqual(paths, [Path("generated.png")])

    async def return_generated_path(self, *args, **kwargs):
        return [Path("generated.png")]

    async def raise_backend_error(self, *args, **kwargs):
        raise GenerationError("后端服务暂时不可用")


class MessageParsingRegressionTests(unittest.TestCase):
    def test_parse_command_text_supports_punctuation_delimiters(self) -> None:
        event = FakeEvent("/改图：把这张图改成电影海报")
        self.assertEqual(parse_command_text(event, "改图"), "把这张图改成电影海报")

    def test_parse_command_text_does_not_capture_unrelated_commands(self) -> None:
        event = FakeEvent("/别的命令 只是路过")
        self.assertEqual(parse_command_text(event, "改图"), "")


class ConfigurationDefaultRegressionTests(unittest.TestCase):
    def test_model_config_defaults_to_high_quality(self) -> None:
        model_config = ModelConfig.from_template_entry({"provider": "openai"})
        self.assertEqual(model_config.quality, "high")

    def test_generation_service_from_config_uses_new_global_defaults(self) -> None:
        generation_service = GenerationService.from_config({}, Path("."), FakeCounter())
        self.assertEqual(generation_service.global_retry_count, 2)
        self.assertEqual(generation_service.global_max_generation_count, 2)

    def test_load_start_message_config_uses_default_custom_persona_prompt(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        start_message_config = plugin_instance._load_start_message_config(
            {"mode": "llm", "llm_persona_source": "custom"}
        )
        self.assertEqual(
            start_message_config.llm_custom_persona_prompt,
            DEFAULT_LLM_CUSTOM_PERSONA_PROMPT,
        )

    def test_load_start_message_config_supports_enabled_switch(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        enabled_config = plugin_instance._load_start_message_config({})
        disabled_config = plugin_instance._load_start_message_config({"enabled": False})

        self.assertEqual(enabled_config.enabled, True)
        self.assertEqual(disabled_config.enabled, False)


class StartMessageOrderRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_quota_error_is_returned_before_start_message(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance._refresh_services = lambda: None
        plugin_instance.generation_service = types.SimpleNamespace(
            _normalize_requested_count=lambda mode, count: 3,
            validate_request_count=lambda requested_count: (_ for _ in ()).throw(GenerationError("超出生成张数上限")),
        )

        async def fail_if_called(*args, **kwargs):
            raise AssertionError("开始提示不应在超限前发送")

        plugin_instance._send_start_message = fail_if_called

        results = []
        async for result in plugin_instance._run_generation(
            FakeEvent("/生图 测试 3"),
            mode="text_to_image",
            prompt="测试",
            count=3,
            input_images=None,
            success_label="生图",
        ):
            results.append(result)

        self.assertEqual(results, ["超出生成张数上限"])

    async def test_build_generation_start_message_returns_empty_when_disabled(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance.start_message_config = GenerationStartMessageConfig(enabled=False)

        message_text = await plugin_instance._build_generation_start_message(FakeEvent("/生图 测试"), "生图")

        self.assertEqual(message_text, "")


class ImageDeliveryRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_generated_images_prefers_event_send(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance.context = types.SimpleNamespace(get_config=lambda: {})

        async def build_image_component(image_path: str):
            return f"image:{image_path}"

        plugin_instance._build_image_component = build_image_component

        event = FakeEvent("/生图 测试")
        event.sent_messages = []

        async def send(message_chain):
            event.sent_messages.append(message_chain)

        event.send = send

        results = []
        async for result in plugin_instance._send_generated_images(event, ["one.png"]):
            results.append(result)

        self.assertEqual(results, [])
        self.assertEqual(len(event.sent_messages), 1)
        self.assertEqual(list(event.sent_messages[0]), ["image:one.png"])

    async def test_send_generated_images_falls_back_to_context_send_message(self) -> None:
        context_sent_messages = []
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance.context = types.SimpleNamespace(
            get_config=lambda: {},
            send_message=self._build_context_send(context_sent_messages),
        )

        async def build_image_component(image_path: str):
            return f"image:{image_path}"

        plugin_instance._build_image_component = build_image_component

        event = FakeEvent("/生图 测试")

        async def failing_send(message_chain):
            raise RuntimeError("event send unavailable")

        event.send = failing_send

        results = []
        async for result in plugin_instance._send_generated_images(event, ["one.png"]):
            results.append(result)

        self.assertEqual(results, [])
        self.assertEqual(context_sent_messages, [("test-origin", ["image:one.png"])])

    async def test_send_generated_images_falls_back_to_result_pipeline(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance.context = types.SimpleNamespace(get_config=lambda: {})

        async def build_image_component(image_path: str):
            return f"image:{image_path}"

        plugin_instance._build_image_component = build_image_component

        event = FakeEvent("/生图 测试")

        results = []
        async for result in plugin_instance._send_generated_images(event, ["one.png"]):
            results.append(result)

        self.assertEqual(results, [["image:one.png"]])

    @staticmethod
    def _build_context_send(context_sent_messages: list[tuple[str, list[str]]]):
        async def send_message(message_origin, message_chain):
            context_sent_messages.append((message_origin, list(message_chain)))

        return send_message


class SuccessDeliveryRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_generation_sends_success_text_before_image_directly(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance._refresh_services = lambda: None
        plugin_instance.context = types.SimpleNamespace(get_config=lambda: {})
        plugin_instance.generation_service = types.SimpleNamespace(
            _normalize_requested_count=lambda mode, count: 1,
            validate_request_count=lambda requested_count: None,
            generate=self._build_generate_result([Path("generated.png")]),
        )

        async def build_image_component(image_path: str):
            return f"image:{image_path}"

        async def retract_start_message(event, message_id):
            return None

        plugin_instance._build_image_component = build_image_component
        plugin_instance._send_start_message = self._build_start_message_result
        plugin_instance._retract_start_message = retract_start_message

        event = FakeEvent("/改图 测试")
        event.sent_messages = []

        async def send(message_chain):
            event.sent_messages.append(list(message_chain))

        event.send = send

        results = []
        async for result in plugin_instance._run_generation(
            event,
            mode="image_to_image",
            prompt="测试",
            count=1,
            input_images=["stub-image"],
            success_label="改图",
        ):
            results.append(result)

        self.assertEqual(results, [])
        self.assertEqual(len(event.sent_messages), 2)
        self.assertEqual(event.sent_messages[0][0].text.startswith("改图成功，用时"), True)
        self.assertEqual(event.sent_messages[1], ["image:generated.png"])

    async def test_run_generation_retracts_passively_sent_start_message_with_platform_message_id(self) -> None:
        start_message_client = FakePlatformClient(
            responses={
                "send_group_msg": {"data": {"message_id": 24680}},
            }
        )
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance._refresh_services = lambda: None
        plugin_instance.context = types.SimpleNamespace(
            get_config=lambda: {},
            get_platform_inst=lambda platform_id: FakePlatform(start_message_client),
        )
        plugin_instance.generation_service = types.SimpleNamespace(
            _normalize_requested_count=lambda mode, count: 1,
            validate_request_count=lambda requested_count: None,
            generate=self._build_generate_result([Path("generated.png")]),
        )

        async def build_image_component(image_path: str):
            return f"image:{image_path}"

        retract_calls: list[str | None] = []

        async def retract_start_message(event, message_id):
            retract_calls.append(message_id)

        plugin_instance._build_image_component = build_image_component
        plugin_instance._send_start_message = self._build_passive_start_message_result
        plugin_instance._retract_start_message = retract_start_message

        event = FakeEvent("/改图 测试")
        event.sent_messages = []

        async def send(message_chain):
            event.sent_messages.append(list(message_chain))

        event.send = send

        results = []
        async for result in plugin_instance._run_generation(
            event,
            mode="image_to_image",
            prompt="测试",
            count=1,
            input_images=["stub-image"],
            success_label="改图",
        ):
            results.append(result)

        self.assertEqual(results, [])
        self.assertEqual(retract_calls, ["24680"])
        self.assertEqual(event.sent_messages[-1], ["image:generated.png"])

    @staticmethod
    async def _build_start_message_result(event, label):
        return StartMessageDispatchResult(text="开始生成", message_id="1", sent_passively=False)

    @staticmethod
    async def _build_passive_start_message_result(event, label):
        return StartMessageDispatchResult(text="开始生成", sent_passively=True)

    @staticmethod
    def _build_generate_result(paths: list[Path]):
        async def generate(**kwargs):
            return paths, "Test Model"

        return generate


class ModerationOptionRegressionTests(unittest.TestCase):
    def test_openai_high_moderation_maps_to_high(self) -> None:
        self.assertEqual(OpenAIAdapter._moderation_attempts("high"), ["high"])

    def test_gemini_high_moderation_maps_to_medium_and_above_blocking(self) -> None:
        safety_attempts = GeminiAdapter()._safety_attempts("high")
        self.assertEqual(
            safety_attempts,
            [[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]],
        )


if __name__ == "__main__":
    unittest.main()
