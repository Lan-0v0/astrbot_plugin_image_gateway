from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal, Union

import aiohttp

from astrbot.api import logger

from ..adapters import GenerationError, ModelConfig, SensitiveContentError, get_adapter
from .counter import GenerationCounter
from .fake_forward import FakeForwardConfig, parse_global_fake_forward, resolve_effective_fake_forward
from .send_strategy import (
    DEFAULT_GLOBAL_SEND_STRATEGY,
    SendStrategy,
    parse_global_send_strategy,
    resolve_effective_send_strategy,
)
from .workflow_config import WorkflowConfig, WorkflowNodeBinding, WorkflowRuntimeConfig, describe_mode
from .a1111_runner import A1111WorkflowRunner
from .workflow_runner import ComfyUIWorkflowRunner

Mode = Literal["text_to_image", "image_to_image"]

GenerationTarget = Union[ModelConfig, WorkflowConfig]


class GenerationService:
    """Schedules image generation across model and workflow targets."""

    def __init__(
        self,
        targets: list[GenerationTarget],
        workflow_node_bindings: list[WorkflowNodeBinding],
        *,
        global_retry_count: int,
        global_max_generation_count: int,
        output_dir: Path,
        counter: GenerationCounter,
        global_send_strategy: SendStrategy = DEFAULT_GLOBAL_SEND_STRATEGY,
        global_fake_forward: FakeForwardConfig | None = None,
        workflow_runtime_default: WorkflowRuntimeConfig | None = None,
    ):
        self.targets = targets
        self.workflow_node_bindings = workflow_node_bindings
        self.global_retry_count = max(1, global_retry_count)
        self.global_max_generation_count = global_max_generation_count
        self.output_dir = output_dir
        self.counter = counter
        self.global_send_strategy = global_send_strategy
        self.global_fake_forward = global_fake_forward or FakeForwardConfig()
        self.workflow_runtime_default = workflow_runtime_default or WorkflowRuntimeConfig()
        self._comfyui_runner = ComfyUIWorkflowRunner()
        self._a1111_runner = A1111WorkflowRunner()

    @classmethod
    def from_config(cls, config: dict, output_dir: Path, counter: GenerationCounter) -> GenerationService:
        raw_models = config.get("models") or []
        targets: list[GenerationTarget] = []
        if isinstance(raw_models, list):
            for entry in raw_models:
                if isinstance(entry, dict):
                    targets.append(ModelConfig.from_template_entry(entry))

        raw_workflows = config.get("workflows") or []
        if isinstance(raw_workflows, list):
            for entry in raw_workflows:
                if isinstance(entry, dict):
                    targets.append(WorkflowConfig.from_template_entry(entry))

        raw_workflow_node_bindings = config.get("workflow_node_bindings") or []
        workflow_node_bindings: list[WorkflowNodeBinding] = []
        if isinstance(raw_workflow_node_bindings, list):
            for entry in raw_workflow_node_bindings:
                if isinstance(entry, dict):
                    workflow_node_bindings.append(WorkflowNodeBinding.from_template_entry(entry))

        enabled_targets = [target for target in targets if target.enabled]
        enabled_targets.sort(key=lambda item: item.priority, reverse=True)

        return cls(
            enabled_targets,
            workflow_node_bindings,
            global_retry_count=int(config.get("global_retry_count", 2) or 2),
            global_max_generation_count=int(config.get("global_max_generation_count", 2) or 2),
            output_dir=output_dir,
            counter=counter,
            global_send_strategy=parse_global_send_strategy(config.get("send_strategy")),
            global_fake_forward=parse_global_fake_forward(config.get("fake_forward")),
            workflow_runtime_default=WorkflowRuntimeConfig.from_raw(config.get("workflow_runtime_default")),
        )

    async def generate(
        self,
        *,
        mode: Mode,
        prompt: str,
        count: int = 1,
        input_images: list[str] | None = None,
    ) -> tuple[list[Path], str, SendStrategy, FakeForwardConfig]:
        requested_count = self._normalize_requested_count(mode, count)
        self.validate_request_count(requested_count, mode=mode)

        execution_errors: list[str] = []
        had_sensitive = False
        quota_exhausted_target_count = 0
        mode_unsupported_target_count = 0
        timeout = aiohttp.ClientTimeout(total=180)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for target in self.targets:
                if isinstance(target, WorkflowConfig) and not target.supports_mode(mode):
                    mode_unsupported_target_count += 1
                    continue

                if self._request_count_exceeds_limit(target, requested_count):
                    quota_exhausted_target_count += 1
                    execution_errors.append(f"{target.display_name}: 超出生成张数上限")
                    continue

                retry_count = self._resolve_retry_count(target)

                for attempt in range(retry_count):
                    try:
                        if attempt > 0:
                            delay = min(2**attempt, 10)
                            logger.info(
                                f"[{target.display_name}] 第 {attempt + 1}/{retry_count} 次重试，等待 {delay}s"
                            )
                            await asyncio.sleep(delay)

                        paths = await self._invoke_target(
                            target,
                            mode=mode,
                            prompt=prompt,
                            requested_count=requested_count,
                            input_images=input_images,
                            session=session,
                        )

                        if paths:
                            await self.counter.add_count(target.model_key(), len(paths))
                            effective_send_strategy = resolve_effective_send_strategy(
                                global_strategy=self.global_send_strategy,
                                entry_strategy=target.send_strategy,
                            )
                            effective_fake_forward = resolve_effective_fake_forward(
                                global_config=self.global_fake_forward,
                                entry_mode=target.fake_forward_mode,
                                entry_custom_qq=target.fake_forward_custom_qq,
                            )
                            return paths, target.display_name, effective_send_strategy, effective_fake_forward
                    except SensitiveContentError as exc:
                        had_sensitive = True
                        msg = f"{target.display_name}: {exc}"
                        logger.warning(msg)
                        execution_errors.append(msg)
                        break
                    except GenerationError as exc:
                        msg = f"{target.display_name}: {exc}"
                        logger.warning(msg)
                        if attempt == retry_count - 1:
                            execution_errors.append(msg)
                    except Exception as exc:
                        msg = f"{target.display_name}: {exc}"
                        logger.error(msg)
                        if attempt == retry_count - 1:
                            execution_errors.append(msg)

        if had_sensitive:
            raise SensitiveContentError(mode)

        if self.targets and quota_exhausted_target_count == len(self.targets):
            raise GenerationError("超出生成张数上限")

        if self.targets and mode_unsupported_target_count == len(self.targets):
            raise GenerationError(
                f"已启用的工作流暂不支持{describe_mode(mode)}，请配置支持对应模式的模型或工作流"
            )

        brief = execution_errors[-1] if execution_errors else "所有模型均生成失败"
        if len(brief) > 120:
            brief = brief[:117] + "..."
        raise GenerationError(brief)

    async def _invoke_target(
        self,
        target: GenerationTarget,
        *,
        mode: Mode,
        prompt: str,
        requested_count: int,
        input_images: list[str] | None,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        if isinstance(target, WorkflowConfig):
            node_bindings = self._get_workflow_node_bindings(target.workflow_id)
            runtime_config = target.resolve_runtime_config(self.workflow_runtime_default)
            workflow_runner = (
                self._a1111_runner
                if target.workflow_engine == "a1111"
                else self._comfyui_runner
            )

            if mode == "text_to_image":
                return await workflow_runner.generate_text_to_image(
                    prompt,
                    requested_count,
                    target,
                    node_bindings,
                    runtime_config,
                    self.output_dir,
                    session,
                )

            return await workflow_runner.generate_image_to_image(
                prompt,
                input_images or [],
                target,
                node_bindings,
                runtime_config,
                self.output_dir,
                session,
            )

        adapter = get_adapter(target.provider)
        if mode == "text_to_image":
            return await adapter.text_to_image(prompt, requested_count, target, self.output_dir, session)
        return await adapter.image_to_image(prompt, input_images or [], target, self.output_dir, session)

    def validate_request_count(self, requested_count: int, *, mode: Mode = "text_to_image") -> None:
        if not self.targets:
            raise GenerationError("未配置任何已启用的图像目标")

        applicable_targets = [
            target
            for target in self.targets
            if not isinstance(target, WorkflowConfig) or target.supports_mode(mode)
        ]

        if not applicable_targets:
            return

        if any(not self._request_count_exceeds_limit(target, requested_count) for target in applicable_targets):
            return

        raise GenerationError("超出生成张数上限")

    @staticmethod
    def _normalize_requested_count(mode: Mode, count: int) -> int:
        if mode == "image_to_image":
            return 1
        return max(1, count)

    def _request_count_exceeds_limit(self, target: GenerationTarget, requested_count: int) -> bool:
        limit = self._resolve_max_count(target)
        return limit >= 0 and requested_count > limit

    def _resolve_retry_count(self, target: GenerationTarget) -> int:
        if target.retry_count and target.retry_count > 0:
            return target.retry_count
        return self.global_retry_count

    def _resolve_max_count(self, target: GenerationTarget) -> int:
        if target.max_generation_count is not None and target.max_generation_count >= 0:
            return target.max_generation_count
        return self.global_max_generation_count

    def _get_workflow_node_bindings(self, workflow_id: str) -> list[WorkflowNodeBinding]:
        return [
            binding
            for binding in self.workflow_node_bindings
            if binding.workflow_id == workflow_id
        ]
