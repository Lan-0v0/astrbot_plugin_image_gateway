from __future__ import annotations

from pathlib import Path
from typing import Any

import aiohttp

from .base import GenerationError, ModelConfig, SensitiveContentError, is_safety_moderation_error
from .http_utils import extract_error_message
from ..utils.storage import download_image, save_base64_image


class MiniMaxAdapter:
    """MiniMax 文生图 / 图生图适配器。"""

    async def text_to_image(
        self,
        prompt: str,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        payload = self._build_payload(prompt, None, max(1, count), model)
        data = await self._post_json(session, model, payload)
        return await self._extract_paths(session, data, output_dir, max(1, count))

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
        payload = self._build_payload(prompt, input_images, 1, model)
        data = await self._post_json(session, model, payload)
        return await self._extract_paths(session, data, output_dir, 1)

    def _build_payload(
        self,
        prompt: str,
        input_images: list[str] | None,
        count: int,
        model: ModelConfig,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model.model_name or "image-01",
            "prompt": prompt,
            "n": max(1, min(count, 9)),
            "response_format": str(model.raw.get("response_format") or "url").strip() or "url",
        }

        aspect_ratio = str(model.raw.get("aspect_ratio") or "").strip()
        if aspect_ratio and aspect_ratio.lower() != "auto":
            payload["aspect_ratio"] = aspect_ratio
        else:
            width, height = self._parse_width_height(model.size)
            if width and height:
                payload["width"] = width
                payload["height"] = height

        if model.seed:
            payload["seed"] = int(model.seed) if str(model.seed).isdigit() else model.seed

        prompt_optimizer = model.raw.get("prompt_optimizer")
        if isinstance(prompt_optimizer, bool):
            payload["prompt_optimizer"] = prompt_optimizer
        elif str(prompt_optimizer or "").strip():
            payload["prompt_optimizer"] = str(prompt_optimizer).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }

        watermark = model.raw.get("aigc_watermark")
        if isinstance(watermark, bool):
            payload["aigc_watermark"] = watermark

        if input_images:
            image_ref = input_images[0]
            if not image_ref.startswith(("http://", "https://", "data:image/")):
                image_ref = f"data:image/png;base64,{image_ref}"
            payload["subject_reference"] = [
                {
                    "type": "character",
                    "image_file": image_ref,
                }
            ]

        return payload

    async def _post_json(
        self,
        session: aiohttp.ClientSession,
        model: ModelConfig,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self._normalize_base_url(model.url)}/image_generation"
        headers = {
            "Authorization": f"Bearer {model.apikey}",
            "Content-Type": "application/json",
        }
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                message = extract_error_message(data, resp.status, fallback="MiniMax 生图失败")
                if is_safety_moderation_error(message):
                    mode = "image_to_image" if payload.get("subject_reference") else "text_to_image"
                    raise SensitiveContentError(mode)
                raise GenerationError(message)
            if not isinstance(data, dict):
                raise GenerationError("MiniMax 返回格式异常")

        base_resp = data.get("base_resp")
        if isinstance(base_resp, dict) and base_resp.get("status_code") not in (None, 0):
            message = str(base_resp.get("status_msg") or base_resp.get("status_code"))
            if is_safety_moderation_error(message):
                mode = "image_to_image" if payload.get("subject_reference") else "text_to_image"
                raise SensitiveContentError(mode)
            raise GenerationError(message)
        return data

    async def _extract_paths(
        self,
        session: aiohttp.ClientSession,
        data: dict[str, Any],
        output_dir: Path,
        count: int,
    ) -> list[Path]:
        paths: list[Path] = []
        payload = data.get("data") if isinstance(data.get("data"), dict) else {}

        image_urls = payload.get("image_urls")
        if isinstance(image_urls, list):
            for image_url in image_urls[:count]:
                if isinstance(image_url, str) and image_url:
                    paths.append(await download_image(session, image_url, output_dir, "minimax"))

        image_base64 = payload.get("image_base64")
        if isinstance(image_base64, list):
            for image_data in image_base64[:count]:
                if isinstance(image_data, str) and image_data:
                    paths.append(
                        await save_base64_image(image_data, output_dir, prefix="minimax")
                    )

        if not paths:
            raise GenerationError("MiniMax 响应中未找到图片数据")
        return paths

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        base = (url or "https://api.minimaxi.com/v1").strip().rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return base

    @staticmethod
    def _parse_width_height(size: str) -> tuple[int | None, int | None]:
        normalized = (size or "").strip().lower()
        if not normalized or normalized == "auto":
            return None, None

        if "*" in normalized or "x" in normalized:
            separator = "*" if "*" in normalized else "x"
            width_text, height_text = normalized.split(separator, 1)
            if width_text.isdigit() and height_text.isdigit():
                return int(width_text), int(height_text)
        return None, None