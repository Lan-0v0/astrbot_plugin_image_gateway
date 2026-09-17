"""Image tag recognition through the online SmilingWolf wd-tagger service.

配合 ``/tag`` 指令使用：用户先发送图片，再引用该图片并发送 ``/tag``，
插件把图片上传到 SmilingWolf 官方托管的 ``wd-tagger`` Gradio Space，
取回 Danbooru 风格的标签串。

之所以不在本地跑模型：wd-tagger-v3 系列的单份权重就有 300~450MB
（例如 ``wd-swinv2-tagger-v3`` 的 ``model.onnx`` 约 446MB、
``model.safetensors`` 约 374MB），插件本体不适合捆绑这么大的模型；
改用官方 Space 后本地零下载、零显存占用，代价是每次识别都需要联网，
并且图片会被上传到该第三方服务。

调用链路（Gradio HTTP API，均已在本机实测可用）::

    POST {space}/gradio_api/upload                 # multipart 上传图片
    POST {space}/gradio_api/call/predict           # 提交识别任务 -> event_id
    GET  {space}/gradio_api/call/predict/{id}      # SSE 读取结果

结果中 ``data[0]`` 即标签串；``data[2]`` 为角色信息（本插件只输出标签块）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import re
from typing import Any

import aiohttp

from ..utils.config import parse_bool, parse_float, parse_int

DEFAULT_TAGGER_SPACE_URL = "https://smilingwolf-wd-tagger.hf.space"
DEFAULT_TAGGER_MODEL_REPO = "SmilingWolf/wd-swinv2-tagger-v3"
DEFAULT_GENERAL_THRESHOLD = 0.35
DEFAULT_CHARACTER_THRESHOLD = 0.85
DEFAULT_TAGGER_TIMEOUT_SECONDS = 180

# 结果事件里的固定位置：0=标签串，1=分级，2=角色，3=带置信度的标签
_TAG_INDEX = 0


class ImageTaggingError(Exception):
    """标签识别过程中的可读错误（网络、服务或结果异常）。"""


@dataclass(slots=True)
class ImageTaggingConfig:
    enabled: bool = True
    space_url: str = DEFAULT_TAGGER_SPACE_URL
    model_repo: str = DEFAULT_TAGGER_MODEL_REPO
    general_threshold: float = DEFAULT_GENERAL_THRESHOLD
    timeout_seconds: int = DEFAULT_TAGGER_TIMEOUT_SECONDS


def normalize_space_url(raw_value: Any) -> str:
    """把用户填写的地址规范成 Gradio 服务根地址（不含 ``/gradio_api``）。"""
    url = str(raw_value or "").strip().rstrip("/")
    if not url:
        return DEFAULT_TAGGER_SPACE_URL
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        url = f"https://{url}"
    suffix = "/gradio_api"
    if url.endswith(suffix):
        url = url[: -len(suffix)].rstrip("/")
    return url or DEFAULT_TAGGER_SPACE_URL


def parse_image_tagging_config(raw_config: Any) -> ImageTaggingConfig:
    config_dict = raw_config if isinstance(raw_config, dict) else {}

    enabled = parse_bool(config_dict.get("enabled"), True)
    space_url = normalize_space_url(config_dict.get("space_url"))
    model_repo = str(config_dict.get("model_repo") or "").strip() or DEFAULT_TAGGER_MODEL_REPO

    general_threshold = parse_float(
        config_dict.get("general_threshold"), DEFAULT_GENERAL_THRESHOLD
    )
    if not 0 < general_threshold <= 1:
        general_threshold = DEFAULT_GENERAL_THRESHOLD

    timeout_seconds = parse_int(
        config_dict.get("timeout_seconds"), DEFAULT_TAGGER_TIMEOUT_SECONDS
    )
    if timeout_seconds <= 0:
        timeout_seconds = DEFAULT_TAGGER_TIMEOUT_SECONDS

    return ImageTaggingConfig(
        enabled=enabled,
        space_url=space_url,
        model_repo=model_repo,
        general_threshold=general_threshold,
        timeout_seconds=timeout_seconds,
    )


class ImageTaggerService:
    """调用在线 wd-tagger Space 识别图片标签。"""

    def __init__(self, config: ImageTaggingConfig | None = None):
        self.config = config or ImageTaggingConfig()

    async def tag_image(self, image_bytes: bytes, *, filename: str = "image.png") -> str:
        """识别图片并返回标签串（如 ``1girl, solo, long hair``）。"""
        if not image_bytes:
            raise ImageTaggingError("图片数据为空，无法识别标签")

        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                remote_path = await self._upload_image(session, image_bytes, filename)
                event_id = await self._submit_task(session, remote_path, len(image_bytes))
                result_payload = await self._read_result(session, event_id)
        except ImageTaggingError:
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise ImageTaggingError(
                f"识别超时（{self.config.timeout_seconds}s），"
                f"在线服务可能正在冷启动，请稍后重试"
            ) from exc
        except aiohttp.ClientError as exc:
            raise ImageTaggingError(
                f"无法连接标签识别服务（{self.config.space_url}）：{exc}"
            ) from exc

        tags = self._extract_tags(result_payload)
        if not tags:
            raise ImageTaggingError("未识别出任何标签，请换一张更清晰的图片重试")
        return tags

    @property
    def api_base(self) -> str:
        return f"{self.config.space_url}/gradio_api"

    async def _upload_image(
        self,
        session: aiohttp.ClientSession,
        image_bytes: bytes,
        filename: str,
    ) -> str:
        form = aiohttp.FormData()
        form.add_field("files", image_bytes, filename=filename, content_type="image/png")
        url = f"{self.api_base}/upload"
        async with session.post(url, data=form) as response:
            text = await response.text()
            if response.status != 200:
                raise ImageTaggingError(f"上传图片失败（HTTP {response.status}）")
            try:
                uploaded = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ImageTaggingError("上传图片失败：服务返回了无法解析的内容") from exc
            if not isinstance(uploaded, list) or not uploaded:
                raise ImageTaggingError("上传图片失败：服务未返回图片路径")
            remote_path = str(uploaded[0] or "").strip()
            if not remote_path:
                raise ImageTaggingError("上传图片失败：服务返回的图片路径为空")
            return remote_path

    async def _submit_task(
        self,
        session: aiohttp.ClientSession,
        remote_path: str,
        image_size: int,
    ) -> str:
        payload = {
            "data": [
                {
                    "path": remote_path,
                    "url": f"{self.api_base}/file={remote_path}",
                    "size": image_size,
                    "mime_type": "image/png",
                    "meta": {"_type": "gradio.FileData"},
                },
                self.config.model_repo,
                self.config.general_threshold,
                False,
                DEFAULT_CHARACTER_THRESHOLD,
                False,
            ]
        }
        url = f"{self.api_base}/call/predict"
        async with session.post(url, json=payload) as response:
            text = await response.text()
            if response.status != 200:
                raise ImageTaggingError(f"提交识别任务失败（HTTP {response.status}）")
            try:
                event = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ImageTaggingError("提交识别任务失败：服务返回了无法解析的内容") from exc
            event_id = str((event or {}).get("event_id") or "").strip()
            if not event_id:
                raise ImageTaggingError("提交识别任务失败：服务未返回任务编号")
            return event_id

    async def _read_result(
        self,
        session: aiohttp.ClientSession,
        event_id: str,
    ) -> Any:
        url = f"{self.api_base}/call/predict/{event_id}"
        async with session.get(url) as response:
            if response.status != 200:
                raise ImageTaggingError(f"读取识别结果失败（HTTP {response.status}）")
            async for raw_line in response.content:
                line = raw_line.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                body = line[len("data:") :].strip()
                if not body or body == "[DONE]":
                    continue
                try:
                    event = json.loads(body)
                except json.JSONDecodeError:
                    continue

                # 当前 Space 直接推送结果数组；旧版 Gradio 会包一层 msg/output。
                if isinstance(event, list):
                    return event
                if not isinstance(event, dict):
                    continue

                message_type = event.get("msg")
                if message_type == "process_completed":
                    if event.get("success") is False:
                        raise ImageTaggingError("在线服务识别失败，请稍后重试")
                    output = event.get("output") or {}
                    data = output.get("data") if isinstance(output, dict) else None
                    if isinstance(data, list) and data:
                        return data
                    raise ImageTaggingError("在线服务未返回标签数据")
                if message_type in {"unexpected_error", "process_errored"}:
                    detail = str(event.get("message") or event.get("error") or "").strip()
                    raise ImageTaggingError(f"在线服务返回错误：{detail or message_type}")
                if message_type == "close_stream":
                    break

        raise ImageTaggingError("未收到识别结果，请稍后重试")

    @staticmethod
    def _extract_tags(result_payload: Any) -> str:
        """从结果负载中取出纯标签串（不含“标签：”等标题文字）。"""
        value: Any = result_payload
        if isinstance(value, list):
            value = value[_TAG_INDEX] if len(value) > _TAG_INDEX else ""
        if not isinstance(value, str):
            return ""
        return value.strip()
