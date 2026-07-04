from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

import aiohttp

from astrbot.api import logger

from ..adapters import GenerationError, ModelConfig, SensitiveContentError, get_adapter
from .counter import GenerationCounter

Mode = Literal["text_to_image", "image_to_image"]


class GenerationService:
    def __init__(
        self,
        models: list[ModelConfig],
        *,
        global_retry_count: int,
        global_max_generation_count: int,
        output_dir: Path,
        counter: GenerationCounter,
    ):
        self.models = models
        self.global_retry_count = max(1, global_retry_count)
        self.global_max_generation_count = global_max_generation_count
        self.output_dir = output_dir
        self.counter = counter

    @classmethod
    def from_config(cls, config: dict, output_dir: Path, counter: GenerationCounter) -> GenerationService:
        raw_models = config.get("models") or []
        models: list[ModelConfig] = []
        if isinstance(raw_models, list):
            for entry in raw_models:
                if isinstance(entry, dict):
                    models.append(ModelConfig.from_template_entry(entry))

        enabled_models = [m for m in models if m.enabled]
        enabled_models.sort(key=lambda item: item.priority, reverse=True)

        return cls(
            enabled_models,
            global_retry_count=int(config.get("global_retry_count", 3) or 3),
            global_max_generation_count=int(config.get("global_max_generation_count", -1) or -1),
            output_dir=output_dir,
            counter=counter,
        )

    async def generate(
        self,
        *,
        mode: Mode,
        prompt: str,
        count: int = 1,
        input_images: list[str] | None = None,
    ) -> tuple[list[Path], str]:
        if not self.models:
            raise GenerationError("未配置任何已启用的图像模型")

        errors: list[str] = []
        had_sensitive = False
        quota_exhausted_model_count = 0
        timeout = aiohttp.ClientTimeout(total=180)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for model in self.models:
                limit = self._resolve_max_count(model)
                current = await self.counter.get_count(model.model_key())
                if limit >= 0 and current + max(1, count) > limit:
                    quota_exhausted_model_count += 1
                    errors.append(f"{model.display_name}: 超出生成张数上限")
                    continue

                retry_count = self._resolve_retry_count(model)
                adapter = get_adapter(model.provider)

                for attempt in range(retry_count):
                    try:
                        if attempt > 0:
                            delay = min(2**attempt, 10)
                            logger.info(
                                f"[{model.display_name}] 第 {attempt + 1}/{retry_count} 次重试，等待 {delay}s"
                            )
                            await asyncio.sleep(delay)

                        if mode == "text_to_image":
                            paths = await adapter.text_to_image(
                                prompt, count, model, self.output_dir, session
                            )
                        else:
                            paths = await adapter.image_to_image(
                                prompt, input_images or [], model, self.output_dir, session
                            )

                        if paths:
                            await self.counter.add_count(model.model_key(), len(paths))
                            return paths, model.display_name
                    except SensitiveContentError as exc:
                        # 安全审查失败不重试本模型（相同内容结果不变），
                        # 记录后继续尝试下一个优先级模型；全部失败再统一上报。
                        had_sensitive = True
                        msg = f"{model.display_name}: {exc}"
                        logger.warning(msg)
                        errors.append(msg)
                        break
                    except GenerationError as exc:
                        msg = f"{model.display_name}: {exc}"
                        logger.warning(msg)
                        if attempt == retry_count - 1:
                            errors.append(msg)
                    except Exception as exc:
                        msg = f"{model.display_name}: {exc}"
                        logger.error(msg)
                        if attempt == retry_count - 1:
                            errors.append(msg)

        if had_sensitive:
            raise SensitiveContentError(mode)

        if quota_exhausted_model_count == len(self.models):
            raise GenerationError("超出生成张数上限")

        brief = errors[-1] if errors else "所有模型均生成失败"
        if len(brief) > 120:
            brief = brief[:117] + "..."
        raise GenerationError(brief)

    def _resolve_retry_count(self, model: ModelConfig) -> int:
        if model.retry_count and model.retry_count > 0:
            return model.retry_count
        return self.global_retry_count

    def _resolve_max_count(self, model: ModelConfig) -> int:
        if model.max_generation_count is not None and model.max_generation_count >= 0:
            return model.max_generation_count
        return self.global_max_generation_count
