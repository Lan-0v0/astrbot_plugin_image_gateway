from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import aiohttp

from astrbot.api import logger

from .base import GenerationError, ModelConfig, SensitiveContentError, is_safety_moderation_error
from .http_utils import extract_error_message
from ..utils.storage import download_image, save_base64_image

_WAN26_MODEL_PATTERN = re.compile(r"^wan2\.6", re.IGNORECASE)


class DashScopeAdapter:
    """阿里云百炼 DashScope 文生图 / 图生图适配器。"""

    async def text_to_image(
        self,
        prompt: str,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        return await self._generate(
            prompt,
            None,
            max(1, count),
            model,
            output_dir,
            session,
        )

    async def image_to_image(
        self,
        prompt: str,
        input_images: list[str],
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        if not input_images:
            raise GenerationError("缺少输入图片")
        return await self._generate(prompt, input_images, 1, model, output_dir, session)

    async def _generate(
        self,
        prompt: str,
        input_images: list[str] | None,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        model_name = (model.model_name or "wan2.6-t2i").strip()
        base_url = self._normalize_base_url(model.url)
        size = self._normalize_size(model.size)
        negative_prompt = str(model.raw.get("negative_prompt") or "").strip()
        prompt_extend = self._parse_prompt_extend(model)
        watermark = self._parse_watermark(model)

        if _WAN26_MODEL_PATTERN.match(model_name):
            if input_images:
                return await self._generate_wan26_image_edit(
                    prompt,
                    input_images,
                    model,
                    base_url,
                    size,
                    output_dir,
                    session,
                )
            return await self._generate_wan26_text_to_image(
                prompt,
                count,
                model,
                base_url,
                size,
                negative_prompt,
                prompt_extend,
                watermark,
                output_dir,
                session,
            )

        if input_images:
            return await self._generate_legacy_ref_image(
                prompt,
                input_images[0],
                model,
                base_url,
                size,
                negative_prompt,
                output_dir,
                session,
            )

        return await self._generate_legacy_async_text_to_image(
            prompt,
            count,
            model,
            base_url,
            size,
            negative_prompt,
            prompt_extend,
            watermark,
            output_dir,
            session,
        )

    async def _generate_wan26_text_to_image(
        self,
        prompt: str,
        count: int,
        model: ModelConfig,
        base_url: str,
        size: str,
        negative_prompt: str,
        prompt_extend: bool,
        watermark: bool,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        sync_url = f"{base_url}/services/aigc/multimodal-generation/generation"
        payload: dict[str, Any] = {
            "model": model.model_name,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ]
            },
            "parameters": {
                "n": max(1, min(count, 4)),
                "size": size,
                "prompt_extend": prompt_extend,
                "watermark": watermark,
            },
        }
        if negative_prompt:
            payload["parameters"]["negative_prompt"] = negative_prompt
        if model.seed:
            payload["parameters"]["seed"] = self._parse_seed(model.seed)

        try:
            data = await self._post_json(session, sync_url, model.apikey, payload)
            paths = await self._extract_wan26_image_paths(session, data, output_dir)
            if paths:
                return paths[:count]
        except GenerationError as exc:
            if not is_safety_moderation_error(str(exc)):
                logger.warning(
                    f"[DashScope:{model.display_name}] 同步生图失败，尝试异步接口: {exc}"
                )
            else:
                raise SensitiveContentError("text_to_image") from exc

        async_url = f"{base_url}/services/aigc/image-generation/generation"
        task_id = await self._create_async_task(
            session,
            async_url,
            model.apikey,
            payload,
            extra_headers={"X-DashScope-Async": "enable"},
        )
        result = await self._poll_task(session, base_url, model.apikey, task_id)
        paths = await self._extract_wan26_image_paths(session, result, output_dir)
        if not paths:
            raise GenerationError("DashScope 响应中未找到图片数据")
        return paths[:count]

    async def _generate_wan26_image_edit(
        self,
        prompt: str,
        input_images: list[str],
        model: ModelConfig,
        base_url: str,
        size: str,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        content: list[dict[str, Any]] = []
        for image in input_images:
            data_url = image if image.startswith("data:image/") else f"data:image/png;base64,{image}"
            content.append({"image": data_url})
        content.append({"text": prompt})

        payload: dict[str, Any] = {
            "model": model.model_name,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            },
            "parameters": {
                "n": 1,
                "size": size,
            },
        }
        if model.seed:
            payload["parameters"]["seed"] = self._parse_seed(model.seed)

        sync_url = f"{base_url}/services/aigc/multimodal-generation/generation"
        try:
            data = await self._post_json(session, sync_url, model.apikey, payload)
            paths = await self._extract_wan26_image_paths(session, data, output_dir)
            if paths:
                return paths
        except GenerationError as exc:
            if is_safety_moderation_error(str(exc)):
                raise SensitiveContentError("image_to_image") from exc
            logger.warning(
                f"[DashScope:{model.display_name}] 同步改图失败，尝试异步接口: {exc}"
            )

        async_url = f"{base_url}/services/aigc/image-generation/generation"
        task_id = await self._create_async_task(
            session,
            async_url,
            model.apikey,
            payload,
            extra_headers={"X-DashScope-Async": "enable"},
        )
        result = await self._poll_task(session, base_url, model.apikey, task_id)
        paths = await self._extract_wan26_image_paths(session, result, output_dir)
        if not paths:
            raise GenerationError("DashScope 改图响应中未找到图片数据")
        return paths

    async def _generate_legacy_async_text_to_image(
        self,
        prompt: str,
        count: int,
        model: ModelConfig,
        base_url: str,
        size: str,
        negative_prompt: str,
        prompt_extend: bool,
        watermark: bool,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        create_url = f"{base_url}/services/aigc/text2image/image-synthesis"
        input_body: dict[str, Any] = {"prompt": prompt}
        if negative_prompt:
            input_body["negative_prompt"] = negative_prompt

        payload: dict[str, Any] = {
            "model": model.model_name,
            "input": input_body,
            "parameters": {
                "size": size,
                "n": max(1, min(count, 4)),
                "prompt_extend": prompt_extend,
                "watermark": watermark,
            },
        }
        if model.seed:
            payload["parameters"]["seed"] = self._parse_seed(model.seed)

        task_id = await self._create_async_task(
            session,
            create_url,
            model.apikey,
            payload,
            extra_headers={"X-DashScope-Async": "enable"},
        )
        result = await self._poll_task(session, base_url, model.apikey, task_id)
        paths = await self._extract_legacy_result_paths(session, result, output_dir)
        if not paths:
            raise GenerationError("DashScope 响应中未找到图片数据")
        return paths[:count]

    async def _generate_legacy_ref_image(
        self,
        prompt: str,
        input_image: str,
        model: ModelConfig,
        base_url: str,
        size: str,
        negative_prompt: str,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        ref_image = input_image if input_image.startswith(("http://", "https://")) else (
            input_image if input_image.startswith("data:image/") else f"data:image/png;base64,{input_image}"
        )

        create_url = f"{base_url}/services/aigc/text2image/image-synthesis"
        input_body: dict[str, Any] = {
            "prompt": prompt,
            "ref_image": ref_image,
        }
        if negative_prompt:
            input_body["negative_prompt"] = negative_prompt

        ref_mode = str(model.raw.get("ref_mode") or "repaint").strip() or "repaint"
        ref_strength = model.raw.get("ref_strength")
        parameters: dict[str, Any] = {
            "size": size,
            "n": 1,
            "ref_mode": ref_mode,
        }
        if ref_strength not in (None, ""):
            parameters["ref_strength"] = float(ref_strength)

        payload = {
            "model": model.model_name,
            "input": input_body,
            "parameters": parameters,
        }

        task_id = await self._create_async_task(
            session,
            create_url,
            model.apikey,
            payload,
            extra_headers={"X-DashScope-Async": "enable"},
        )
        result = await self._poll_task(session, base_url, model.apikey, task_id)
        paths = await self._extract_legacy_result_paths(session, result, output_dir)
        if not paths:
            raise GenerationError("DashScope 改图响应中未找到图片数据")
        return paths

    async def _create_async_task(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_key: str,
        payload: dict[str, Any],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                message = extract_error_message(data, resp.status, fallback="DashScope 创建任务失败")
                raise GenerationError(message)

        output = data.get("output") if isinstance(data, dict) else None
        if not isinstance(output, dict) or not output.get("task_id"):
            raise GenerationError("DashScope 创建任务响应缺少 task_id")
        return str(output["task_id"])

    async def _poll_task(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
        task_id: str,
        *,
        timeout_seconds: int = 300,
        poll_interval_seconds: float = 2.0,
    ) -> dict[str, Any]:
        url = f"{base_url}/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        elapsed = 0.0
        last_status = "UNKNOWN"

        while elapsed < timeout_seconds:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    message = extract_error_message(data, resp.status, fallback="DashScope 查询任务失败")
                    raise GenerationError(message)

            if not isinstance(data, dict):
                raise GenerationError("DashScope 任务查询返回格式异常")

            output = data.get("output")
            if not isinstance(output, dict):
                raise GenerationError("DashScope 任务查询缺少 output")

            task_status = str(output.get("task_status") or "").upper()
            last_status = task_status or last_status

            if task_status == "SUCCEEDED":
                return data
            if task_status == "FAILED":
                message = extract_error_message(data, 500, fallback="DashScope 任务执行失败")
                raise GenerationError(message)
            if task_status in {"CANCELED", "UNKNOWN"}:
                raise GenerationError(f"DashScope 任务状态异常: {task_status}")

            await asyncio.sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds

        raise GenerationError(f"DashScope 任务超时（最后状态: {last_status}）")

    async def _post_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                message = extract_error_message(data, resp.status, fallback="DashScope 请求失败")
                raise GenerationError(message)
            if not isinstance(data, dict):
                raise GenerationError("DashScope 返回格式异常")
            if data.get("code"):
                raise GenerationError(str(data.get("message") or data.get("code")))
            return data

    async def _extract_wan26_image_paths(
        self,
        session: aiohttp.ClientSession,
        data: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        paths: list[Path] = []
        output = data.get("output") if isinstance(data.get("output"), dict) else data

        choices = output.get("choices") if isinstance(output, dict) else None
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message") or {}
                content = message.get("content") or []
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    image_url = item.get("image") or item.get("url")
                    if isinstance(image_url, str) and image_url:
                        paths.append(await download_image(session, image_url, output_dir, "dashscope"))

        if paths:
            return paths
        return await self._extract_legacy_result_paths(session, data, output_dir)

    async def _extract_legacy_result_paths(
        self,
        session: aiohttp.ClientSession,
        data: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        paths: list[Path] = []
        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        results = output.get("results") if isinstance(output, dict) else None

        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                if item.get("url"):
                    paths.append(await download_image(session, str(item["url"]), output_dir, "dashscope"))
                elif item.get("b64_image"):
                    paths.append(
                        await save_base64_image(str(item["b64_image"]), output_dir, prefix="dashscope")
                    )

        return paths

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        base = (url or "https://dashscope.aliyuncs.com/api/v1").strip().rstrip("/")
        if base.endswith("/api/v1"):
            return base
        if "/api/v1" not in base:
            base = f"{base}/api/v1"
        return base.rstrip("/")

    @staticmethod
    def _normalize_size(size: str) -> str:
        normalized = (size or "1280*1280").strip()
        if normalized.lower() == "auto":
            return "1280*1280"
        return normalized.replace("x", "*").replace("X", "*")

    @staticmethod
    def _parse_seed(seed: str) -> int:
        text = (seed or "").strip()
        if text.isdigit():
            return int(text)
        raise GenerationError(f"DashScope seed 不是合法整数: {seed!r}")

    @staticmethod
    def _parse_prompt_extend(model: ModelConfig) -> bool:
        quality = (model.quality or "auto").strip().lower()
        if quality in {"high", "auto"}:
            return True
        if quality in {"medium", "low"}:
            return False
        raw_value = model.raw.get("prompt_extend")
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            return raw_value.strip().lower() in {"1", "true", "yes", "on"}
        return True

    @staticmethod
    def _parse_watermark(model: ModelConfig) -> bool:
        moderation = (model.moderation or "auto").strip().lower()
        if moderation in {"none", "low"}:
            return False
        raw_value = model.raw.get("watermark")
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            return raw_value.strip().lower() in {"1", "true", "yes", "on"}
        return False