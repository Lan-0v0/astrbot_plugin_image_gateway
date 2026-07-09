from __future__ import annotations

import copy
import json
import random
from typing import Any

from ..adapters.base import GenerationError
from ..utils.json_path import set_by_dot_path
from .workflow_config import WorkflowConfig, WorkflowNodeBinding

_SKIP_BINDING = object()


def merge_workflow_payload(
    workflow_config: WorkflowConfig,
    node_bindings: list[WorkflowNodeBinding],
    *,
    mode: str = "text_to_image",
    positive_prompt: str,
    input_images: list[str] | None = None,
) -> dict[str, Any]:
    """Overlay configured node bindings onto the workflow's raw JSON content.

    Each binding is applied via explicit node_id + field_path targeting,
    overwriting whatever value already exists in the exported workflow JSON.
    """
    workflow_payload = copy.deepcopy(workflow_config.parsed_workflow_content())

    for binding in node_bindings:
        _apply_single_binding(
            workflow_payload,
            binding,
            workflow_display_name=workflow_config.display_name,
            mode=mode,
            positive_prompt=positive_prompt,
            input_images=input_images or [],
        )

    return workflow_payload


def _apply_single_binding(
    workflow_payload: dict[str, Any],
    binding: WorkflowNodeBinding,
    *,
    workflow_display_name: str,
    mode: str,
    positive_prompt: str,
    input_images: list[str],
) -> None:
    node_id = (binding.node_id or "").strip()
    field_path = binding.field_path

    if not field_path:
        raise GenerationError(
            f"工作流「{workflow_display_name}」存在缺少字段路径的绑定配置"
        )

    if node_id in {"_root", "root", "__root__"}:
        node_payload = workflow_payload
    else:
        if not node_id:
            raise GenerationError(
                f"工作流「{workflow_display_name}」存在缺少节点ID的绑定配置"
            )
        node_payload = workflow_payload.get(node_id)
        if not isinstance(node_payload, dict):
            raise GenerationError(
                f"工作流「{workflow_display_name}」中未找到节点 {node_id}，无法应用绑定"
            )

    resolved_value = _resolve_binding_value(
        binding,
        mode=mode,
        workflow_display_name=workflow_display_name,
        positive_prompt=positive_prompt,
        input_images=input_images,
    )

    if resolved_value is _SKIP_BINDING:
        return

    try:
        set_by_dot_path(node_payload, field_path, resolved_value)
    except (KeyError, IndexError, TypeError) as exc:
        raise GenerationError(
            f"工作流「{workflow_display_name}」节点 {node_id} 的字段路径 {field_path} 无效: {exc}"
        ) from exc


def field_targets_init_images(binding: WorkflowNodeBinding) -> bool:
    field_path = (binding.field_path or "").strip().lower()
    return field_path in {"init_images", "init_images.0"}


def _resolve_binding_value(
    binding: WorkflowNodeBinding,
    *,
    mode: str,
    workflow_display_name: str,
    positive_prompt: str,
    input_images: list[str],
) -> Any:
    binding_type = binding.binding_type

    if binding_type == "prompt_positive":
        return positive_prompt

    if binding_type == "prompt_negative":
        return binding.custom_value

    if binding_type == "custom_text":
        return binding.custom_value

    if binding_type == "seed":
        return _resolve_numeric_value(binding.custom_value, allow_random_int=True)

    if binding_type == "custom_number":
        return _resolve_numeric_value(binding.custom_value, allow_random_int=False)

    if binding_type == "image_input":
        if not input_images:
            return _SKIP_BINDING
        image_value = input_images[0]
        if field_targets_init_images(binding):
            return [image_value]
        return image_value

    if binding_type == "mode_switch_text":
        return _resolve_mode_switch_text(binding, mode=mode)

    if binding_type == "mode_switch_number":
        return _resolve_numeric_value(
            _resolve_mode_switch_text(binding, mode=mode),
            allow_random_int=False,
        )

    if binding_type == "mode_switch_json":
        raw_value = _resolve_mode_switch_text(binding, mode=mode)
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise GenerationError(
                f"工作流「{workflow_display_name}」的模式切换 JSON 配置无效: {raw_value!r}"
            ) from exc

    raise GenerationError(f"不支持的绑定类型: {binding_type}")


def _resolve_mode_switch_text(binding: WorkflowNodeBinding, *, mode: str) -> str:
    if mode == "image_to_image":
        return binding.image_to_image_value
    return binding.text_to_image_value


def _resolve_numeric_value(raw_value: str, *, allow_random_int: bool) -> int | float:
    text_value = (raw_value or "").strip()

    if not text_value:
        if allow_random_int:
            return random.randint(0, 2**32 - 1)
        raise GenerationError("自定义数值绑定不能为空")

    try:
        if "." in text_value:
            return float(text_value)
        return int(text_value)
    except ValueError as exc:
        raise GenerationError(f"数值绑定内容不是合法数字: {text_value!r}") from exc
