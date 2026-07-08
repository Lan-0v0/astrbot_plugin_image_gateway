from __future__ import annotations

import asyncio
import json
import os
import sys
import types
import time
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
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.saved_config: dict[str, Any] | None = None

        def save_config(self, replace_config=None, *, indent=2):
            if replace_config is not None:
                self.clear()
                self.update(replace_config)
            self.saved_config = json.loads(json.dumps(self))

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
    DEFAULT_START_MESSAGES,
    DEFAULT_LLM_CUSTOM_PERSONA_PROMPT,
    GenerationStartMessageConfig,
    ImageGatewayPlugin,
    StartMessageDispatchResult,
)
from astrbot_plugin_image_gateway.services.fake_forward import (  # noqa: E402
    FOLLOW_GLOBAL as FAKE_FORWARD_FOLLOW_GLOBAL,
    FakeForwardConfig,
    FakeForwardMode,
    parse_entry_fake_forward_mode,
    parse_global_fake_forward,
    resolve_effective_fake_forward,
)
from astrbot_plugin_image_gateway.services.generation import GenerationService  # noqa: E402
from astrbot_plugin_image_gateway.services.image_cache import (  # noqa: E402
    DEFAULT_IMAGE_CACHE_CLEANUP_DAYS,
    cleanup_expired_image_cache,
    parse_image_cache_cleanup_days,
)
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
from astrbot_plugin_image_gateway.services.workflow_runner import ComfyUIWorkflowRunner  # noqa: E402
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
        sender_name: str = "Test User",
        platform_id: str = "test-platform",
        platform_name: str = "aiocqhttp",
    ):
        self.message_str = message_text
        self.unified_msg_origin = "test-origin"
        self._group_id = group_id
        self._sender_id = sender_id
        self._sender_name = sender_name
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

    def get_sender_name(self):
        return self._sender_name

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
    def build_model(
        self,
        display_name: str,
        *,
        max_generation_count: int = -1,
        priority: int = 0,
    ) -> ModelConfig:
        return ModelConfig(
            provider="openai",
            display_name=display_name,
            url="https://example.com/v1",
            apikey="test-key",
            model_name="test-model",
            max_generation_count=max_generation_count,
            priority=priority,
        )

    async def test_returns_quota_error_only_when_all_models_are_exhausted(self) -> None:
        primary_model = self.build_model("Primary", max_generation_count=1)
        secondary_model = self.build_model("Secondary", max_generation_count=-1)
        counter = FakeCounter({primary_model.model_key(): 1})
        service = GenerationService(
            [primary_model, secondary_model],
            [],
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
            [],
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
            [],
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
            paths, model_name, _effective_send_strategy, _effective_fake_forward = await service.generate(
                mode="image_to_image", prompt="test prompt"
            )

        self.assertEqual(model_name, "Primary")
        self.assertEqual(paths, [Path("generated.png")])

    async def test_four_providers_fall_back_to_next_priority_provider_when_current_one_fails(self) -> None:
        provider_specs = [
            ("ProviderAlpha", 400),
            ("ProviderBeta", 300),
            ("ProviderGamma", 200),
            ("ProviderDelta", 100),
        ]

        for failing_index in range(len(provider_specs) - 1):
            failing_name, failing_priority = provider_specs[failing_index]
            expected_fallback_name, _expected_fallback_priority = provider_specs[failing_index + 1]

            with self.subTest(failing_provider=failing_name):
                models = [
                    self.build_model(
                        name,
                        priority=priority,
                        # Force higher-priority providers before the failing one to be skipped,
                        # so the chosen provider becomes the active candidate for this subtest.
                        max_generation_count=0 if index < failing_index else -1,
                    )
                    for index, (name, priority) in enumerate(provider_specs)
                ]
                attempted_providers: list[str] = []

                async def adapter_generate(_prompt, _count, target, _output_dir, _session):
                    attempted_providers.append(target.display_name)
                    if target.display_name == failing_name:
                        raise GenerationError("模拟当前提供商生成失败")
                    return [Path(f"{target.display_name}.png")]

                service = GenerationService(
                    models,
                    [],
                    global_retry_count=1,
                    global_max_generation_count=-1,
                    output_dir=Path("."),
                    counter=FakeCounter(),
                )
                adapter = types.SimpleNamespace(
                    text_to_image=adapter_generate,
                    image_to_image=adapter_generate,
                )

                with (
                    patch(
                        "astrbot_plugin_image_gateway.services.generation.get_adapter",
                        return_value=adapter,
                    ),
                    patch(
                        "astrbot_plugin_image_gateway.services.generation.aiohttp.ClientSession",
                        FakeClientSession,
                    ),
                ):
                    paths, provider_name, _effective_send_strategy, _effective_fake_forward = await service.generate(
                        mode="text_to_image",
                        prompt="test prompt",
                    )

                self.assertEqual(provider_name, expected_fallback_name)
                self.assertEqual(paths, [Path(f"{expected_fallback_name}.png")])
                self.assertEqual(attempted_providers, [failing_name, expected_fallback_name])

    async def test_generate_resolves_effective_fake_forward_from_global_config(self) -> None:
        model = self.build_model("Primary", priority=100)
        model.fake_forward_mode = FAKE_FORWARD_FOLLOW_GLOBAL

        service = GenerationService(
            [model],
            [],
            global_retry_count=1,
            global_max_generation_count=-1,
            output_dir=Path("."),
            counter=FakeCounter(),
            global_fake_forward=FakeForwardConfig(mode=FakeForwardMode.REQUESTER.value),
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
            _paths, _model_name, _effective_send_strategy, effective_fake_forward = await service.generate(
                mode="text_to_image",
                prompt="test prompt",
            )

        self.assertEqual(effective_fake_forward.mode, FakeForwardMode.REQUESTER.value)
        self.assertEqual(effective_fake_forward.custom_qq, "")

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

    def test_model_config_fake_forward_defaults_to_follow_global(self) -> None:
        model_config = ModelConfig.from_template_entry({"provider": "openai"})
        self.assertEqual(model_config.fake_forward_mode, FAKE_FORWARD_FOLLOW_GLOBAL)
        self.assertEqual(model_config.fake_forward_custom_qq, "")

    def test_model_config_fake_forward_parses_explicit_value(self) -> None:
        model_config = ModelConfig.from_template_entry(
            {
                "provider": "openai",
                "fake_forward_mode": "custom_qq",
                "fake_forward_custom_qq": "QQ: 123456abc",
            }
        )
        self.assertEqual(model_config.fake_forward_mode, FakeForwardMode.CUSTOM_QQ.value)
        self.assertEqual(model_config.fake_forward_custom_qq, "123456")

    def test_generation_service_from_config_uses_new_global_defaults(self) -> None:
        generation_service = GenerationService.from_config({}, Path("."), FakeCounter())
        self.assertEqual(generation_service.global_retry_count, 2)
        self.assertEqual(generation_service.global_max_generation_count, 2)
        self.assertEqual(generation_service.global_send_strategy, SendStrategy.DIRECT_FIRST)
        self.assertEqual(generation_service.global_fake_forward.mode, FakeForwardMode.OFF.value)
        self.assertEqual(generation_service.global_fake_forward.custom_qq, "")

    def test_parse_image_cache_cleanup_days_uses_default_when_missing(self) -> None:
        self.assertEqual(
            parse_image_cache_cleanup_days(None),
            DEFAULT_IMAGE_CACHE_CLEANUP_DAYS,
        )

    def test_parse_image_cache_cleanup_days_allows_blank_to_disable_cleanup(self) -> None:
        self.assertEqual(parse_image_cache_cleanup_days(""), None)
        self.assertEqual(parse_image_cache_cleanup_days("   "), None)

    def test_load_start_message_config_uses_default_custom_persona_prompt(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        start_message_config = plugin_instance._load_start_message_config(
            {"mode": "llm", "llm_persona_source": "custom"}
        )
        self.assertEqual(
            start_message_config.llm_custom_persona_prompt,
            DEFAULT_LLM_CUSTOM_PERSONA_PROMPT,
        )
        self.assertEqual(
            DEFAULT_LLM_CUSTOM_PERSONA_PROMPT,
            "根据现在的情景，以适宜的性格言语，简单表述要开始生成图片了，不分段不加格式，10字以内，结尾不加标点符号换成颜文字表情，严禁使用emoji。",
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
        plugin_instance.generation_service.validate_request_count = (
            lambda requested_count, mode="text_to_image": (_ for _ in ()).throw(
                GenerationError("超出生成张数上限")
            )
        )

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


    async def test_run_generation_passes_request_mode_to_validate_request_count(self) -> None:
        observed_modes: list[str] = []
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance._refresh_services = lambda: None
        plugin_instance.generation_service = types.SimpleNamespace(
            _normalize_requested_count=lambda mode, count: 1,
            validate_request_count=lambda requested_count, mode="text_to_image": observed_modes.append(mode),
            generate=self._raise_generation_error("stop after validation"),
        )
        async def start_message_result(event, label):
            return StartMessageDispatchResult(text="开始生成", message_id="1", sent_passively=False)

        async def noop_retract_start_message(event, message_id):
            return None

        plugin_instance._send_start_message = start_message_result
        plugin_instance._retract_start_message = noop_retract_start_message

        results = []
        async for result in plugin_instance._run_generation(
            FakeEvent("/改图 测试"),
            mode="image_to_image",
            prompt="测试",
            count=1,
            input_images=["stub-image"],
            success_label="改图",
        ):
            results.append(result)

        self.assertEqual(results, ["stop after validation"])
        self.assertEqual(observed_modes, ["image_to_image"])

    def test_refresh_services_reads_image_cache_cleanup_days_and_triggers_cleanup(self) -> None:
        cleanup_calls: list[tuple[Path, int | None]] = []
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance.context = None
        plugin_instance.plugin_config = {"image_cache_cleanup_days": "14"}
        plugin_instance._last_image_cache_cleanup_at = 0.0
        plugin_instance._load_start_message_config = lambda raw_config: "start-config"
        temp_data_dir = Path(self.id().replace(".", "_"))
        if temp_data_dir.exists():
            for existing_path in temp_data_dir.rglob("*"):
                if existing_path.is_file():
                    existing_path.unlink()
            for existing_dir in sorted(temp_data_dir.rglob("*"), reverse=True):
                if existing_dir.is_dir():
                    existing_dir.rmdir()
            temp_data_dir.rmdir()

        def fake_cleanup(images_dir: Path) -> None:
            cleanup_calls.append((images_dir, plugin_instance.image_cache_cleanup_days))

        plugin_instance._maybe_cleanup_image_cache = fake_cleanup

        with patch(
            "astrbot_plugin_image_gateway.main.StarTools.get_data_dir",
            return_value=temp_data_dir,
        ):
            with patch(
                "astrbot_plugin_image_gateway.main.GenerationService.from_config",
                return_value="generation-service",
            ):
                plugin_instance._refresh_services()

        self.assertEqual(plugin_instance.image_cache_cleanup_days, 14)
        self.assertEqual(plugin_instance.generation_service, "generation-service")
        self.assertEqual(plugin_instance.start_message_config, "start-config")
        self.assertEqual(len(cleanup_calls), 1)
        for existing_path in temp_data_dir.rglob("*"):
            if existing_path.is_file():
                existing_path.unlink()
        for existing_dir in sorted(temp_data_dir.rglob("*"), reverse=True):
            if existing_dir.is_dir():
                existing_dir.rmdir()
        temp_data_dir.rmdir()

    @staticmethod
    def _raise_generation_error(message: str):
        async def generate(**kwargs):
            raise GenerationError(message)

        return generate


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
        plugin_instance.generation_service.validate_request_count = (
            lambda requested_count, mode="text_to_image": None
        )

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

    async def test_run_generation_fake_forward_merges_success_text_instead_of_start_message(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance._refresh_services = lambda: None
        plugin_instance.context = types.SimpleNamespace(get_config=lambda: {})
        plugin_instance.global_send_strategy = SendStrategy.DIRECT_FIRST
        plugin_instance.generation_service = types.SimpleNamespace(
            _normalize_requested_count=lambda mode, count: 1,
            validate_request_count=lambda requested_count: None,
            generate=self._build_generate_result(
                [Path("generated.png")],
                fake_forward_config=FakeForwardConfig(mode=FakeForwardMode.REQUESTER.value),
            ),
        )

        async def build_image_component(image_path: str):
            return f"image:{image_path}"

        async def retract_start_message(event, message_id):
            return None

        plugin_instance._build_image_component = build_image_component
        plugin_instance._send_start_message = self._build_start_message_result
        plugin_instance._retract_start_message = retract_start_message
        plugin_instance.generation_service.validate_request_count = (
            lambda requested_count, mode="text_to_image": None
        )

        event = FakeEvent("/生图 测试", sender_id="24680", sender_name="Requester")
        event.sent_messages = []

        async def send(message_chain):
            event.sent_messages.append(list(message_chain))

        event.send = send

        results = []
        async for result in plugin_instance._run_generation(
            event,
            mode="text_to_image",
            prompt="测试",
            count=1,
            success_label="生图",
        ):
            results.append(result)

        self.assertEqual(results, [])
        self.assertEqual(len(event.sent_messages), 1)
        merged_nodes = event.sent_messages[0][0].nodes
        self.assertEqual(len(merged_nodes), 2)
        self.assertTrue(merged_nodes[0].content[0].text.startswith("生图成功，用时"))
        self.assertNotIn("开始生成", merged_nodes[0].content[0].text)
        self.assertEqual(merged_nodes[1].content[-1], "image:generated.png")

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
        plugin_instance.generation_service.validate_request_count = (
            lambda requested_count, mode="text_to_image": None
        )

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

    async def test_build_fake_forward_chain_uses_requester_identity(self) -> None:
        plugin_instance = object.__new__(ImageGatewayPlugin)
        plugin_instance.context = types.SimpleNamespace(get_config=lambda: {})

        async def build_image_component(image_path: str):
            return f"image:{image_path}"

        plugin_instance._build_image_component = build_image_component

        event = FakeEvent("/生图 测试", sender_id="24680", sender_name="Requester")
        chain = await plugin_instance._build_fake_forward_chain(
            event,
            "开始生成",
            ["generated.png"],
            FakeForwardConfig(mode=FakeForwardMode.REQUESTER.value),
        )

        self.assertEqual(len(chain), 1)
        nodes = chain[0].nodes
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].uin, "24680")
        self.assertEqual(nodes[0].name, "Requester")
        self.assertEqual(nodes[0].content[0].text, "开始生成")
        self.assertEqual(nodes[1].content[-1], "image:generated.png")

    @staticmethod
    def _build_generate_result(
        paths: list[Path],
        *,
        fake_forward_config: FakeForwardConfig | None = None,
    ):
        async def generate(**kwargs):
            return paths, "Test Model", SendStrategy.DIRECT_FIRST, (fake_forward_config or FakeForwardConfig())

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

    def test_openai_image_to_image_rejects_invalid_base64_input(self) -> None:
        adapter = OpenAIAdapter()
        model = ModelConfig(
            provider="openai",
            display_name="OpenAI",
            url="https://example.com/v1",
            apikey="test-key",
            model_name="test-model",
        )

        with self.assertRaises(GenerationError) as raised_error:
            asyncio.run(
                adapter.image_to_image(
                    "测试",
                    ["not-valid-base64"],
                    model,
                    Path("."),
                    FakeClientSession(),
                )
            )

        self.assertEqual(str(raised_error.exception), "输入图片不是有效的 base64 数据")


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


class FakeForwardRegressionTests(unittest.TestCase):
    def test_parse_global_fake_forward_defaults_to_off(self) -> None:
        config = parse_global_fake_forward(None)
        self.assertEqual(config.mode, FakeForwardMode.OFF.value)
        self.assertEqual(config.custom_qq, "")
        self.assertEqual(config.enabled, False)

    def test_parse_global_fake_forward_custom_qq_normalizes_digits(self) -> None:
        config = parse_global_fake_forward({"mode": "custom_qq", "custom_qq": "QQ 12a34b56"})
        self.assertEqual(config.mode, FakeForwardMode.CUSTOM_QQ.value)
        self.assertEqual(config.custom_qq, "123456")
        self.assertEqual(config.enabled, True)

    def test_parse_entry_fake_forward_mode_defaults_to_follow_global(self) -> None:
        self.assertEqual(parse_entry_fake_forward_mode(None), FAKE_FORWARD_FOLLOW_GLOBAL)
        self.assertEqual(parse_entry_fake_forward_mode(""), FAKE_FORWARD_FOLLOW_GLOBAL)
        self.assertEqual(parse_entry_fake_forward_mode("not-a-real-mode"), FAKE_FORWARD_FOLLOW_GLOBAL)

    def test_resolve_effective_fake_forward_follows_global(self) -> None:
        effective_config = resolve_effective_fake_forward(
            global_config=FakeForwardConfig(
                mode=FakeForwardMode.REQUESTER.value,
                custom_qq="",
            ),
            entry_mode=FAKE_FORWARD_FOLLOW_GLOBAL,
            entry_custom_qq="",
        )
        self.assertEqual(effective_config.mode, FakeForwardMode.REQUESTER.value)
        self.assertEqual(effective_config.custom_qq, "")

    def test_resolve_effective_fake_forward_requires_custom_qq_value(self) -> None:
        effective_config = resolve_effective_fake_forward(
            global_config=FakeForwardConfig(
                mode=FakeForwardMode.BOT_SELF.value,
                custom_qq="",
            ),
            entry_mode=FakeForwardMode.CUSTOM_QQ.value,
            entry_custom_qq="",
        )
        self.assertEqual(effective_config.mode, FakeForwardMode.OFF.value)
        self.assertEqual(effective_config.custom_qq, "")


class ImageCacheCleanupRegressionTests(unittest.TestCase):
    def test_parse_image_cache_cleanup_days_parses_positive_integer(self) -> None:
        self.assertEqual(parse_image_cache_cleanup_days("14"), 14)
        self.assertEqual(parse_image_cache_cleanup_days(3), 3)

    def test_parse_image_cache_cleanup_days_disables_cleanup_for_non_positive_values(self) -> None:
        self.assertEqual(parse_image_cache_cleanup_days("0"), None)
        self.assertEqual(parse_image_cache_cleanup_days(-1), None)

    def test_cleanup_expired_image_cache_deletes_only_expired_files(self) -> None:
        temp_dir = Path(self.id().replace(".", "_"))
        if temp_dir.exists():
            for existing_path in temp_dir.rglob("*"):
                if existing_path.is_file():
                    existing_path.unlink()
            for existing_dir in sorted(temp_dir.rglob("*"), reverse=True):
                if existing_dir.is_dir():
                    existing_dir.rmdir()
            temp_dir.rmdir()

        images_dir = temp_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        expired_file = images_dir / "expired.png"
        fresh_file = images_dir / "fresh.png"
        expired_file.write_bytes(b"old")
        fresh_file.write_bytes(b"new")

        current_time = time.time()
        expired_mtime = current_time - (8 * 86400)
        fresh_mtime = current_time - (2 * 86400)
        expired_file.touch()
        fresh_file.touch()
        os.utime(expired_file, (expired_mtime, expired_mtime))
        os.utime(fresh_file, (fresh_mtime, fresh_mtime))

        deleted_count = cleanup_expired_image_cache(
            images_dir,
            retention_days=7,
            now=current_time,
        )

        self.assertEqual(deleted_count, 1)
        self.assertEqual(expired_file.exists(), False)
        self.assertEqual(fresh_file.exists(), True)

        fresh_file.unlink()
        images_dir.rmdir()
        temp_dir.rmdir()


class WorkflowConfigRegressionTests(unittest.TestCase):
    def test_conf_schema_uses_provider_names_for_model_templates(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        self.assertEqual(schema["models"]["templates"]["openai"]["name"], "OpenAI")
        self.assertEqual(schema["models"]["templates"]["gemini"]["name"], "Gemini")

    def test_conf_schema_moves_prompt_and_image_usage_help_into_binding_type_hint(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        binding_items = schema["workflow_node_bindings"]["templates"]["binding"]["items"]
        binding_type = binding_items["binding_type"]

        self.assertIn("正向提示词", binding_type["hint"])
        self.assertIn("/生图 /改图", binding_type["hint"])
        self.assertIn("图片输入", binding_type["hint"])
        self.assertIn("双模式工作流", binding_type["hint"])
        self.assertIn("模式切换数值", binding_type["hint"])
        self.assertIn("模式切换 JSON", binding_type["hint"])
        self.assertNotIn("prompt_positive_help", binding_items)
        self.assertNotIn("image_input_help", binding_items)

    def test_conf_schema_describes_workflow_binding_as_dual_locator_rules(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        bindings_section = schema["workflow_node_bindings"]
        self.assertIn("节点ID+字段路径双重定位", bindings_section["hint"])

    def helper_conf_schema_removes_workflow_type_and_keeps_supported_modes(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        workflow_items = schema["workflows"]["templates"]["comfyui"]["items"]

        self.assertNotIn("workflow_type_label", workflow_items)
        self.assertEqual(workflow_items["workflow_type"]["description"], "类型")
        self.assertEqual(workflow_items["workflow_type"]["options"], ["comfyui"])
        self.assertEqual(workflow_items["workflow_type"]["labels"], ["ComfyUI"])
        self.assertEqual(
            workflow_items["supported_modes"]["options"],
            ["text_to_image", "both", "image_to_image"],
        )
        self.assertEqual(
            workflow_items["supported_modes"]["labels"],
            ["仅文生图", "文生图 + 改图", "仅改图"],
        )

    def test_conf_schema_removes_workflow_type_and_keeps_supported_modes_v134(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        workflow_items = schema["workflows"]["templates"]["comfyui"]["items"]

        self.assertNotIn("workflow_type_label", workflow_items)
        self.assertNotIn("workflow_type", workflow_items)
        self.assertEqual(
            workflow_items["supported_modes"]["options"],
            ["text_to_image", "both", "image_to_image"],
        )

    def test_conf_schema_uses_workflow_id_as_workflow_display_item(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        workflow_template = schema["workflows"]["templates"]["comfyui"]
        workflow_items = workflow_template["items"]

        self.assertEqual(workflow_template["display_item"], "workflow_id")
        self.assertNotIn("hide_hint_in_list", workflow_template)
        self.assertNotIn("display_name", workflow_items)
        self.assertEqual(
            workflow_template["hint"],
            "工作流 ID (workflow_id)输入框中输入的内容变量",
        )
        self.assertEqual(
            workflow_items["workflow_id"]["hint"],
            "用于关联下方“工作流自定义节点条目”，可输入任意中文/英文/符号作为名称。",
        )

    def test_conf_schema_uses_plugin_managed_binding_display_summary(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        binding_template = schema["workflow_node_bindings"]["templates"]["binding"]
        binding_items = binding_template["items"]

        self.assertEqual(binding_template["display_item"], ["display_summary"])
        self.assertTrue(binding_items["display_summary"]["invisible"])
        self.assertIn("CFG", binding_items["display_name"]["hint"])

    def test_plugin_normalizes_binding_display_summary_and_persists_config(self) -> None:
        config_cls = sys.modules["astrbot.api"].AstrBotConfig
        config = config_cls(
            {
                "workflow_node_bindings": [
                    {
                        "__template_key": "binding",
                        "display_name": "?????",
                        "workflow_id": "miaomiao??",
                        "node_id": "85",
                        "field_path": "inputs.text",
                        "binding_type": "prompt_positive",
                    }
                ]
            }
        )

        context_cls = sys.modules["astrbot.api.star"].Context
        plugin = ImageGatewayPlugin(context_cls(), config)

        binding_entry = plugin.plugin_config["workflow_node_bindings"][0]
        expected_summary = plugin._build_workflow_binding_display_summary(
            {
                "display_name": "?????",
                "workflow_id": "miaomiao??",
            }
        )
        self.assertEqual(binding_entry["display_summary"], expected_summary)
        self.assertIsNotNone(config.saved_config)
        self.assertEqual(
            config.saved_config["workflow_node_bindings"][0]["display_summary"],
            expected_summary,
        )

    def test_conf_schema_exposes_fake_forward_options_for_models_and_workflows(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        model_items = schema["models"]["templates"]["openai"]["items"]
        workflow_items = schema["workflows"]["templates"]["comfyui"]["items"]
        global_items = schema["fake_forward"]["items"]

        self.assertEqual(global_items["mode"]["options"], ["off", "bot_self", "requester", "custom_qq"])
        self.assertEqual(
            model_items["fake_forward_mode"]["options"],
            ["follow_global", "off", "bot_self", "requester", "custom_qq"],
        )
        self.assertEqual(
            workflow_items["fake_forward_mode"]["options"],
            ["follow_global", "off", "bot_self", "requester", "custom_qq"],
        )
        self.assertEqual(
            model_items["fake_forward_custom_qq"]["condition"],
            {"fake_forward_mode": "custom_qq"},
        )
        self.assertEqual(
            workflow_items["fake_forward_custom_qq"]["condition"],
            {"fake_forward_mode": "custom_qq"},
        )

    def test_conf_schema_exposes_image_cache_cleanup_between_fake_forward_and_send_strategy(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        schema_keys = list(schema.keys())
        self.assertLess(schema_keys.index("fake_forward"), schema_keys.index("image_cache_cleanup_days"))
        self.assertLess(schema_keys.index("image_cache_cleanup_days"), schema_keys.index("send_strategy"))
        self.assertEqual(schema["image_cache_cleanup_days"]["default"], "7")
        self.assertEqual(schema["image_cache_cleanup_days"]["type"], "string")

    def test_conf_schema_documents_priority_preset_numeric_values(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        model_priority_hint = schema["models"]["templates"]["openai"]["items"]["priority"]["hint"]
        workflow_priority_hint = schema["workflows"]["templates"]["comfyui"]["items"]["priority"]["hint"]

        for hint in (model_priority_hint, workflow_priority_hint):
            self.assertIn("最高=40", hint)
            self.assertIn("高=30", hint)
            self.assertIn("普通=20", hint)
            self.assertIn("低=10", hint)
            self.assertIn("最低=0", hint)

    def test_conf_schema_fixed_message_default_matches_code_default(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        fixed_messages = schema["generation_start_message"]["items"]["fixed_messages"]["default"]
        fixed_messages_hint = schema["generation_start_message"]["items"]["fixed_messages"]["hint"]

        self.assertEqual(DEFAULT_START_MESSAGES, ["开始生成0v0~"])
        self.assertEqual(fixed_messages, DEFAULT_START_MESSAGES)
        self.assertIn("开始生成0v0~", fixed_messages_hint)

    def test_conf_schema_llm_prompt_default_matches_code_default(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        llm_prompt_default = schema["generation_start_message"]["items"]["llm_custom_persona_prompt"]["default"]

        self.assertEqual(llm_prompt_default, DEFAULT_LLM_CUSTOM_PERSONA_PROMPT)
        self.assertIn("颜文字表情", llm_prompt_default)
        self.assertIn("严禁使用emoji", llm_prompt_default)

    def test_workflow_runtime_default_timeout_matches_schema_default(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        runtime_timeout_default = schema["workflow_runtime_default"]["items"]["timeout_seconds"]["default"]
        runtime_config = WorkflowRuntimeConfig.from_raw({})

        self.assertEqual(runtime_timeout_default, 300)
        self.assertEqual(runtime_config.timeout_seconds, 300)
        self.assertEqual(runtime_config.base_url, "http://127.0.0.1:8188")

    def test_conf_schema_exposes_mode_switch_fields_with_direct_conditions(self) -> None:
        schema = json.loads((repository_root / "_conf_schema.json").read_text(encoding="utf-8"))

        binding_items = schema["workflow_node_bindings"]["templates"]["binding"]["items"]

        self.assertTrue(binding_items["text_to_image_value"]["invisible"])
        self.assertTrue(binding_items["image_to_image_value"]["invisible"])
        self.assertEqual(
            binding_items["mode_switch_text_text_to_image_value"]["condition"],
            {"binding_type": "mode_switch_text"},
        )
        self.assertEqual(
            binding_items["mode_switch_text_image_to_image_value"]["condition"],
            {"binding_type": "mode_switch_text"},
        )
        self.assertEqual(
            binding_items["mode_switch_number_text_to_image_value"]["condition"],
            {"binding_type": "mode_switch_number"},
        )
        self.assertEqual(
            binding_items["mode_switch_number_image_to_image_value"]["condition"],
            {"binding_type": "mode_switch_number"},
        )
        self.assertEqual(
            binding_items["mode_switch_json_text_to_image_value"]["condition"],
            {"binding_type": "mode_switch_json"},
        )
        self.assertEqual(
            binding_items["mode_switch_json_image_to_image_value"]["condition"],
            {"binding_type": "mode_switch_json"},
        )

    def test_workflow_node_binding_from_template_entry_falls_back_to_custom_text(self) -> None:
        node_binding = WorkflowNodeBinding.from_template_entry(
            {
                "workflow_id": "portrait_flux",
                "node_id": "6",
                "field_path": "inputs.text",
                "binding_type": "not-a-real-type",
            }
        )
        self.assertEqual(node_binding.workflow_id, "portrait_flux")
        self.assertEqual(node_binding.binding_type, "custom_text")

    def helper_from_template_entry_parses_bindings_and_defaults(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {
                "workflow_id": "portrait_flux",
                "display_name": "我的 ComfyUI 工作流",
                "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
            }
        )

        self.assertEqual(workflow_config.workflow_id, "portrait_flux")
        self.assertEqual(workflow_config.workflow_type, "comfyui")
        self.assertEqual(workflow_config.kind, "workflow")
        self.assertEqual(workflow_config.send_strategy, FOLLOW_GLOBAL)
        self.assertEqual(workflow_config.supported_modes, ["text_to_image"])

    def test_from_template_entry_parses_bindings_defaults_and_fake_forward(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {
                "workflow_id": "portrait_flux",
                "display_name": "My ComfyUI Workflow",
                "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
                "fake_forward_mode": "custom_qq",
                "fake_forward_custom_qq": "qq: 778899",
            }
        )

        self.assertEqual(workflow_config.workflow_id, "portrait_flux")
        self.assertEqual(workflow_config.display_name, "portrait_flux")
        self.assertEqual(workflow_config.kind, "workflow")
        self.assertEqual(workflow_config.send_strategy, FOLLOW_GLOBAL)
        self.assertEqual(workflow_config.fake_forward_mode, FakeForwardMode.CUSTOM_QQ.value)
        self.assertEqual(workflow_config.fake_forward_custom_qq, "778899")
        self.assertEqual(workflow_config.supported_modes, ["text_to_image"])

    def test_from_template_entry_uses_workflow_id_as_display_name(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {
                "workflow_id": "portrait_flux",
                "display_name": "旧显示名称",
                "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
            }
        )

        self.assertEqual(workflow_config.workflow_id, "portrait_flux")
        self.assertEqual(workflow_config.display_name, "portrait_flux")

    def test_from_template_entry_falls_back_to_display_name_as_workflow_id(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {
                "display_name": "默认工作流ID",
                "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
            }
        )

        self.assertEqual(workflow_config.workflow_id, "默认工作流ID")
        self.assertEqual(workflow_config.display_name, "默认工作流ID")

    def helper_from_template_entry_falls_back_to_comfyui_for_unknown_workflow_type(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry({"workflow_type": "unknown-engine"})
        self.assertEqual(workflow_config.workflow_type, "comfyui")

    def test_from_template_entry_reads_supported_modes_for_dual_entry_workflow(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {
                "workflow_id": "dual-entry",
                "supported_modes": ["text_to_image", "image_to_image", "invalid-mode"],
            }
        )

        self.assertTrue(workflow_config.supports_mode("text_to_image"))
        self.assertTrue(workflow_config.supports_mode("image_to_image"))
        self.assertEqual(workflow_config.supported_modes, ["text_to_image", "image_to_image"])

    def test_from_template_entry_reads_supported_modes_for_image_to_image_only_workflow(self) -> None:
        workflow_config = WorkflowConfig.from_template_entry(
            {
                "workflow_id": "img2img-only",
                "supported_modes": "image_to_image",
            }
        )

        self.assertFalse(workflow_config.supports_mode("text_to_image"))
        self.assertTrue(workflow_config.supports_mode("image_to_image"))
        self.assertEqual(workflow_config.supported_modes, ["image_to_image"])

    def test_workflow_node_binding_reads_mode_switch_values(self) -> None:
        node_binding = WorkflowNodeBinding.from_template_entry(
            {
                "workflow_id": "dual-entry",
                "node_id": "31",
                "field_path": "inputs.latent_image",
                "binding_type": "mode_switch_json",
                "text_to_image_value": "[\"23\", 0]",
                "image_to_image_value": "[\"225\", 0]",
            }
        )

        self.assertEqual(node_binding.binding_type, "mode_switch_json")
        self.assertEqual(node_binding.text_to_image_value, "[\"23\", 0]")
        self.assertEqual(node_binding.image_to_image_value, "[\"225\", 0]")

    def test_workflow_node_binding_reads_type_specific_mode_switch_fields(self) -> None:
        node_binding = WorkflowNodeBinding.from_template_entry(
            {
                "workflow_id": "dual-entry",
                "node_id": "206",
                "field_path": "inputs.denoise",
                "binding_type": "mode_switch_number",
                "mode_switch_number_text_to_image_value": "1.0",
                "mode_switch_number_image_to_image_value": "0.45",
            }
        )

        self.assertEqual(node_binding.binding_type, "mode_switch_number")
        self.assertEqual(node_binding.text_to_image_value, "1.0")
        self.assertEqual(node_binding.image_to_image_value, "0.45")

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
    ) -> WorkflowConfig:
        return WorkflowConfig.from_template_entry(
            {
                "workflow_id": "portrait_flux",
                "display_name": "测试工作流",
                "workflow_content": json.dumps(workflow_payload),
            }
        )

    def test_merge_overwrites_positive_prompt_via_node_id_and_field_path(self) -> None:
        workflow_config = self.build_workflow_config(
            {"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "placeholder", "clip": ["4", 1]}}},
        )

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="6",
                field_path="inputs.text",
                binding_type="prompt_positive",
            )
        ]

        merged_payload = merge_workflow_payload(
            workflow_config,
            node_bindings,
            positive_prompt="一只猫在草地上奔跑",
        )

        self.assertEqual(merged_payload["6"]["inputs"]["text"], "一只猫在草地上奔跑")
        self.assertEqual(merged_payload["6"]["inputs"]["clip"], ["4", 1])

    def test_merge_overwrites_list_index_field_path(self) -> None:
        workflow_config = self.build_workflow_config({"9": {"inputs": {"texts": ["old-a", "old-b"]}}})

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="9",
                field_path="inputs.texts.1",
                binding_type="custom_text",
                custom_value="new-b",
            )
        ]

        merged_payload = merge_workflow_payload(workflow_config, node_bindings, positive_prompt="unused")

        self.assertEqual(merged_payload["9"]["inputs"]["texts"], ["old-a", "new-b"])

    def test_merge_custom_number_keeps_numeric_type_not_string(self) -> None:
        workflow_config = self.build_workflow_config({"3": {"inputs": {"cfg": 7.0, "steps": 20}}})

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="3",
                field_path="inputs.cfg",
                binding_type="custom_number",
                custom_value="4.5",
            ),
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="3",
                field_path="inputs.steps",
                binding_type="custom_number",
                custom_value="30",
            ),
        ]

        merged_payload = merge_workflow_payload(workflow_config, node_bindings, positive_prompt="unused")

        self.assertEqual(merged_payload["3"]["inputs"]["cfg"], 4.5)
        self.assertIsInstance(merged_payload["3"]["inputs"]["cfg"], float)
        self.assertEqual(merged_payload["3"]["inputs"]["steps"], 30)
        self.assertIsInstance(merged_payload["3"]["inputs"]["steps"], int)

    def test_merge_random_seed_when_custom_value_is_empty(self) -> None:
        workflow_config = self.build_workflow_config({"3": {"inputs": {"seed": 0}}})

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="3",
                field_path="inputs.seed",
                binding_type="seed",
                custom_value="",
            )
        ]

        merged_payload = merge_workflow_payload(workflow_config, node_bindings, positive_prompt="unused")

        self.assertIsInstance(merged_payload["3"]["inputs"]["seed"], int)

    def test_merge_raises_generation_error_for_missing_node(self) -> None:
        workflow_config = self.build_workflow_config({"6": {"inputs": {"text": "placeholder"}}})

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="999",
                field_path="inputs.text",
                binding_type="prompt_positive",
            )
        ]

        with self.assertRaises(GenerationError):
            merge_workflow_payload(workflow_config, node_bindings, positive_prompt="不会用到")

    def test_merge_raises_generation_error_for_invalid_field_path(self) -> None:
        workflow_config = self.build_workflow_config({"6": {"inputs": {"text": "placeholder"}}})

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="6",
                field_path="inputs.missing_field",
                binding_type="prompt_positive",
            )
        ]

        with self.assertRaises(GenerationError):
            merge_workflow_payload(workflow_config, node_bindings, positive_prompt="不会用到")

    def test_merge_skips_image_input_binding_when_no_images_provided(self) -> None:
        workflow_config = self.build_workflow_config({"10": {"inputs": {"image": "placeholder.png"}}})

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="10",
                field_path="inputs.image",
                binding_type="image_input",
            )
        ]

        merged_payload = merge_workflow_payload(
            workflow_config,
            node_bindings,
            positive_prompt="unused",
            input_images=None,
        )

        self.assertEqual(merged_payload["10"]["inputs"]["image"], "placeholder.png")

    def test_merge_mode_switch_number_uses_request_mode(self) -> None:
        workflow_config = self.build_workflow_config({"31": {"inputs": {"denoise": 1.0}}})

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="31",
                field_path="inputs.denoise",
                binding_type="mode_switch_number",
                text_to_image_value="1.0",
                image_to_image_value="0.45",
            )
        ]

        text_to_image_payload = merge_workflow_payload(
            workflow_config,
            node_bindings,
            mode="text_to_image",
            positive_prompt="unused",
        )
        image_to_image_payload = merge_workflow_payload(
            workflow_config,
            node_bindings,
            mode="image_to_image",
            positive_prompt="unused",
        )

        self.assertEqual(text_to_image_payload["31"]["inputs"]["denoise"], 1.0)
        self.assertEqual(image_to_image_payload["31"]["inputs"]["denoise"], 0.45)

    def test_merge_mode_switch_json_can_rewire_comfyui_links(self) -> None:
        workflow_config = self.build_workflow_config({"31": {"inputs": {"latent_image": ["23", 0]}}})

        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="portrait_flux",
                node_id="31",
                field_path="inputs.latent_image",
                binding_type="mode_switch_json",
                text_to_image_value="[\"23\", 0]",
                image_to_image_value="[\"225\", 0]",
            )
        ]

        merged_payload = merge_workflow_payload(
            workflow_config,
            node_bindings,
            mode="image_to_image",
            positive_prompt="unused",
        )

        self.assertEqual(merged_payload["31"]["inputs"]["latent_image"], ["225", 0])


class ComfyUIWorkflowRunnerRegressionTests(unittest.IsolatedAsyncioTestCase):
    class FakeResponse:
        def __init__(self, *, status: int = 200, json_data: Any = None, body: bytes = b""):
            self.status = status
            self._json_data = json_data
            self._body = body

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def json(self, content_type=None):
            return self._json_data

        async def read(self):
            return self._body

    class FakeSession:
        def __init__(self):
            self.posts: list[tuple[str, dict[str, Any]]] = []
            self.gets: list[tuple[str, dict[str, Any]]] = []

        def post(self, url: str, **kwargs):
            self.posts.append((url, kwargs))
            if url.endswith("/upload/image"):
                return ComfyUIWorkflowRunnerRegressionTests.FakeResponse(
                    json_data={"name": "uploaded.png"}
                )
            if url.endswith("/prompt"):
                return ComfyUIWorkflowRunnerRegressionTests.FakeResponse(
                    json_data={"prompt_id": "prompt-123"}
                )
            return ComfyUIWorkflowRunnerRegressionTests.FakeResponse(status=404, json_data={})

        def get(self, url: str, **kwargs):
            self.gets.append((url, kwargs))
            if "/history/" in url:
                return ComfyUIWorkflowRunnerRegressionTests.FakeResponse(
                    json_data={
                        "prompt-123": {
                            "outputs": {
                                "save": {
                                    "images": [
                                        {"filename": "out.png", "subfolder": "", "type": "output"}
                                    ]
                                }
                            }
                        }
                    }
                )
            if url.endswith("/view"):
                return ComfyUIWorkflowRunnerRegressionTests.FakeResponse(body=b"image-bytes")
            return ComfyUIWorkflowRunnerRegressionTests.FakeResponse(status=404, json_data={})

    def build_workflow_config(self, supported_modes: list[str] | None = None) -> WorkflowConfig:
        workflow_payload = {
            "23": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
            "31": {"inputs": {"latent_image": ["23", 0], "denoise": 1.0}},
            "222": {"inputs": {"image": "placeholder.png"}},
            "225": {"inputs": {"pixels": ["222", 0], "vae": ["51", 2]}},
            "51": {"inputs": {}},
        }
        return WorkflowConfig.from_template_entry(
            {
                "workflow_id": "dual-entry",
                "display_name": "Dual Entry Workflow",
                "supported_modes": supported_modes or ["text_to_image", "image_to_image"],
                "workflow_content": json.dumps(workflow_payload),
            }
        )

    async def test_generate_image_to_image_uploads_image_and_rewires_dual_entry_workflow(self) -> None:
        runner = ComfyUIWorkflowRunner()
        session = self.FakeSession()
        workflow_config = self.build_workflow_config()
        node_bindings = [
            WorkflowNodeBinding(
                workflow_id="dual-entry",
                node_id="222",
                field_path="inputs.image",
                binding_type="image_input",
            ),
            WorkflowNodeBinding(
                workflow_id="dual-entry",
                node_id="31",
                field_path="inputs.latent_image",
                binding_type="mode_switch_json",
                text_to_image_value="[\"23\", 0]",
                image_to_image_value="[\"225\", 0]",
            ),
            WorkflowNodeBinding(
                workflow_id="dual-entry",
                node_id="31",
                field_path="inputs.denoise",
                binding_type="mode_switch_number",
                text_to_image_value="1.0",
                image_to_image_value="0.45",
            ),
        ]

        paths = await runner.generate_image_to_image(
            "test",
            ["data:image/png;base64,aGVsbG8="],
            workflow_config,
            node_bindings,
            WorkflowRuntimeConfig(),
            Path("."),
            session,
        )

        self.assertEqual(len(paths), 1)
        prompt_posts = [kwargs for url, kwargs in session.posts if url.endswith("/prompt")]
        self.assertEqual(len(prompt_posts), 1)
        prompt_payload = prompt_posts[0]["json"]["prompt"]
        self.assertEqual(prompt_payload["222"]["inputs"]["image"], "uploaded.png")
        self.assertEqual(prompt_payload["31"]["inputs"]["latent_image"], ["225", 0])
        self.assertEqual(prompt_payload["31"]["inputs"]["denoise"], 0.45)

class MixedTargetSchedulingRegressionTests(unittest.IsolatedAsyncioTestCase):
    def build_workflow(
        self,
        display_name: str,
        *,
        priority: int = 0,
        supported_modes: list[str] | None = None,
    ) -> WorkflowConfig:
        return WorkflowConfig.from_template_entry(
            {
                "workflow_id": display_name,
                "priority": priority,
                "supported_modes": supported_modes or ["text_to_image"],
                "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
            }
        )

    def build_model(
        self,
        display_name: str,
        *,
        priority: int = 0,
        max_generation_count: int = -1,
    ) -> ModelConfig:
        return ModelConfig(
            provider="openai",
            display_name=display_name,
            url="https://example.com/v1",
            apikey="test-key",
            model_name="test-model",
            priority=priority,
            max_generation_count=max_generation_count,
        )

    async def test_workflow_and_model_targets_are_scheduled_by_priority(self) -> None:
        low_priority_model = self.build_model("LowPriorityModel", priority=1)
        high_priority_workflow = self.build_workflow("HighPriorityWorkflow", priority=10)
        counter = FakeCounter()
        service = GenerationService(
            [high_priority_workflow, low_priority_model],
            [
                WorkflowNodeBinding(
                    workflow_id=high_priority_workflow.workflow_id,
                    node_id="6",
                    field_path="inputs.text",
                    binding_type="prompt_positive",
                )
            ],
            global_retry_count=1,
            global_max_generation_count=-1,
            output_dir=Path("."),
            counter=counter,
        )

        async def fake_generate_text_to_image(
            self,
            prompt,
            count,
            workflow_config,
            node_bindings,
            runtime_config,
            output_dir,
            session,
        ):
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
            paths, target_name, _effective_send_strategy, _effective_fake_forward = await service.generate(
                mode="text_to_image", prompt="测试"
            )

        self.assertEqual(target_name, "HighPriorityWorkflow")
        self.assertEqual(paths, [Path("workflow_generated.png")])

    async def test_workflow_target_reports_mode_mismatch_for_image_to_image_requests(self) -> None:
        workflow_only = self.build_workflow("OnlyWorkflow", priority=10)
        counter = FakeCounter()
        service = GenerationService(
            [workflow_only],
            [],
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

    async def test_image_to_image_only_workflow_reports_mode_mismatch_for_text_to_image_requests(self) -> None:
        workflow_only = self.build_workflow(
            "ImageOnlyWorkflow",
            priority=10,
            supported_modes=["image_to_image"],
        )
        counter = FakeCounter()
        service = GenerationService(
            [workflow_only],
            [],
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
                await service.generate(mode="text_to_image", prompt="测试")

        self.assertIn("暂不支持文生图", str(raised_error.exception))

    async def test_validate_request_count_ignores_mode_mismatched_workflows(self) -> None:
        image_only_workflow = self.build_workflow(
            "ImageOnlyWorkflow",
            priority=10,
            supported_modes=["image_to_image"],
        )
        fallback_model = self.build_model("FallbackModel", priority=1, max_generation_count=2)
        counter = FakeCounter()
        service = GenerationService(
            [image_only_workflow, fallback_model],
            [],
            global_retry_count=1,
            global_max_generation_count=2,
            output_dir=Path("."),
            counter=counter,
        )

        successful_adapter = types.SimpleNamespace(
            text_to_image=self._return_generated_path,
            image_to_image=self._return_generated_path,
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
            paths, target_name, _effective_send_strategy, _effective_fake_forward = await service.generate(
                mode="text_to_image",
                prompt="测试",
                count=2,
            )

        self.assertEqual(target_name, "FallbackModel")
        self.assertEqual(paths, [Path("fallback_generated.png")])

    async def test_dual_entry_workflow_handles_image_to_image_requests(self) -> None:
        workflow_only = self.build_workflow(
            "DualEntryWorkflow",
            priority=10,
            supported_modes=["text_to_image", "image_to_image"],
        )
        counter = FakeCounter()
        service = GenerationService(
            [workflow_only],
            [],
            global_retry_count=1,
            global_max_generation_count=-1,
            output_dir=Path("."),
            counter=counter,
        )

        async def fake_generate_image_to_image(
            _runner,
            prompt,
            input_images,
            workflow_config,
            node_bindings,
            runtime_config,
            output_dir,
            session,
        ):
            self.assertEqual(input_images, ["stub-image"])
            return [Path("workflow_img2img.png")]

        with (
            patch(
                "astrbot_plugin_image_gateway.services.generation.ComfyUIWorkflowRunner.generate_image_to_image",
                fake_generate_image_to_image,
            ),
            patch(
                "astrbot_plugin_image_gateway.services.generation.aiohttp.ClientSession",
                FakeClientSession,
            ),
        ):
            paths, target_name, _effective_send_strategy, _effective_fake_forward = await service.generate(
                mode="image_to_image",
                prompt="test",
                input_images=["stub-image"],
            )

        self.assertEqual(target_name, "DualEntryWorkflow")
        self.assertEqual(paths, [Path("workflow_img2img.png")])

    async def test_workflow_falls_back_to_next_model_on_failure(self) -> None:
        failing_workflow = self.build_workflow("FailingWorkflow", priority=10)
        fallback_model = self.build_model("FallbackModel", priority=1)
        counter = FakeCounter()
        service = GenerationService(
            [failing_workflow, fallback_model],
            [
                WorkflowNodeBinding(
                    workflow_id=failing_workflow.workflow_id,
                    node_id="6",
                    field_path="inputs.text",
                    binding_type="prompt_positive",
                )
            ],
            global_retry_count=1,
            global_max_generation_count=-1,
            output_dir=Path("."),
            counter=counter,
        )

        async def fake_generate_text_to_image(
            self,
            prompt,
            count,
            workflow_config,
            node_bindings,
            runtime_config,
            output_dir,
            session,
        ):
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
            paths, target_name, _effective_send_strategy, _effective_fake_forward = await service.generate(
                mode="text_to_image", prompt="测试"
            )

        self.assertEqual(target_name, "FallbackModel")
        self.assertEqual(paths, [Path("fallback_generated.png")])

    async def test_real_workflow_error_is_not_overwritten_by_mode_mismatch_skip_message(self) -> None:
        failing_text_workflow = self.build_workflow(
            "miaomiao文生图",
            priority=20,
            supported_modes=["text_to_image"],
        )
        skipped_image_workflow = self.build_workflow(
            "miaomiao改图",
            priority=10,
            supported_modes=["image_to_image"],
        )
        counter = FakeCounter()
        service = GenerationService(
            [failing_text_workflow, skipped_image_workflow],
            [
                WorkflowNodeBinding(
                    workflow_id=failing_text_workflow.workflow_id,
                    node_id="6",
                    field_path="inputs.Append",
                    binding_type="prompt_positive",
                )
            ],
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
                await service.generate(mode="text_to_image", prompt="JK")

        self.assertIn("miaomiao文生图", str(raised_error.exception))
        self.assertIn("字段路径 inputs.Append 无效", str(raised_error.exception))
        self.assertNotIn("miaomiao改图", str(raised_error.exception))
        self.assertNotIn("暂不支持文生图", str(raised_error.exception))

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
                    "workflow_id": "test-workflow",
                    "priority": 10,
                    "workflow_content": json.dumps({"6": {"inputs": {"text": "placeholder"}}}),
                }
            ],
            "workflow_node_bindings": [
                {
                    "workflow_id": "test-workflow",
                    "node_id": "6",
                    "field_path": "inputs.text",
                    "binding_type": "prompt_positive",
                }
            ],
        }
        service = GenerationService.from_config(config, Path("."), FakeCounter())

        self.assertEqual(len(service.targets), 2)
        self.assertEqual(service.targets[0].display_name, "test-workflow")
        self.assertEqual(service.targets[1].display_name, "TestModel")
        self.assertEqual(len(service.workflow_node_bindings), 1)


if __name__ == "__main__":
    unittest.main()
