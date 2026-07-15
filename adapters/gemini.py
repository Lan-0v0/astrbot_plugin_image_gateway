from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import aiohttp

from astrbot.api import logger

from .base import (
    FailureClass,
    GenerationError,
    ModelConfig,
    SensitiveContentError,
    classify_generation_failure,
    moderation_bypass_enabled,
    raise_exhausted_generation_error,
)
from ..utils.storage import download_image, save_base64_image

_DATA_URL_PATTERN = re.compile(
    r"(data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+)"
)
_HTTP_URL_PATTERN = re.compile(r"(https?://[^\s)\"']+)")

_SAFETY_FINISH_REASONS = {
    "SAFETY",
    "IMAGE_SAFETY",
    "PROHIBITED_CONTENT",
    "BLOCKLIST",
    "SPII",
}


class GeminiAdapter:
    _HARM_CATEGORIES = [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
        "HARM_CATEGORY_CIVIC_INTEGRITY",
    ]

    async def text_to_image(
        self,
        prompt: str,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        paths: list[Path] = []
        remaining = max(1, count)
        last_error = "Gemini 生图失败"

        while remaining > 0:
            batch = min(remaining, 4)
            try:
                batch_paths = await self._generate_once(
                    prompt, None, batch, model, output_dir, session
                )
                paths.extend(batch_paths)
                remaining -= len(batch_paths)
            except SensitiveContentError:
                raise
            except GenerationError as exc:
                last_error = str(exc)
                break

        if paths:
            return paths
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
        return await self._generate_once(
            prompt, input_images, 1, model, output_dir, session
        )

    async def _generate_once(
        self,
        prompt: str,
        input_images: list[str] | None,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        url = self._build_generate_url(model.url, model.model_name, model.apikey)
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if input_images:
            for image in input_images:
                raw = image.split(",", 1)[-1] if image.startswith("data:image/") else image
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": raw,
                        }
                    }
                )

        generation_config: dict[str, Any] = {
            "responseModalities": ["TEXT", "IMAGE"],
        }
        if count > 1:
            generation_config["candidateCount"] = count
        if model.seed:
            generation_config["seed"] = int(model.seed) if model.seed.isdigit() else model.seed

        payload_base: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }

        safety_attempts = self._safety_attempts(model.moderation)
        bypass_chain = moderation_bypass_enabled(model.moderation, default="default")
        mode = "image_to_image" if input_images else "text_to_image"
        last_error = "Gemini 改图失败" if input_images else "Gemini 生图失败"
        content_blocked = False

        for safety_settings in safety_attempts:
            payload = dict(payload_base)
            if safety_settings is not None:
                payload["safetySettings"] = safety_settings
            try:
                data = await self._post_json(session, url, payload)
                paths = await self._extract_paths(session, data, output_dir)
                if paths:
                    return paths[:count] if count else paths
            except GenerationError as exc:
                last_error = str(exc)
                failure = classify_generation_failure(last_error)
                label = self._safety_label(safety_settings)
                logger.warning(
                    f"[Gemini:{model.display_name}] 尝试 safety={label} "
                    f"失败({failure.value}): {exc}"
                )
                if failure == FailureClass.AUTH_OR_QUOTA:
                    raise GenerationError(last_error) from exc
                if failure == FailureClass.CONTENT_BLOCKED:
                    content_blocked = True
                # PARAM / CONTENT / UNKNOWN: continue remaining safety steps (including omit).

        # OpenAI-compatible images surface — different moderation plane for many gateways.
        if bypass_chain:
            try:
                paths = await self._generate_via_openai_compatible(
                    prompt, input_images, count, model, output_dir, session
                )
                if paths:
                    return paths
            except SensitiveContentError:
                # OpenAI adapter already exhausted its own chain with content blocks.
                raise
            except GenerationError as exc:
                last_error = str(exc)
                failure = classify_generation_failure(last_error)
                logger.warning(
                    f"[Gemini:{model.display_name}] OpenAI 兼容回退失败({failure.value}): {exc}"
                )
                if failure == FailureClass.CONTENT_BLOCKED:
                    content_blocked = True
                elif failure == FailureClass.AUTH_OR_QUOTA:
                    raise GenerationError(last_error) from exc

        raise_exhausted_generation_error(
            mode,
            last_error,
            content_blocked=content_blocked,
        )

    def _safety_attempts(self, level: str) -> list[list[dict[str, str]] | None]:
        level = (level or "default").lower()
        if level == "none":
            return [
                self._build_safety_settings("BLOCK_NONE"),
                self._build_safety_settings("OFF"),
                self._build_safety_settings("BLOCK_ONLY_HIGH"),
                # Omit safetySettings entirely (reachable after content-block on prior steps).
                None,
                # Asymmetric: loosen only high-impact categories; keep others at BLOCK_ONLY_HIGH.
                self._build_asymmetric_safety_settings(),
            ]
        if level == "high":
            return [self._build_safety_settings("BLOCK_MEDIUM_AND_ABOVE")]
        if level == "low":
            return [self._build_safety_settings("BLOCK_ONLY_HIGH")]
        return [None]

    def _build_safety_settings(self, threshold: str) -> list[dict[str, str]]:
        return [
            {"category": category, "threshold": threshold}
            for category in self._HARM_CATEGORIES
        ]

    def _build_asymmetric_safety_settings(self) -> list[dict[str, str]]:
        loose = {
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "HARM_CATEGORY_DANGEROUS_CONTENT",
        }
        settings: list[dict[str, str]] = []
        for category in self._HARM_CATEGORIES:
            threshold = "BLOCK_NONE" if category in loose else "BLOCK_ONLY_HIGH"
            settings.append({"category": category, "threshold": threshold})
        return settings

    @staticmethod
    def _safety_label(settings: list[dict[str, str]] | None) -> str:
        if not settings:
            return "default"
        thresholds = {item.get("threshold", "custom") for item in settings}
        if len(thresholds) == 1:
            return next(iter(thresholds)) or "custom"
        return "asymmetric"

    @staticmethod
    def _build_generate_url(base_url: str, model_name: str, api_key: str) -> str:
        base = (base_url or "").strip().rstrip("/")
        if ":generateContent" in base:
            url = base
        elif base.endswith(f"/models/{model_name}"):
            url = f"{base}:generateContent"
        else:
            url = f"{base}/models/{model_name}:generateContent"
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}key={api_key}"

    async def _post_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                message = self._extract_error_message(data, resp.status)
                raise GenerationError(message)
            if not isinstance(data, dict):
                raise GenerationError("Gemini 返回格式异常")
            return data

    async def _extract_paths(
        self,
        session: aiohttp.ClientSession,
        data: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        prompt_feedback = data.get("promptFeedback") or data.get("prompt_feedback") or {}
        if isinstance(prompt_feedback, dict):
            block_reason = str(
                prompt_feedback.get("blockReason") or prompt_feedback.get("block_reason") or ""
            ).strip()
            if block_reason:
                raise GenerationError(f"blocked due to safety filter: {block_reason}")

        paths: list[Path] = []
        candidates = data.get("candidates") or []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            finish_reason = str(
                candidate.get("finishReason") or candidate.get("finish_reason") or ""
            ).upper()
            if finish_reason in _SAFETY_FINISH_REASONS:
                raise GenerationError(f"blocked due to safety filter: {finish_reason}")
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline_data = part.get("inlineData") or part.get("inline_data")
                if isinstance(inline_data, dict) and inline_data.get("data"):
                    mime = str(inline_data.get("mimeType") or inline_data.get("mime_type") or "image/png")
                    fmt = mime.split("/")[-1] or "png"
                    path = await save_base64_image(
                        str(inline_data["data"]), output_dir, prefix="gemini", fmt=fmt
                    )
                    paths.append(path)
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    extracted = self._parse_text_for_image(text)
                    if extracted:
                        url, b64, fmt = extracted
                        if url:
                            paths.append(await download_image(session, url, output_dir, "gemini"))
                        elif b64:
                            paths.append(
                                await save_base64_image(b64, output_dir, prefix="gemini", fmt=fmt)
                            )

        if not paths:
            raise GenerationError("Gemini 响应中未找到图片数据")
        return paths

    def _parse_text_for_image(self, text: str) -> tuple[str | None, str | None, str] | None:
        text = text.strip()
        if text.startswith("http://") or text.startswith("https://"):
            return text, None, "png"
        if text.startswith("data:image/"):
            header, b64 = text.split(",", 1)
            fmt = header.split("/")[1].split(";")[0]
            return None, b64, fmt
        data_match = _DATA_URL_PATTERN.search(text)
        if data_match:
            header, b64 = data_match.group(1).split(",", 1)
            fmt = header.split("/")[1].split(";")[0]
            return None, b64, fmt
        url_match = _HTTP_URL_PATTERN.search(text)
        if url_match:
            return url_match.group(1), None, "png"
        return None

    async def _generate_via_openai_compatible(
        self,
        prompt: str,
        input_images: list[str] | None,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        from .openai import OpenAIAdapter

        openai_model = ModelConfig(
            provider="openai",
            display_name=model.display_name,
            url=model.url,
            apikey=model.apikey,
            model_name=model.model_name,
            quality=model.quality,
            size=model.size,
            moderation=model.moderation,
            seed=model.seed,
        )
        adapter = OpenAIAdapter()
        if input_images:
            return await adapter.image_to_image(
                prompt, input_images, openai_model, output_dir, session
            )
        return await adapter.text_to_image(
            prompt, count, openai_model, output_dir, session
        )

    @staticmethod
    def _extract_error_message(data: Any, status: int) -> str:
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if isinstance(err, str):
                return err
            if data.get("message"):
                return str(data["message"])
        return f"HTTP {status}"
