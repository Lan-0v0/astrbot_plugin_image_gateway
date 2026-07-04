from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from typing import Any
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
from astrbot_plugin_image_gateway.services.send_strategy import (  # noqa: E402
    FOLLOW_GLOBAL,
    SendStrategy,
    get_sender_order,
    parse_entry_send_strategy,
    parse_global_send_strategy,
    resolve_effective_send_strategy,
)
from astrbot_plugin_image_gateway.services.workflow_config import (  # noqa: E402
    WorkflowConfig,
    WorkflowNodeBinding,
    WorkflowRuntimeConfig,
)
from astrbot_plugin_image_gateway.services.workflow_merge import merge_workflow_payload  # noqa: E402
from astrbot_plugin_image_gateway.utils.json_path import get_by_dot_path, set_by_dot_path  # noqa: E402
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
            paths, model_name, _effective_send_strategy = await service.generate(
                mode="image_to_image", prompt="test prompt"
            )

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

    def test_model_config_send_strategy_defaults_to_follow_global(self) -> None:
        model_config = ModelConfig.from_template_entry({"provider": "openai"})
        self.assertEqual(model_config.send_strategy, "follow_global")

    def test_model_config_send_strategy_parses_explicit_value(self) -> None:
        model_config = ModelConfig.from_template_entry(
            {"provider": "openai", "send_strategy": "event_send_first"}
        )
        self.assertEqual(model_config.send_strategy, "event_send_first")

    def test_generation_service_from_config_uses_new_global_defaults(self) -> None:
        generation_service = GenerationService.from_config({}, Path("."), FakeCounter())
        self.assertEqual(generation_service.global_retry_count, 2)
        self.assertEqual(generation_service.global_max_generation_count, 2)
        self.assertEqual(generation_service.global_send_strategy, SendStrategy.DIRECT_FIRST)

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
        plugin_instance.global_send_strategy = SendStrategy.DIRECT_FIRST
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
        plugin_instance.global_send_strategy = SendStrategy.DIRECT_FIRST
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
            return paths, "Test Model", SendStrategy.DIRECT_FIRST

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


class JsonPathRegressionTests(unittest.TestCase):
    def test_get_by_dot_path_reads_nested_dict_value(self) -> None:
        data = {"inputs": {"text": "hello"}}
        self.assertEqual(get_by_dot_path(data, "inputs.text"), "hello")

    def test_get_by_dot_path_reads_list_index(self) -> None:
        data = {"inputs": {"texts": ["first", "second"]}}
        self.assertEqual(get_by_dot_path(data, "inputs.texts.0"), "first")
        self.assertEqual(get_by_dot_path(data, "inputs.texts.1"), "second")

    def test_set_by_dot_path_overwrites_nested_dict_value(self) -> None:
        data = {"inputs": {"text": "original"}}
        set_by_dot_path(data, "inputs.text", "overwritten")
        self.assertEqual(data["inputs"]["text"], "overwritten")

    def test_set_by_dot_path_overwrites_list_index(self) -> None:
        data = {"inputs": {"texts": ["first", "second"]}}
        set_by_dot_path(data, "inputs.texts.1", "replaced")
        self.assertEqual(data["inputs"]["texts"], ["first", "replaced"])

    def test_set_by_dot_path_raises_key_error_for_missing_field(self) -> None:
        data = {"inputs": {}}
        with self.assertRaises(KeyError):
            get_by_dot_path(data, "inputs.missing")

    def test_set_by_dot_path_raises_index_error_for_out_of_range_index(self) -> None:
        data = {"inputs": {"texts": ["only"]}}
        with self.assertRaises(IndexError):
            set_by_dot_path(data, "inputs.texts.5", "value")


class SendStrategyRegressionTests(unittest.TestCase):
    def test_parse_global_send_strategy_defaults_to_direct_first(self) -> None:
        self.assertEqual(parse_global_send_strategy(None), SendStrategy.DIRECT_FIRST)
        self.assertEqual(parse_global_send_strategy(""), SendStrategy.DIRECT_FIRST)
        self.assertEqual(parse_global_send_strategy("not-a-real-strategy"), SendStrategy.DIRECT_FIRST)

    def test_parse_global_send_strategy_parses_explicit_value(self) -> None:
        self.assertEqual(
            parse_global_send_strategy("platform_client_first"),
            SendStrategy.PLATFORM_CLIENT_FIRST,
        )

    def test_parse_entry_send_strategy_defaults_to_follow_global(self) -> None:
        self.assertEqual(parse_entry_send_strategy(None), FOLLOW_GLOBAL)
        self.assertEqual(parse_entry_send_strategy(""), FOLLOW_GLOBAL)
        self.assertEqual(parse_entry_send_strategy("not-a-real-strategy"), FOLLOW_GLOBAL)

    def test_parse_entry_send_strategy_parses_explicit_value(self) -> None:
        self.assertEqual(parse_entry_send_strategy("event_send_first"), "event_send_first")

    def test_resolve_effective_send_strategy_follows_global_when_entry_unset(self) -> None:
        effective_strategy = resolve_effective_send_strategy(
            global_strategy=SendStrategy.PLATFORM_CLIENT_FIRST,
            entry_strategy=FOLLOW_GLOBAL,
        )
        self.assertEqual(effective_strategy, SendStrategy.PLATFORM_CLIENT_FIRST)

    def test_resolve_effective_send_strategy_overrides_global_when_entry_set(self) -> None:
        effective_strategy = resolve_effective_send_strategy(
            global_strategy=SendStrategy.DIRECT_FIRST,
            entry_strategy="result_pipeline_only",
        )
        self.assertEqual(effective_strategy, SendStrategy.RESULT_PIPELINE_ONLY)

    def test_get_sender_order_direct_first_prefers_platform_client_for_start_message(self) -> None:
        delivery_order = get_sender_order(SendStrategy.DIRECT_FIRST, for_start_message=False)
        start_message_order = get_sender_order(SendStrategy.DIRECT_FIRST, for_start_message=True)

        self.assertEqual(delivery_order[0], "event_send")
        self.assertEqual(start_message_order[0], "platform_client")

    def test_get_sender_order_result_pipeline_only_returns_empty_list(self) -> None:
        self.assertEqual(get_sender_order(SendStrategy.RESULT_PIPELINE_ONLY), [])


class WorkflowConfigRegressionTests(unittest.TestCase):
    def test_workflow_node_binding_from_template_entry_falls_back_to_custom_text(self) -> None:
        node_binding = WorkflowNodeBinding.from_template_entry(
            {"node_id": "6", "field_path": "inputs.text", "binding_type": "not-a-real-type"}
        )
        self.assertEqual(node_binding.binding_type, "custom_text")

    def test_from_template_entry_parses_bindings_and_defaults(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {
                "display_name": "我的 ComfyUI 工作流",
                "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
                "workflow_variable_bindings": [
                    {
                        "node_id": "6",
                        "field_path": "inputs.text",
                        "binding_type": "prompt_positive",
                    }
                ],
            }
        )

        self.assertEqual(workflow_config.workflow_type, "comfyui")
        self.assertEqual(workflow_config.kind, "workflow")
        self.assertEqual(workflow_config.send_strategy, FOLLOW_GLOBAL)
        self.assertEqual(len(workflow_config.node_bindings), 1)
        self.assertEqual(workflow_config.node_bindings[0].binding_type, "prompt_positive")

    def test_from_template_entry_falls_back_to_comfyui_for_unknown_workflow_type(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry({"workflow_type": "unknown-engine"})
        self.assertEqual(workflow_config.workflow_type, "comfyui")

    def test_parsed_workflow_content_raises_generation_error_on_invalid_json(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {"display_name": "坏 JSON", "workflow_content": "{not valid json"}
        )
        with self.assertRaises(GenerationError):
            workflow_config.parsed_workflow_content()

    def test_resolve_runtime_config_uses_default_when_no_override(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry({"display_name": "无覆盖工作流"})
        default_runtime = WorkflowRuntimeConfig(base_url="http://default:8188", api_key="default-key")

        resolved_runtime = workflow_config.resolve_runtime_config(default_runtime)

        self.assertEqual(resolved_runtime.base_url, "http://default:8188")
        self.assertEqual(resolved_runtime.api_key, "default-key")

    def test_resolve_runtime_config_applies_entry_overrides(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {
                "display_name": "覆盖工作流",
                "runtime_base_url_override": "http://override:8188",
                "runtime_api_key_override": "override-key",
            }
        )
        default_runtime = WorkflowRuntimeConfig(base_url="http://default:8188", api_key="default-key")

        resolved_runtime = workflow_config.resolve_runtime_config(default_runtime)

        self.assertEqual(resolved_runtime.base_url, "http://override:8188")
        self.assertEqual(resolved_runtime.api_key, "override-key")


class WorkflowMergeRegressionTests(unittest.TestCase):
    def build_workflow_config(
        self,
        workflow_payload: dict[str, Any],
        node_bindings: list[dict[str, Any]],
    ) -> WorkflowConfig:
        return WorkflowConfig.from_template_entry(
            {
                "display_name": "测试工作流",
                "workflow_content": json.dumps(workflow_payload),
                "workflow_variable_bindings": node_bindings,
            }
        )

    def test_merge_overwrites_positive_prompt_via_node_id_and_field_path(self) -> None:
        workflow_config = self.build_workflow_config(
            {"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "placeholder", "clip": ["4", 1]}}},
            [{"node_id": "6", "field_path": "inputs.text", "binding_type": "prompt_positive"}],
        )

        merged_payload = merge_workflow_payload(workflow_config, positive_prompt="一只猫在草地上奔跑")

        self.assertEqual(merged_payload["6"]["inputs"]["text"], "一只猫在草地上奔跑")
        self.assertEqual(merged_payload["6"]["inputs"]["clip"], ["4", 1])

    def test_merge_overwrites_list_index_field_path(self) -> None:
        workflow_config = self.build_workflow_config(
            {"9": {"inputs": {"texts": ["old-a", "old-b"]}}},
            [{"node_id": "9", "field_path": "inputs.texts.1", "binding_type": "custom_text", "custom_value": "new-b"}],
        )

        merged_payload = merge_workflow_payload(workflow_config, positive_prompt="unused")

        self.assertEqual(merged_payload["9"]["inputs"]["texts"], ["old-a", "new-b"])

    def test_merge_custom_number_keeps_numeric_type_not_string(self) -> None:
        workflow_config = self.build_workflow_config(
            {"3": {"inputs": {"cfg": 7.0, "steps": 20}}},
            [
                {"node_id": "3", "field_path": "inputs.cfg", "binding_type": "custom_number", "custom_value": "4.5"},
                {"node_id": "3", "field_path": "inputs.steps", "binding_type": "custom_number", "custom_value": "30"},
            ],
        )

        merged_payload = merge_workflow_payload(workflow_config, positive_prompt="unused")

        self.assertEqual(merged_payload["3"]["inputs"]["cfg"], 4.5)
        self.assertIsInstance(merged_payload["3"]["inputs"]["cfg"], float)
        self.assertEqual(merged_payload["3"]["inputs"]["steps"], 30)
        self.assertIsInstance(merged_payload["3"]["inputs"]["steps"], int)

    def test_merge_random_seed_when_custom_value_is_empty(self) -> None:
        workflow_config = self.build_workflow_config(
            {"3": {"inputs": {"seed": 0}}},
            [{"node_id": "3", "field_path": "inputs.seed", "binding_type": "seed", "custom_value": ""}],
        )

        merged_payload = merge_workflow_payload(workflow_config, positive_prompt="unused")

        self.assertIsInstance(merged_payload["3"]["inputs"]["seed"], int)

    def test_merge_raises_generation_error_for_missing_node(self) -> None:
        workflow_config = self.build_workflow_config(
            {"6": {"inputs": {"text": "placeholder"}}},
            [{"node_id": "999", "field_path": "inputs.text", "binding_type": "prompt_positive"}],
        )

        with self.assertRaises(GenerationError):
            merge_workflow_payload(workflow_config, positive_prompt="不会用到")

    def test_merge_raises_generation_error_for_invalid_field_path(self) -> None:
        workflow_config = self.build_workflow_config(
            {"6": {"inputs": {"text": "placeholder"}}},
            [{"node_id": "6", "field_path": "inputs.missing_field", "binding_type": "prompt_positive"}],
        )

        with self.assertRaises(GenerationError):
            merge_workflow_payload(workflow_config, positive_prompt="不会用到")

    def test_merge_skips_image_input_binding_when_no_images_provided(self) -> None:
        workflow_config = self.build_workflow_config(
            {"10": {"inputs": {"image": "placeholder.png"}}},
            [{"node_id": "10", "field_path": "inputs.image", "binding_type": "image_input"}],
        )

        merged_payload = merge_workflow_payload(workflow_config, positive_prompt="unused", input_images=None)

        self.assertEqual(merged_payload["10"]["inputs"]["image"], "placeholder.png")


class MixedTargetSchedulingRegressionTests(unittest.IsolatedAsyncioTestCase):
    def build_workflow(self, display_name: str, *, priority: int = 0) -> WorkflowConfig:
        return WorkflowConfig.from_template_entry(
            {
                "display_name": display_name,
                "priority": priority,
                "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
                "workflow_variable_bindings": [
                    {"node_id": "6", "field_path": "inputs.text", "binding_type": "prompt_positive"}
                ],
            }
        )

    def build_model(self, display_name: str, *, priority: int = 0) -> ModelConfig:
        return ModelConfig(
            provider="openai",
            display_name=display_name,
            url="https://example.com/v1",
            apikey="test-key",
            model_name="test-model",
            priority=priority,
        )

    async def test_workflow_and_model_targets_are_scheduled_by_priority(self) -> None:
        low_priority_model = self.build_model("LowPriorityModel", priority=1)
        high_priority_workflow = self.build_workflow("HighPriorityWorkflow", priority=10)
        counter = FakeCounter()
        service = GenerationService(
            [high_priority_workflow, low_priority_model],
            global_retry_count=1,
            global_max_generation_count=-1,
            output_dir=Path("."),
            counter=counter,
        )

        async def fake_generate_text_to_image(self, prompt, count, workflow_config, runtime_config, output_dir, session):
            return [Path("workflow_generated.png")]

        with (
            patch(
                "astrbot_plugin_image_gateway.services.generation.ComfyUIWorkflowRunner.generate_text_to_image",
                fake_generate_text_to_image,
            ),
            patch(
                "astrbot_plugin_image_gateway.services.generation.aiohttp.ClientSession",
                FakeClientSession,
            ),
        ):
            paths, target_name, _effective_send_strategy = await service.generate(
                mode="text_to_image", prompt="测试"
            )

        self.assertEqual(target_name, "HighPriorityWorkflow")
        self.assertEqual(paths, [Path("workflow_generated.png")])

    async def test_workflow_target_is_skipped_for_image_to_image_requests(self) -> None:
        workflow_only = self.build_workflow("OnlyWorkflow", priority=10)
        counter = FakeCounter()
        service = GenerationService(
            [workflow_only],
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
                await service.generate(mode="image_to_image", prompt="测试", input_images=["stub-image"])

        self.assertIn("暂不支持改图", str(raised_error.exception))

    async def test_workflow_falls_back_to_next_model_on_failure(self) -> None:
        failing_workflow = self.build_workflow("FailingWorkflow", priority=10)
        fallback_model = self.build_model("FallbackModel", priority=1)
        counter = FakeCounter()
        service = GenerationService(
            [failing_workflow, fallback_model],
            global_retry_count=1,
            global_max_generation_count=-1,
            output_dir=Path("."),
            counter=counter,
        )

        async def fake_generate_text_to_image(self, prompt, count, workflow_config, runtime_config, output_dir, session):
            raise GenerationError("ComfyUI 连接失败")

        successful_adapter = types.SimpleNamespace(
            text_to_image=self._return_generated_path,
            image_to_image=self._return_generated_path,
        )

        with (
            patch(
                "astrbot_plugin_image_gateway.services.generation.ComfyUIWorkflowRunner.generate_text_to_image",
                fake_generate_text_to_image,
            ),
            patch(
                "astrbot_plugin_image_gateway.services.generation.get_adapter",
                return_value=successful_adapter,
            ),
            patch(
                "astrbot_plugin_image_gateway.services.generation.aiohttp.ClientSession",
                FakeClientSession,
            ),
        ):
            paths, target_name, _effective_send_strategy = await service.generate(
                mode="text_to_image", prompt="测试"
            )

        self.assertEqual(target_name, "FallbackModel")
        self.assertEqual(paths, [Path("fallback_generated.png")])

    async def _return_generated_path(self, *args, **kwargs):
        return [Path("fallback_generated.png")]

    async def test_from_config_reads_workflows_alongside_models(self) -> None:
        config = {
            "models": [
                {
                    "provider": "openai",
                    "display_name": "TestModel",
                    "priority": 1,
                }
            ],
            "workflows": [
                {
                    "display_name": "TestWorkflow",
                    "priority": 10,
                    "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
                }
            ],
        }
        service = GenerationService.from_config(config, Path("."), FakeCounter())

        self.assertEqual(len(service.targets), 2)
        self.assertEqual(service.targets[0].display_name, "TestWorkflow")
        self.assertEqual(service.targets[1].display_name, "TestModel")


if __name__ == "__main__":
    unittest.main()
