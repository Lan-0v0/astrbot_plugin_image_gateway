from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random
import re
import time
from typing import Any

from astrbot.api import AstrBotConfig, logger
import astrbot.api.message_components as Comp
from astrbot.api.all import Image
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.message.message_event_result import MessageChain

from .adapters import GenerationError
from .services.counter import GenerationCounter
from .services.fake_forward import FakeForwardConfig, FakeForwardMode, parse_global_fake_forward
from .services.generation import GenerationService
from .services.image_cache import cleanup_expired_image_cache, parse_image_cache_cleanup_days
from .services.send_strategy import SendStrategy, get_sender_order, parse_global_send_strategy
from .utils.messages import collect_input_images, parse_command_text, parse_count_and_prompt

PLUGIN_NAME = "astrbot_plugin_image_gateway"
DEFAULT_START_MESSAGES = ["开始生成0v0~"]
DEFAULT_LLM_CUSTOM_PERSONA_PROMPT = (
    "根据现在的情景，以适宜的性格言语，简单表述要开始生成图片了，不分段不加格式，10字以内，结尾不加标点符号换成颜文字表情，严禁使用emoji。"
)
LLM_START_MESSAGE_PROMPT_TEMPLATE = (
    "请用简短自然的中文，向用户发送一句{label}开始前的提示。"
    "只输出一句话，不要换行，不要解释，不要表情，不要引号，长度尽量控制在12个字以内。"
)


@dataclass(slots=True)
class GenerationStartMessageConfig:
    enabled: bool = True
    mode: str = "fixed"
    fixed_messages: list[str] = field(default_factory=lambda: ["开始生成0v0~"])
    llm_provider_id: str = ""
    llm_persona_source: str = "current"
    llm_custom_persona_prompt: str = DEFAULT_LLM_CUSTOM_PERSONA_PROMPT


@dataclass(slots=True)
class StartMessageDispatchResult:
    text: str
    message_id: str | None = None
    sent_passively: bool = False


@register(
    PLUGIN_NAME,
    "AstrBot",
    "多模型图像生成网关，支持 OpenAI/Gemini/ComfyUI Workflow、优先级回退与自然语言触发",
    "1.4.7",
)
class ImageGatewayPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config
        self.plugin_config: dict = dict(config or {})
        self._normalize_plugin_config()
        self._last_image_cache_cleanup_at = 0.0
        self._refresh_services()

    def _normalize_plugin_config(self) -> None:
        changed = False
        raw_bindings = self.plugin_config.get("workflow_node_bindings")
        if isinstance(raw_bindings, list):
            for entry in raw_bindings:
                if not isinstance(entry, dict):
                    continue
                display_summary = self._build_workflow_binding_display_summary(entry)
                if entry.get("display_summary") != display_summary:
                    entry["display_summary"] = display_summary
                    changed = True

        if changed:
            self._persist_plugin_config()

    @staticmethod
    def _build_workflow_binding_display_summary(entry: dict[str, Any]) -> str:
        display_name = str(entry.get("display_name") or "").strip()
        workflow_id = str(entry.get("workflow_id") or "").strip()

        if display_name and workflow_id:
            return f"{display_name}——{workflow_id}"
        if display_name:
            return display_name
        if workflow_id:
            return workflow_id
        return ""

    def _persist_plugin_config(self) -> None:
        save_config = getattr(self.config, "save_config", None)
        if callable(save_config):
            save_config(replace_config=self.plugin_config)
            return

        if isinstance(self.config, dict):
            self.config.clear()
            self.config.update(self.plugin_config)

    def _refresh_services(self) -> None:
        data_dir = StarTools.get_data_dir(PLUGIN_NAME)
        images_dir = data_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        self.image_cache_cleanup_days = parse_image_cache_cleanup_days(
            self.plugin_config.get("image_cache_cleanup_days")
        )
        self._maybe_cleanup_image_cache(images_dir)
        counter_file = data_dir / "generation_counts.json"
        self.generation_service = GenerationService.from_config(
            self.plugin_config,
            images_dir,
            GenerationCounter(counter_file),
        )
        self.enable_nl_trigger = bool(self.plugin_config.get("enable_nl_trigger", True))
        self.global_send_strategy = parse_global_send_strategy(self.plugin_config.get("send_strategy"))
        self.global_fake_forward = parse_global_fake_forward(self.plugin_config.get("fake_forward"))
        self.start_message_config = self._load_start_message_config(
            self.plugin_config.get("generation_start_message")
        )

    def _maybe_cleanup_image_cache(self, images_dir: Path) -> None:
        if self.image_cache_cleanup_days is None:
            return

        now = time.time()
        # ``_refresh_services`` 会在插件启动和生成前刷新；限制为每 6 小时最多扫描一次。
        if (
            self._last_image_cache_cleanup_at > 0
            and (now - self._last_image_cache_cleanup_at) < 21600
        ):
            return

        deleted_count = cleanup_expired_image_cache(
            images_dir,
            retention_days=self.image_cache_cleanup_days,
            now=now,
        )
        self._last_image_cache_cleanup_at = now

        if deleted_count > 0:
            logger.info(
                f"图片缓存定时清理完成，已删除 {deleted_count} 个超过 {self.image_cache_cleanup_days} 天的文件"
            )

    def _load_start_message_config(
        self,
        raw_config: Any,
    ) -> GenerationStartMessageConfig:
        config_dict = raw_config if isinstance(raw_config, dict) else {}

        enabled = bool(config_dict.get("enabled", True))

        mode = str(config_dict.get("mode") or "fixed").strip().lower()
        if mode not in {"fixed", "llm"}:
            mode = "fixed"

        fixed_messages = self._normalize_message_list(
            config_dict.get("fixed_messages"),
            fallback=DEFAULT_START_MESSAGES,
        )

        llm_provider_id = str(config_dict.get("llm_provider_id") or "").strip()

        llm_persona_source = str(config_dict.get("llm_persona_source") or "current").strip().lower()
        if llm_persona_source not in {"current", "custom"}:
            llm_persona_source = "current"

        llm_custom_persona_prompt = str(
            config_dict.get("llm_custom_persona_prompt") or DEFAULT_LLM_CUSTOM_PERSONA_PROMPT
        ).strip()

        return GenerationStartMessageConfig(
            enabled=enabled,
            mode=mode,
            fixed_messages=fixed_messages,
            llm_provider_id=llm_provider_id,
            llm_persona_source=llm_persona_source,
            llm_custom_persona_prompt=llm_custom_persona_prompt,
        )

    @staticmethod
    def _normalize_message_list(raw_values: Any, *, fallback: list[str]) -> list[str]:
        normalized_values: list[str] = []

        if isinstance(raw_values, list):
            iterable_values = raw_values
        elif isinstance(raw_values, str):
            iterable_values = [raw_values]
        else:
            iterable_values = []

        for raw_value in iterable_values:
            text = str(raw_value or "").strip()
            if text and text not in normalized_values:
                normalized_values.append(text)

        return normalized_values or list(fallback)

    async def _send_generated_images(
        self,
        event: AstrMessageEvent,
        image_paths: list[str],
        *,
        send_strategy: SendStrategy = SendStrategy.DIRECT_FIRST,
    ):
        if not image_paths:
            return

        sender_order = get_sender_order(send_strategy)
        merged_chain, single_image_chains = await self._build_image_delivery_chains(event, image_paths)

        if merged_chain and await self._send_message_chain_directly(event, merged_chain, sender_order=sender_order):
            return

        if len(single_image_chains) == 1:
            yield event.chain_result(single_image_chains[0])
            return

        for single_image_chain in single_image_chains:
            if await self._send_message_chain_directly(event, single_image_chain, sender_order=sender_order):
                continue
            yield event.chain_result(single_image_chain)

    async def _build_image_delivery_chains(
        self,
        event: AstrMessageEvent,
        image_paths: list[str],
    ) -> tuple[list[Any], list[list[Any]]]:
        image_components: list[Image] = []
        single_image_chains: list[list[Any]] = []

        for index, image_path in enumerate(image_paths, start=1):
            image_component = await self._build_image_component(image_path)
            image_components.append(image_component)

            if len(image_paths) == 1:
                single_image_chains.append([image_component])
            else:
                single_image_chains.append(
                    [Comp.Plain(f"图片 {index}/{len(image_paths)}"), image_component]
                )

        if len(image_components) == 1:
            return single_image_chains[0], single_image_chains

        nodes: list[Comp.Node] = []
        sender_id = event.get_sender_id()
        sender_name = event.get_sender_name() or "Bot"

        for index, image_component in enumerate(image_components, start=1):
            nodes.append(
                Comp.Node(
                    uin=sender_id,
                    name=sender_name,
                    content=[Comp.Plain(f"图片 {index}/{len(image_components)}"), image_component],
                )
            )

        return [Comp.Nodes(nodes=nodes)], single_image_chains

    async def _build_fake_forward_chain(
        self,
        event: AstrMessageEvent,
        start_message_text: str,
        image_paths: list[str],
        fake_forward_config: FakeForwardConfig,
    ) -> list[Any]:
        sender_uin, sender_name = await self._resolve_fake_forward_sender_identity(
            event,
            fake_forward_config,
        )

        if not sender_uin:
            return []

        nodes: list[Comp.Node] = []
        if start_message_text:
            nodes.append(
                Comp.Node(
                    uin=sender_uin,
                    name=sender_name,
                    content=[Comp.Plain(start_message_text)],
                )
            )

        image_components: list[Image] = []
        for image_path in image_paths:
            image_components.append(await self._build_image_component(image_path))

        for index, image_component in enumerate(image_components, start=1):
            content: list[Any] = []
            if len(image_components) > 1:
                content.append(Comp.Plain(f"图片 {index}/{len(image_components)}"))
            content.append(image_component)
            nodes.append(
                Comp.Node(
                    uin=sender_uin,
                    name=sender_name,
                    content=content,
                )
            )

        if not nodes:
            return []

        return [Comp.Nodes(nodes=nodes)]

    async def _send_message_chain_directly(
        self,
        event: AstrMessageEvent,
        chain_components: list[Any],
        *,
        sender_order: list[str] | None = None,
    ) -> bool:
        resolved_sender_order = (
            sender_order if sender_order is not None else ["event_send", "context_send_message"]
        )

        for sender_name in resolved_sender_order:
            if sender_name == "event_send" and await self._try_send_via_event_send(event, chain_components):
                return True
            if sender_name == "context_send_message" and await self._try_send_via_context_send_message(
                event, chain_components
            ):
                return True
            if sender_name == "platform_client" and await self._try_send_via_platform_client_chain(
                event, chain_components
            ):
                return True

        return False

    async def _try_send_via_event_send(
        self,
        event: AstrMessageEvent,
        chain_components: list[Any],
    ) -> bool:
        message_chain = MessageChain(chain_components)
        event_send_method = getattr(event, "send", None)
        if not callable(event_send_method):
            return False

        try:
            await event_send_method(message_chain)
            logger.debug("消息已通过 event.send 直接发送")
            return True
        except Exception as exc:
            logger.warning(f"event.send 发送失败，尝试下一层回退: {exc}")
            return False

    async def _try_send_via_context_send_message(
        self,
        event: AstrMessageEvent,
        chain_components: list[Any],
    ) -> bool:
        message_chain = MessageChain(chain_components)
        context_send_method = getattr(self.context, "send_message", None)
        message_origin = getattr(event, "unified_msg_origin", None)
        if not callable(context_send_method) or not message_origin:
            return False

        try:
            await context_send_method(message_origin, message_chain)
            logger.debug("消息已通过 context.send_message 直接发送")
            return True
        except Exception as exc:
            logger.warning(f"context.send_message 发送失败，回退结果管道: {exc}")
            return False

    async def _try_send_via_platform_client_chain(
        self,
        event: AstrMessageEvent,
        chain_components: list[Any],
    ) -> bool:
        get_platform_inst = getattr(self.context, "get_platform_inst", None)
        if not callable(get_platform_inst):
            return False

        platform = get_platform_inst(event.get_platform_id())
        if platform is None:
            return False

        try:
            client = platform.get_client()
        except Exception as exc:
            logger.warning(f"获取平台客户端失败，无法通过客户端直接发送: {exc}")
            return False

        if client is None or not hasattr(client, "call_action"):
            return False

        if (
            len(chain_components) == 1
            and isinstance(chain_components[0], Comp.Nodes)
            and await self._try_send_via_platform_client_forward_nodes(event, chain_components[0])
        ):
            return True

        segments: list[dict[str, Any]] = []
        for component in chain_components:
            segment = await self._build_platform_message_segment(component)
            if segment is None:
                logger.debug("消息片段不支持平台客户端发送，放弃该链路")
                return False
            segments.append(segment)

        session_id = event.get_group_id() or event.get_sender_id()
        if not session_id or not str(session_id).isdigit():
            return False

        try:
            if event.get_group_id():
                await client.call_action(
                    "send_group_msg",
                    group_id=int(session_id),
                    message=segments,
                )
            else:
                await client.call_action(
                    "send_private_msg",
                    user_id=int(session_id),
                    message=segments,
                )
            logger.debug("消息已通过平台客户端直接发送")
            return True
        except Exception as exc:
            logger.warning(f"平台客户端直接发送失败: {exc}")
            return False

    async def _try_send_via_platform_client_forward_nodes(
        self,
        event: AstrMessageEvent,
        nodes_component: Any,
    ) -> bool:
        get_platform_inst = getattr(self.context, "get_platform_inst", None)
        if not callable(get_platform_inst):
            return False

        platform = get_platform_inst(event.get_platform_id())
        if platform is None:
            return False

        try:
            client = platform.get_client()
        except Exception as exc:
            logger.warning(f"获取平台客户端失败，无法通过客户端直接发送合并转发: {exc}")
            return False

        if client is None or not hasattr(client, "call_action"):
            return False

        nodes = list(getattr(nodes_component, "nodes", []) or [])
        if not nodes:
            return False

        payload_nodes: list[dict[str, Any]] = []
        for node in nodes:
            content_segments: list[dict[str, Any]] = []
            for component in list(getattr(node, "content", []) or []):
                segment = await self._build_platform_message_segment(component)
                if segment is None:
                    logger.debug("合并转发节点中存在平台客户端不支持的片段，放弃该链路")
                    return False
                content_segments.append(segment)

            payload_nodes.append(
                {
                    "type": "node",
                    "data": {
                        "uin": str(getattr(node, "uin", "") or ""),
                        "name": str(getattr(node, "name", "") or "Bot"),
                        "content": content_segments,
                    },
                }
            )

        session_id = event.get_group_id() or event.get_sender_id()
        if not session_id or not str(session_id).isdigit():
            return False

        try:
            if event.get_group_id():
                await client.call_action(
                    "send_group_forward_msg",
                    group_id=int(session_id),
                    messages=payload_nodes,
                )
            else:
                await client.call_action(
                    "send_private_forward_msg",
                    user_id=int(session_id),
                    messages=payload_nodes,
                )
            logger.debug("合并转发消息已通过平台客户端直接发送")
            return True
        except Exception as exc:
            logger.warning(f"平台客户端直接发送合并转发失败: {exc}")
            return False

    async def _build_platform_message_segment(self, component: Any) -> dict[str, Any] | None:
        if isinstance(component, Comp.Plain):
            return {"type": "text", "data": {"text": str(getattr(component, "text", ""))}}

        if isinstance(component, Image):
            try:
                base64_payload = await component.convert_to_base64()
            except Exception as exc:
                logger.warning(f"图片转换为 base64 失败，平台客户端无法发送: {exc}")
                return None
            raw_base64 = (
                base64_payload.split(",", 1)[-1]
                if base64_payload.startswith("data:image")
                else base64_payload
            )
            return {"type": "image", "data": {"file": f"base64://{raw_base64}"}}

        return None

    async def _send_plain_text_directly(
        self,
        event: AstrMessageEvent,
        text: str,
        *,
        sender_order: list[str] | None = None,
    ) -> bool:
        success, _message_id = await self._send_plain_text_directly_with_message_id(
            event,
            text,
            sender_order=sender_order,
        )
        return success

    async def _send_plain_text_directly_with_message_id(
        self,
        event: AstrMessageEvent,
        text: str,
        *,
        sender_order: list[str] | None = None,
    ) -> tuple[bool, str | None]:
        resolved_sender_order = (
            sender_order
            if sender_order is not None
            else ["event_send", "context_send_message", "platform_client"]
        )

        for sender_name in resolved_sender_order:
            if sender_name == "platform_client":
                platform_send_success, platform_message_id = await self._send_plain_text_via_platform_client(
                    event,
                    text,
                )
                if platform_send_success:
                    return True, platform_message_id
                continue

            if await self._send_message_chain_directly(event, [Comp.Plain(text)], sender_order=[sender_name]):
                return True, None

        return False, None

    async def _send_plain_text_via_platform_client(
        self,
        event: AstrMessageEvent,
        text: str,
    ) -> tuple[bool, str | None]:

        platform = self.context.get_platform_inst(event.get_platform_id())
        if platform is None:
            return False, None

        try:
            client = platform.get_client()
        except Exception as exc:
            logger.warning(f"获取平台客户端失败，文本主动发送不可用: {exc}")
            return False, None

        if client is None or not hasattr(client, "call_action"):
            return False, None

        session_id = event.get_group_id() or event.get_sender_id()
        if not session_id or not str(session_id).isdigit():
            return False, None

        try:
            if event.get_group_id():
                response = await client.call_action(
                    "send_group_msg",
                    group_id=int(session_id),
                    message=text,
                )
            else:
                response = await client.call_action(
                    "send_private_msg",
                    user_id=int(session_id),
                    message=text,
                )
            message_id = self._extract_message_id(response)
            logger.debug("文本消息已通过平台客户端直接发送")
            return True, message_id
        except Exception as exc:
            logger.warning(f"平台客户端直接发送文本失败，回退结果管道: {exc}")
            return False, None

    async def _send_fake_forward_result(
        self,
        event: AstrMessageEvent,
        summary_text: str,
        image_paths: list[str],
        *,
        fake_forward_config: FakeForwardConfig,
        send_strategy: SendStrategy,
    ):
        merged_chain = await self._build_fake_forward_chain(
            event,
            summary_text,
            image_paths,
            fake_forward_config,
        )
        if not merged_chain:
            if summary_text:
                yield event.plain_result(summary_text)
            async for result in self._send_generated_images(
                event,
                image_paths,
                send_strategy=send_strategy,
            ):
                yield result
            return

        sender_order = get_sender_order(send_strategy)
        if await self._send_message_chain_directly(event, merged_chain, sender_order=sender_order):
            return

        yield event.chain_result(merged_chain)

    async def _build_image_component(self, image_path: str) -> Image:
        callback_api_base = self.context.get_config().get("callback_api_base")
        if not callback_api_base:
            return Image.fromFileSystem(image_path)
        try:
            image_component = Image.fromFileSystem(image_path)
            download_url = await image_component.convert_to_web_link()
            return Image.fromURL(download_url)
        except Exception as exc:
            logger.warning(f"callback_api 发送失败，回退本地文件: {exc}")
            return Image.fromFileSystem(image_path)

    async def _run_generation(
        self,
        event: AstrMessageEvent,
        *,
        mode: str,
        prompt: str,
        count: int = 1,
        input_images: list[str] | None = None,
        success_label: str,
    ):
        self._refresh_services()

        try:
            requested_count = self.generation_service._normalize_requested_count(mode, count)
            self.generation_service.validate_request_count(requested_count, mode=mode)
        except GenerationError as exc:
            yield event.plain_result(str(exc))
            return

        start_message = await self._send_start_message(event, success_label)
        if start_message.sent_passively:
            start_message_sender_order = get_sender_order(self.global_send_strategy, for_start_message=True)
            fallback_send_success, fallback_message_id = await self._send_plain_text_directly_with_message_id(
                event,
                start_message.text,
                sender_order=start_message_sender_order,
            )
            start_message.message_id = start_message.message_id or fallback_message_id
            if not fallback_send_success:
                yield event.plain_result(start_message.text)

        started = time.time()

        try:
            paths, _model_name, effective_send_strategy, effective_fake_forward = (
                await self.generation_service.generate(
                mode=mode,
                prompt=prompt,
                count=count,
                input_images=input_images,
                )
            )
        except GenerationError as exc:
            await self._retract_start_message(event, start_message.message_id)
            yield event.plain_result(str(exc))
            return
        except Exception as exc:
            logger.error(f"图像生成异常: {exc}")
            await self._retract_start_message(event, start_message.message_id)
            yield event.plain_result("图像生成失败，请稍后重试")
            return

        elapsed = time.time() - started
        success_message_text = f"{success_label}成功，用时{elapsed:.1f}秒"
        await self._retract_start_message(event, start_message.message_id)

        image_paths = [str(path) for path in paths]
        if effective_fake_forward.enabled:
            async for result in self._send_fake_forward_result(
                event,
                success_message_text,
                image_paths,
                fake_forward_config=effective_fake_forward,
                send_strategy=effective_send_strategy,
            ):
                yield result
            return

        success_message_sender_order = get_sender_order(effective_send_strategy)
        success_message_sent_directly = await self._send_plain_text_directly(
            event,
            success_message_text,
            sender_order=success_message_sender_order,
        )

        if not success_message_sent_directly:
            yield event.plain_result(success_message_text)

        async for result in self._send_generated_images(
            event,
            image_paths,
            send_strategy=effective_send_strategy,
        ):
            yield result

    async def _send_start_message(
        self,
        event: AstrMessageEvent,
        label: str,
    ) -> StartMessageDispatchResult:
        if not self.start_message_config.enabled:
            return StartMessageDispatchResult(text="")

        message_text = await self._build_generation_start_message(event, label)
        platform = self.context.get_platform_inst(event.get_platform_id())
        if platform is None:
            return StartMessageDispatchResult(text=message_text, sent_passively=True)

        try:
            client = platform.get_client()
        except Exception as exc:
            logger.warning(f"获取平台客户端失败，回退被动发送: {exc}")
            return StartMessageDispatchResult(text=message_text, sent_passively=True)

        if client is None or not hasattr(client, "call_action"):
            return StartMessageDispatchResult(text=message_text, sent_passively=True)

        session_id = event.get_group_id() or event.get_sender_id()
        if not session_id or not str(session_id).isdigit():
            return StartMessageDispatchResult(text=message_text, sent_passively=True)

        try:
            if event.get_group_id():
                response = await client.call_action(
                    "send_group_msg",
                    group_id=int(session_id),
                    message=message_text,
                )
            else:
                response = await client.call_action(
                    "send_private_msg",
                    user_id=int(session_id),
                    message=message_text,
                )

            message_id = self._extract_message_id(response)
            return StartMessageDispatchResult(
                text=message_text,
                message_id=message_id,
            )
        except Exception as exc:
            logger.warning(f"发送开始提示失败，回退被动发送: {exc}")

        return StartMessageDispatchResult(text=message_text, sent_passively=True)

    async def _retract_start_message(
        self,
        event: AstrMessageEvent,
        message_id: str | None,
    ) -> None:
        if not message_id:
            return

        platform = self.context.get_platform_inst(event.get_platform_id())
        if platform is None:
            return

        try:
            client = platform.get_client()
        except Exception as exc:
            logger.warning(f"获取平台客户端失败，无法撤回开始提示: {exc}")
            return

        if client is None or not hasattr(client, "call_action"):
            return

        try:
            await client.call_action("delete_msg", message_id=int(message_id))
        except Exception as exc:
            logger.warning(f"撤回开始提示失败: {exc}")

    async def _build_generation_start_message(
        self,
        event: AstrMessageEvent,
        label: str,
    ) -> str:
        if not self.start_message_config.enabled:
            return ""

        if self.start_message_config.mode == "llm":
            llm_message = await self._generate_llm_start_message(event, label)
            if llm_message:
                return llm_message
            logger.warning("LLM 开始提示生成失败，回退固定语句")

        return random.choice(self.start_message_config.fixed_messages)

    async def _generate_llm_start_message(
        self,
        event: AstrMessageEvent,
        label: str,
    ) -> str:
        provider_id = self._resolve_start_message_provider_id(event)
        if not provider_id:
            logger.warning("未找到可用的 LLM 提供商，无法使用 LLM 开始提示")
            return ""

        system_prompt = await self._resolve_start_message_persona_prompt(event)
        prompt = LLM_START_MESSAGE_PROMPT_TEMPLATE.format(label=label)

        try:
            llm_response = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
                system_prompt=system_prompt or None,
            )
        except Exception as exc:
            logger.warning(f"LLM 开始提示生成失败: {exc}")
            return ""

        completion_text = getattr(llm_response, "completion_text", "") or ""
        return self._clean_start_message_text(completion_text)

    def _resolve_start_message_provider_id(self, event: AstrMessageEvent) -> str | None:
        configured_provider_id = self.start_message_config.llm_provider_id
        if configured_provider_id:
            return configured_provider_id

        try:
            current_provider = self.context.get_using_provider(event.unified_msg_origin)
            if current_provider:
                return current_provider.meta().id
        except Exception as exc:
            logger.warning(f"获取当前默认提供商失败: {exc}")

        try:
            available_providers = self.context.get_all_providers()
            if available_providers:
                return available_providers[0].meta().id
        except Exception as exc:
            logger.warning(f"获取可用提供商列表失败: {exc}")

        return None

    async def _resolve_start_message_persona_prompt(
        self,
        event: AstrMessageEvent,
    ) -> str:
        if self.start_message_config.llm_persona_source == "custom":
            custom_prompt = self.start_message_config.llm_custom_persona_prompt.strip()
            if custom_prompt:
                return custom_prompt
            logger.warning("自定义人设提示词为空，回退到当前人设")

        try:
            conversation_id = await self.context.conversation_manager.get_curr_conversation_id(
                event.unified_msg_origin,
            )
            conversation_persona_id = None
            if conversation_id:
                conversation = await self.context.conversation_manager.get_conversation(
                    event.unified_msg_origin,
                    conversation_id,
                )
                if conversation:
                    conversation_persona_id = conversation.persona_id

            provider_settings = dict(
                self.context.get_config(event.unified_msg_origin).get("provider_settings", {}),
            )
            _, selected_persona, _, _ = await self.context.persona_manager.resolve_selected_persona(
                umo=event.unified_msg_origin,
                conversation_persona_id=conversation_persona_id,
                platform_name=event.get_platform_name(),
                provider_settings=provider_settings,
            )
            if selected_persona and selected_persona.get("prompt"):
                return str(selected_persona["prompt"]).strip()
        except Exception as exc:
            logger.warning(f"获取当前人设失败: {exc}")

        try:
            default_persona = await self.context.persona_manager.get_default_persona_v3(
                event.unified_msg_origin,
            )
            if default_persona and default_persona.get("prompt"):
                return str(default_persona["prompt"]).strip()
        except Exception as exc:
            logger.warning(f"获取默认人设失败: {exc}")

        return ""

    @staticmethod
    def _clean_start_message_text(text: str) -> str:
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return ""

        cleaned_text = cleaned_text.splitlines()[0].strip()
        cleaned_text = re.sub(r"\s+", " ", cleaned_text)
        cleaned_text = cleaned_text.strip("`\"'“”‘’")
        cleaned_text = re.sub(r"^[：:—\-]+", "", cleaned_text).strip()
        return cleaned_text

    async def _resolve_fake_forward_sender_identity(
        self,
        event: AstrMessageEvent,
        fake_forward_config: FakeForwardConfig,
    ) -> tuple[str, str]:
        mode = fake_forward_config.mode

        if mode == FakeForwardMode.REQUESTER.value:
            requester_uin = str(event.get_sender_id() or "").strip()
            requester_name = self._get_event_sender_name(event) or requester_uin or "用户"
            return requester_uin, requester_name

        if mode == FakeForwardMode.CUSTOM_QQ.value:
            custom_qq = str(fake_forward_config.custom_qq or "").strip()
            if not custom_qq:
                return "", ""
            custom_name = await self._resolve_qq_nickname(event, custom_qq)
            return custom_qq, custom_name or custom_qq

        if mode == FakeForwardMode.BOT_SELF.value:
            bot_uin, bot_name = await self._resolve_bot_identity(event)
            return bot_uin, bot_name

        return "", ""

    @staticmethod
    def _get_event_sender_name(event: AstrMessageEvent) -> str:
        get_sender_name = getattr(event, "get_sender_name", None)
        if callable(get_sender_name):
            try:
                sender_name = str(get_sender_name() or "").strip()
                if sender_name:
                    return sender_name
            except Exception:
                return ""
        return ""

    async def _resolve_bot_identity(self, event: AstrMessageEvent) -> tuple[str, str]:
        client = self._get_platform_client(event)
        if client is not None:
            try:
                response = await client.call_action("get_login_info")
                if isinstance(response, dict):
                    data = response.get("data") if isinstance(response.get("data"), dict) else response
                    user_id = str(data.get("user_id") or "").strip()
                    nickname = str(data.get("nickname") or "").strip()
                    if user_id:
                        return user_id, nickname or "Bot"
            except Exception as exc:
                logger.warning(f"获取 Bot 自身身份信息失败，回退默认名称: {exc}")

        return "", "Bot"

    async def _resolve_qq_nickname(self, event: AstrMessageEvent, qq: str) -> str:
        client = self._get_platform_client(event)
        if client is None or not qq:
            return ""

        try:
            response = await client.call_action("get_stranger_info", user_id=int(qq), no_cache=True)
            if isinstance(response, dict):
                data = response.get("data") if isinstance(response.get("data"), dict) else response
                nickname = str(data.get("nickname") or "").strip()
                if nickname:
                    return nickname
        except Exception as exc:
            logger.warning(f"获取自定义 QQ 昵称失败，回退使用 QQ 号: {exc}")

        return ""

    def _get_platform_client(self, event: AstrMessageEvent) -> Any | None:
        get_platform_inst = getattr(self.context, "get_platform_inst", None)
        if not callable(get_platform_inst):
            return None

        platform = get_platform_inst(event.get_platform_id())
        if platform is None:
            return None

        try:
            return platform.get_client()
        except Exception as exc:
            logger.warning(f"获取平台客户端失败: {exc}")
            return None

    @staticmethod
    def _extract_message_id(response: Any) -> str | None:
        if response is None:
            return None

        if isinstance(response, dict):
            if response.get("message_id") is not None:
                return str(response["message_id"])

            data = response.get("data")
            if isinstance(data, dict) and data.get("message_id") is not None:
                return str(data["message_id"])

        if isinstance(response, (int, str)):
            message_id = str(response).strip()
            return message_id or None

        return None

    async def _handle_text_to_image_request(
        self,
        event: AstrMessageEvent,
        *,
        prompt: str = "",
        count: int = 1,
    ):
        event.stop_event()
        text = prompt.strip() or parse_command_text(event, "生图")
        prompt_text, image_count = parse_count_and_prompt(text, default_count=count or 1)

        if not prompt_text:
            yield event.plain_result("缺少生图提示词")
            return

        async for result in self._run_generation(
            event,
            mode="text_to_image",
            prompt=prompt_text,
            count=image_count,
            success_label="生图",
        ):
            yield result

    async def _handle_image_to_image_request(
        self,
        event: AstrMessageEvent,
        *,
        prompt: str = "",
    ):
        event.stop_event()
        prompt_text = prompt.strip() or parse_command_text(event, "改图")
        if not prompt_text:
            yield event.plain_result("缺少改图提示词")
            return

        input_images = await collect_input_images(event)
        if not input_images:
            yield event.plain_result("缺少改图的图片")
            return

        async for result in self._run_generation(
            event,
            mode="image_to_image",
            prompt=prompt_text,
            input_images=input_images,
            success_label="改图",
        ):
            yield result

    @filter.command("生图")
    async def text_to_image_command(
        self,
        event: AstrMessageEvent,
        prompt: str = "",
        count: int = 1,
    ):
        """文字生图：`/生图 {prompt} {count?}`"""
        async for result in self._handle_text_to_image_request(
            event,
            prompt=prompt,
            count=count,
        ):
            yield result

    @filter.regex(r"^(?:/|／)?\s*生图[，,、:：;；。.!！？?]+\s*.*$")
    async def punctuated_text_to_image_command(self, event: AstrMessageEvent):
        """兼容 `/生图，xxx` 这类带中文标点的指令。"""
        async for result in self._handle_text_to_image_request(event):
            yield result

    @filter.command("改图")
    async def image_to_image_command(self, event: AstrMessageEvent, prompt: str = ""):
        """图片改图：`/改图 {prompt}`，需附带或引用一张图片"""
        async for result in self._handle_image_to_image_request(event, prompt=prompt):
            yield result

    @filter.regex(r"^(?:/|／)?\s*改图[，,、:：;；。.!！？?]+\s*.*$")
    async def punctuated_image_to_image_command(self, event: AstrMessageEvent):
        """兼容 `/改图，xxx` 这类带中文标点的指令。"""
        async for result in self._handle_image_to_image_request(event):
            yield result

    @filter.llm_tool(name="image_gateway_generate")
    async def image_gateway_generate_tool(
        self,
        event: AstrMessageEvent,
        prompt: str,
        mode: str = "text_to_image",
        count: int = 1,
    ):
        """Generate or edit images through the configured image gateway.

        Args:
            prompt(string): Text prompt for generation or editing
            mode(string): text_to_image or image_to_image
            count(number): Number of images to generate for text_to_image
        """
        if not self.enable_nl_trigger:
            yield event.plain_result("自然语言生图未启用，请使用 /生图 或 /改图 指令")
            return

        mode_value = (mode or "text_to_image").strip().lower()
        if mode_value not in {"text_to_image", "image_to_image"}:
            mode_value = "text_to_image"

        input_images = None
        if mode_value == "image_to_image":
            input_images = await collect_input_images(event)
            if not input_images:
                yield event.plain_result("改图需要附带或引用一张图片")
                return

        label = "生图" if mode_value == "text_to_image" else "改图"
        async for result in self._run_generation(
            event,
            mode=mode_value,
            prompt=prompt,
            count=max(1, int(count or 1)),
            input_images=input_images,
            success_label=label,
        ):
            yield result
