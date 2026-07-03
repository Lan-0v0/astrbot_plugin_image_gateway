from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

import aiohttp

from astrbot.api import logger

from .base import (
    GenerationError,
    ModelConfig,
    SensitiveContentError,
    is_safety_moderation_error,
    moderation_bypass_enabled,
    sensitive_content_message,
)
from ..utils.storage import download_image, save_base64_image

_DATA_URL_PATTERN = re.compile(
    r"(data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+)"
)
_HTTP_URL_PATTERN = re.compile(r"(https?://[^\s)\"']+)")


class OpenAIAdapter:
    async def text_to_image(
        self,
        prompt: str,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        base_url = self._normalize_base_url(model.url)
        url = f"{base_url}/images/generations"
        payload = self._build_generation_payload(prompt, count, model)
        moderation_attempts = self._moderation_attempts(model.moderation)
        bypass_chain = moderation_bypass_enabled(model.moderation)

        last_error = "OpenAI 生图失败"
        for moderation in moderation_attempts:
            body = dict(payload)
            if moderation is not None:
                body["moderation"] = moderation
            try:
                data = await self._post_json(session, url, model.apikey, body)
                paths = await self._extract_and_save_paths(session, data, output_dir, "openai")
                if paths:
                    return paths
            except GenerationError as exc:
                last_error = str(exc)
                if bypass_chain and moderation == "low" and is_safety_moderation_error(last_error):
                    raise SensitiveContentError("text_to_image") from exc
                logger.warning(f"[OpenAI:{model.display_name}] 生图尝试 moderation={moderation} 失败: {exc}")

        # 兼容部分网关仅支持 chat/completions 返回图片
        if bypass_chain:
            try:
                paths = await self._text_to_image_via_chat(
                    prompt, None, count, model, output_dir, session
                )
                if paths:
                    return paths
            except GenerationError as exc:
                last_error = str(exc)

        raise GenerationError(last_error)

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

        base_url = self._normalize_base_url(model.url)
        url = f"{base_url}/images/edits"
        moderation_attempts = self._moderation_attempts(model.moderation)
        bypass_chain = moderation_bypass_enabled(model.moderation)
        image_bytes = base64.b64decode(self._strip_data_url(input_images[0]))
        last_error = "OpenAI 改图失败"

        for moderation in moderation_attempts:
            form = aiohttp.FormData()
            form.add_field("model", model.model_name)
            form.add_field("prompt", prompt)
            if model.size and model.size != "auto":
                form.add_field("size", model.size)
            if moderation is not None:
                form.add_field("moderation", moderation)
            form.add_field(
                "image",
                image_bytes,
                filename="input.png",
                content_type="image/png",
            )
            try:
                data = await self._post_form(session, url, model.apikey, form)
                paths = await self._extract_and_save_paths(session, data, output_dir, "openai_edit")
                if paths:
                    return paths
            except GenerationError as exc:
                last_error = str(exc)
                if bypass_chain and moderation == "low" and is_safety_moderation_error(last_error):
                    raise SensitiveContentError("image_to_image") from exc
                logger.warning(f"[OpenAI:{model.display_name}] 改图尝试 moderation={moderation} 失败: {exc}")

        if bypass_chain:
            try:
                paths = await self._text_to_image_via_chat(
                    prompt, input_images, 1, model, output_dir, session
                )
                if paths:
                    return paths
            except GenerationError as exc:
                last_error = str(exc)

        raise GenerationError(last_error)

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        base = (url or "https://api.openai.com/v1").strip().rstrip("/")
        if not base.endswith("/v1"):
            if base.endswith("/v1beta"):
                return base
            base = f"{base}/v1"
        return base

    @staticmethod
    def _moderation_attempts(level: str) -> list[str | None]:
        level = (level or "auto").lower()
        if level == "none":
            return [None, "low", "auto"]
        if level == "low":
            return ["low"]
        return ["auto"]

    def _build_generation_payload(
        self, prompt: str, count: int, model: ModelConfig
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model.model_name,
            "prompt": prompt,
            "n": max(1, count),
            "response_format": "b64_json",
        }
        if model.size and model.size != "auto":
            payload["size"] = model.size
        if model.quality and model.quality != "auto":
            payload["quality"] = model.quality
        if model.seed:
            payload["seed"] = model.seed
        return payload

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
                message = self._extract_error_message(data, resp.status)
                raise GenerationError(message)
            if not isinstance(data, dict):
                raise GenerationError("OpenAI 返回格式异常")
            return data

    async def _post_form(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_key: str,
        form: aiohttp.FormData,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {api_key}"}
        async with session.post(url, data=form, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                message = self._extract_error_message(data, resp.status)
                raise GenerationError(message)
            if not isinstance(data, dict):
                raise GenerationError("OpenAI 返回格式异常")
            return data

    async def _extract_and_save_paths(
        self,
        session: aiohttp.ClientSession,
        data: dict[str, Any],
        output_dir: Path,
        prefix: str,
    ) -> list[Path]:
        paths: list[Path] = []
        items = data.get("data") or []
        if not isinstance(items, list):
            raise GenerationError("OpenAI 响应缺少 data 字段")

        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("b64_json"):
                path = await save_base64_image(
                    str(item["b64_json"]), output_dir, prefix=prefix
                )
                paths.append(path)
            elif item.get("url"):
                path = await download_image(session, str(item["url"]), output_dir, prefix)
                paths.append(path)

        if not paths:
            raise GenerationError("OpenAI 响应中未找到图片数据")
        return paths

    async def _text_to_image_via_chat(
        self,
        prompt: str,
        input_images: list[str] | None,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        base_url = self._normalize_base_url(model.url)
        url = f"{base_url}/chat/completions"
        content: list[dict[str, Any]] | str
        message_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"Generate {max(1, count)} image(s) for this description. "
                    f"Return image as data URL or direct image URL only.\n\n{prompt}"
                ),
            }
        ]
        if input_images:
            for image in input_images:
                data_url = image if image.startswith("data:image/") else f"data:image/png;base64,{image}"
                message_content.append({"type": "image_url", "image_url": {"url": data_url}})
            content = message_content
        else:
            content = message_content[0]["text"]

        payload = {
            "model": model.model_name,
            "messages": [{"role": "user", "content": content}],
        }
        data = await self._post_json(session, url, model.apikey, payload)
        return await self._extract_chat_image_paths(session, data, output_dir)

    async def _extract_chat_image_paths(
        self,
        session: aiohttp.ClientSession,
        data: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        choices = data.get("choices") or []
        if not choices:
            raise GenerationError("Chat 接口未返回 choices")

        message = choices[0].get("message") or {}
        content = message.get("content")
        image_url, base64_data, image_format = self._parse_chat_content(message, content)
        paths: list[Path] = []

        if image_url:
            paths.append(await download_image(session, image_url, output_dir, "openai_chat"))
        elif base64_data:
            paths.append(
                await save_base64_image(base64_data, output_dir, prefix="openai_chat", fmt=image_format)
            )

        if not paths:
            raise GenerationError("Chat 接口响应中未找到图片")
        return paths

    def _parse_chat_content(
        self, message: dict[str, Any], content: Any
    ) -> tuple[str | None, str | None, str]:
        image_url: str | None = None
        base64_data: str | None = None
        image_format = "png"

        if isinstance(content, str):
            text = content.strip()
            if text.startswith("http://") or text.startswith("https://"):
                image_url = text
            elif text.startswith("data:image/"):
                base64_data, image_format = self._split_data_url(text)
            else:
                data_match = _DATA_URL_PATTERN.search(text)
                if data_match:
                    base64_data, image_format = self._split_data_url(data_match.group(1))
                else:
                    url_match = _HTTP_URL_PATTERN.search(text)
                    if url_match:
                        image_url = url_match.group(1)
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") in {"image_url", "output_image"}:
                    candidate = item.get("image_url") or item.get("url")
                    if isinstance(candidate, dict):
                        candidate = candidate.get("url")
                    if isinstance(candidate, str):
                        if candidate.startswith("data:image/"):
                            base64_data, image_format = self._split_data_url(candidate)
                        else:
                            image_url = candidate
                        break

        if not image_url and not base64_data:
            images_field = message.get("images")
            if isinstance(images_field, list):
                for item in images_field:
                    if not isinstance(item, dict):
                        continue
                    candidate = item.get("image_url") or item.get("url")
                    if isinstance(candidate, dict):
                        candidate = candidate.get("url")
                    if isinstance(candidate, str):
                        if candidate.startswith("data:image/"):
                            base64_data, image_format = self._split_data_url(candidate)
                        else:
                            image_url = candidate
                        break

        return image_url, base64_data, image_format

    @staticmethod
    def _split_data_url(data_url: str) -> tuple[str, str]:
        header, base64_part = data_url.split(",", 1)
        image_format = header.split("/")[1].split(";")[0]
        return base64_part, image_format

    @staticmethod
    def _strip_data_url(value: str) -> str:
        if value.startswith("data:image/"):
            return value.split(",", 1)[-1]
        return value

    @staticmethod
    def _extract_error_message(data: Any, status: int) -> str:
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if isinstance(err, str):
                return err
        return f"HTTP {status}"
