from __future__ import annotations

from pathlib import Path

import aiohttp

from .base import GenerationError, ModelConfig, SensitiveContentError
from .openai import OpenAIAdapter


class VolcengineAdapter:
    """火山引擎方舟图像生成适配器（OpenAI Images 兼容协议）。"""

    async def text_to_image(
        self,
        prompt: str,
        count: int,
        model: ModelConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        adapter = OpenAIAdapter()
        return await adapter.text_to_image(
            prompt,
            count,
            self._to_openai_model(model),
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

        openai_model = self._to_openai_model(model)
        adapter = OpenAIAdapter()

        try:
            return await adapter.image_to_image(
                prompt,
                input_images,
                openai_model,
                output_dir,
                session,
            )
        except SensitiveContentError:
            raise
        except GenerationError:
            return await adapter._text_to_image_via_chat(
                prompt,
                input_images,
                1,
                openai_model,
                output_dir,
                session,
            )

    @staticmethod
    def _to_openai_model(model: ModelConfig) -> ModelConfig:
        response_format = str(model.raw.get("response_format") or "b64_json").strip() or "b64_json"
        return ModelConfig(
            provider="openai",
            display_name=model.display_name,
            url=VolcengineAdapter._normalize_base_url(model.url),
            apikey=model.apikey,
            model_name=model.model_name or "doubao-seedream-3-0-t2i-250415",
            quality=model.quality,
            size=VolcengineAdapter._normalize_size(model.size),
            moderation=model.moderation,
            seed=model.seed,
            raw={**model.raw, "response_format": response_format},
        )

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        base = (url or "https://ark.cn-beijing.volces.com/api/v3").strip().rstrip("/")
        if base.endswith("/v3"):
            return base
        if "/v3" not in base:
            base = f"{base}/v3"
        return base

    @staticmethod
    def _normalize_size(size: str) -> str:
        normalized = (size or "1024x1024").strip()
        if normalized.lower() == "auto":
            return "1024x1024"
        return normalized.replace("*", "x")