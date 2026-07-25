from __future__ import annotations

import asyncio
from dataclasses import replace
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
from ..utils.config import parse_int
from ..utils.resolution import apply_prompt_resolution_if_auto

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
        global_timeout_seconds: int = 180,
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
        # -1 means unlimited for API models following global timeout.
        self.global_timeout_seconds = parse_int(global_timeout_seconds, 180)
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
            global_retry_count=parse_int(config.get("global_retry_count"), 2) or 2,
            global_max_generation_count=parse_int(
                config.get("global_max_generation_count"), 2
            ) or 2,
            global_timeout_seconds=parse_int(config.get("global_timeout_seconds"), 180),
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
        dedicated_command: str | None = None,
        size_override: str | None = None,
    ) -> tuple[list[Path], str, SendStrategy, FakeForwardConfig]:
        targets = self._select_targets(dedicated_command)
        requested_count = self._normalize_requested_count(mode, count)
        self.validate_request_count(
            requested_count, mode=mode, dedicated_command=dedicated_command
        )

        execution_errors: list[str] = []
        had_sensitive = False
        quota_exhausted_target_count = 0
        mode_unsupported_target_count = 0

        for target in targets:
            if not target.supports_mode(mode):
                mode_unsupported_target_count += 1
                continue

            if self._request_count_exceeds_limit(target, requested_count):
                quota_exhausted_target_count += 1
                execution_errors.append(f"{target.display_name}: 超出生成张数上限")
                continue

            retry_count = self._resolve_retry_count(target)
            client_timeout = self._build_client_timeout(target)

            for attempt in range(retry_count):
                try:
                    if attempt > 0:
                        delay = min(2**attempt, 10)
                        logger.info(
                            f"[{target.display_name}] 第 {attempt + 1}/{retry_count} 次重试，等待 {delay}s"
                        )
                        await asyncio.sleep(delay)

                    async with aiohttp.ClientSession(timeout=client_timeout) as session:
                        paths = await self._invoke_target_until_count(
                            target,
                            mode=mode,
                            prompt=prompt,
                            requested_count=requested_count,
                            input_images=input_images,
                            session=session,
                            size_override=size_override,
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
                except (asyncio.TimeoutError, TimeoutError):
                    timeout_label = self._format_timeout_label(target)
                    msg = f"{target.display_name}: 请求超时（{timeout_label}）"
                    logger.warning(msg)
                    if attempt == retry_count - 1:
                        execution_errors.append(msg)
                except Exception as exc:
                    detail = str(exc).strip() or type(exc).__name__
                    msg = f"{target.display_name}: {detail}"
                    logger.error(msg)
                    if attempt == retry_count - 1:
                        execution_errors.append(msg)

        if had_sensitive:
            raise SensitiveContentError(mode)

        if targets and quota_exhausted_target_count == len(targets):
            raise GenerationError("超出生成张数上限")

        if targets and mode_unsupported_target_count == len(targets):
            raise GenerationError(
                f"已启用的工作流暂不支持{describe_mode(mode)}，请配置支持对应模式的模型或工作流"
            )

        brief = execution_errors[-1] if execution_errors else "所有模型均生成失败"
        if len(brief) > 120:
            brief = brief[:117] + "..."
        raise GenerationError(brief)

    async def _invoke_target_until_count(
        self,
        target: GenerationTarget,
        *,
        mode: Mode,
        prompt: str,
        requested_count: int,
        input_images: list[str] | None,
        session: aiohttp.ClientSession,
        size_override: str | None = None,
    ) -> list[Path]:
        paths: list[Path] = []
        while len(paths) < requested_count:
            remaining_count = requested_count - len(paths)
            batch_paths = await self._invoke_target(
                target,
                mode=mode,
                prompt=prompt,
                requested_count=remaining_count,
                input_images=input_images,
                session=session,
                size_override=size_override,
            )
            if not batch_paths:
                raise GenerationError(f"{target.display_name} 未返回任何图片")
            paths.extend(batch_paths[:remaining_count])
        return paths

    async def _invoke_target(
        self,
        target: GenerationTarget,
        *,
        mode: Mode,
        prompt: str,
        requested_count: int,
        input_images: list[str] | None,
        session: aiohttp.ClientSession,
        size_override: str | None = None,
    ) -> list[Path]:
        if isinstance(target, WorkflowConfig):
            node_bindings = self._get_workflow_node_bindings(target.workflow_id)
            runtime_config = self._resolve_workflow_runtime_config(target)
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

        # Workflows keep their own fixed / bound sizes. For API models only:
        # when entry size is "auto", optionally promote an explicit resolution
        # from pre-resolution (regex/LLM) or a deterministic prompt parse.
        api_target = apply_prompt_resolution_if_auto(
            target,
            prompt,
            size_override=size_override,
        )
        if api_target.size != target.size:
            logger.info(
                f"[{target.display_name}] size=auto，使用提示词分辨率: {api_target.size}"
            )

        adapter = get_adapter(target.provider)
        if mode == "text_to_image":
            return await adapter.text_to_image(
                prompt, requested_count, api_target, self.output_dir, session
            )
        return await adapter.image_to_image(
            prompt, input_images or [], api_target, self.output_dir, session
        )

    def validate_request_count(
        self,
        requested_count: int,
        *,
        mode: Mode = "text_to_image",
        dedicated_command: str | None = None,
    ) -> None:
        targets = self._select_targets(dedicated_command)
        if not targets:
            raise GenerationError("默认指令没有可用的图像目标")

        applicable_targets = [
            target
            for target in targets
            if target.supports_mode(mode)
        ]

        if not applicable_targets:
            return

        if any(not self._request_count_exceeds_limit(target, requested_count) for target in applicable_targets):
            return

        raise GenerationError("超出生成张数上限")

    def _select_targets(self, dedicated_command: str | None) -> list[GenerationTarget]:
        if dedicated_command:
            targets = [
                target
                for target in self.targets
                if target.dedicated_command == dedicated_command
            ]
            if not targets:
                raise GenerationError(f"未找到专属指令 /{dedicated_command} 对应的图像目标")
            return targets
        return [target for target in self.targets if not target.dedicated_command]

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

    def _resolve_configured_timeout_seconds(self, target: GenerationTarget) -> int | None:
        """Return configured timeout seconds, or None for unlimited.

        Both API models and workflows follow either the global default timeout
        or a per-entry custom value (timeout_mode / timeout_seconds).
        """
        if getattr(target, "timeout_mode", "follow_global") == "custom":
            seconds = parse_int(getattr(target, "timeout_seconds", -1), -1)
        else:
            seconds = parse_int(self.global_timeout_seconds, 180)

        if seconds < 0:
            return None
        return max(1, seconds)

    def _resolve_workflow_runtime_config(self, target: WorkflowConfig) -> WorkflowRuntimeConfig:
        """Apply entry/global timeout onto the workflow runtime config used for polling."""
        runtime_config = target.resolve_runtime_config(self.workflow_runtime_default)
        configured = self._resolve_configured_timeout_seconds(target)
        if configured is None:
            # Practical "unlimited" for polling loops that require a numeric deadline.
            return replace(runtime_config, timeout_seconds=365 * 24 * 3600)
        return replace(runtime_config, timeout_seconds=configured)

    def _build_client_timeout(self, target: GenerationTarget) -> aiohttp.ClientTimeout:
        configured = self._resolve_configured_timeout_seconds(target)
        if configured is None:
            return aiohttp.ClientTimeout(total=None)
        # Workflow sessions keep a small buffer so polling can finish near the limit.
        if isinstance(target, WorkflowConfig):
            return aiohttp.ClientTimeout(total=max(1, configured + 30))
        return aiohttp.ClientTimeout(total=configured)

    def _format_timeout_label(self, target: GenerationTarget) -> str:
        configured = self._resolve_configured_timeout_seconds(target)
        if configured is None:
            return "不限制"
        return f"{configured}s"

    def _get_workflow_node_bindings(self, workflow_id: str) -> list[WorkflowNodeBinding]:
        return [
            binding
            for binding in self.workflow_node_bindings
            if binding.workflow_id == workflow_id
        ]
