from __future__ import annotations

import time

from astrbot.api import AstrBotConfig, logger
import astrbot.api.message_components as Comp
from astrbot.api.all import Image
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register

from .adapters import GenerationError
from .services.counter import GenerationCounter
from .services.generation import GenerationService
from .utils.messages import collect_input_images, parse_command_text, parse_count_and_prompt

PLUGIN_NAME = "astrbot_plugin_image_gateway"


@register(
    PLUGIN_NAME,
    "AstrBot",
    "多模型图像生成网关，支持 OpenAI/Gemini、优先级回退与自然语言触发",
    "1.0.0",
)
class ImageGatewayPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.plugin_config: dict = dict(config or {})
        self._refresh_services()

    def _refresh_services(self) -> None:
        data_dir = StarTools.get_data_dir(PLUGIN_NAME)
        images_dir = data_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        counter_file = data_dir / "generation_counts.json"
        self.generation_service = GenerationService.from_config(
            self.plugin_config,
            images_dir,
            GenerationCounter(counter_file),
        )
        self.enable_nl_trigger = bool(self.plugin_config.get("enable_nl_trigger", True))

    async def _send_generated_images(self, event: AstrMessageEvent, image_paths: list[str]):
        if not image_paths:
            return

        if len(image_paths) == 1:
            image_component = await self._build_image_component(image_paths[0])
            yield event.chain_result([image_component])
            return

        nodes: list[Comp.Node] = []
        sender_id = event.get_sender_id()
        sender_name = event.get_sender_name() or "Bot"
        for index, path in enumerate(image_paths, start=1):
            image_component = await self._build_image_component(path)
            nodes.append(
                Comp.Node(
                    uin=sender_id,
                    name=sender_name,
                    content=[Comp.Plain(f"图片 {index}/{len(image_paths)}"), image_component],
                )
            )
        yield event.chain_result([Comp.Nodes(nodes=nodes)])

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
        started = time.time()

        try:
            paths, _model_name = await self.generation_service.generate(
                mode=mode,
                prompt=prompt,
                count=count,
                input_images=input_images,
            )
        except GenerationError as exc:
            yield event.plain_result(str(exc))
            return
        except Exception as exc:
            logger.error(f"图像生成异常: {exc}")
            yield event.plain_result("图像生成失败，请稍后重试")
            return

        elapsed = time.time() - started
        yield event.plain_result(f"{success_label}成功，用时{elapsed:.1f}秒")
        async for result in self._send_generated_images(event, [str(path) for path in paths]):
            yield result

    @filter.command("生图")
    async def text_to_image_command(
        self,
        event: AstrMessageEvent,
        prompt: str = "",
        count: int = 1,
    ):
        """文字生图：`/生图 {prompt} {count?}`"""
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

    @filter.command("改图")
    async def image_to_image_command(self, event: AstrMessageEvent, prompt: str = ""):
        """图片改图：`/改图 {prompt}`，需附带或引用一张图片"""
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
