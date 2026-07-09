from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..adapters.base import GenerationError
from .fake_forward import normalize_custom_qq, parse_entry_fake_forward_mode
from .priority import resolve_priority_value
from .send_strategy import parse_entry_send_strategy

SUPPORTED_BINDING_TYPES = {
    "prompt_positive",
    "prompt_negative",
    "image_input",
    "seed",
    "custom_text",
    "custom_number",
    "mode_switch_text",
    "mode_switch_number",
    "mode_switch_json",
}

SUPPORTED_WORKFLOW_MODES = {"text_to_image", "image_to_image"}
SUPPORTED_WORKFLOW_ENGINES = {"comfyui", "a1111"}
DEFAULT_WORKFLOW_ENGINE = "comfyui"


@dataclass
class WorkflowNodeBinding:
    """A single ``node_id + field_path`` override applied to a workflow payload."""

    workflow_id: str
    node_id: str
    field_path: str
    binding_type: str
    custom_value: str = ""
    text_to_image_value: str = ""
    image_to_image_value: str = ""

    @classmethod
    def from_template_entry(cls, entry: dict[str, Any]) -> WorkflowNodeBinding:
        binding_type = str(entry.get("binding_type") or "custom_text").strip().lower()
        if binding_type not in SUPPORTED_BINDING_TYPES:
            binding_type = "custom_text"

        custom_value = str(entry.get("custom_value") or "")
        if binding_type == "prompt_negative":
            custom_value = str(entry.get("prompt_negative_value") or custom_value)
        elif binding_type == "custom_text":
            custom_value = str(entry.get("custom_text_value") or custom_value)
        elif binding_type == "seed":
            custom_value = str(entry.get("seed_value") or custom_value)
        elif binding_type == "custom_number":
            custom_value = str(entry.get("custom_number_value") or custom_value)

        text_to_image_value = str(entry.get("text_to_image_value") or "").strip()
        image_to_image_value = str(entry.get("image_to_image_value") or "").strip()
        if binding_type.startswith("mode_switch_"):
            text_to_image_value = _resolve_mode_switch_entry_value(
                entry,
                suffix="text_to_image_value",
                binding_type=binding_type,
                fallback=text_to_image_value,
            )
            image_to_image_value = _resolve_mode_switch_entry_value(
                entry,
                suffix="image_to_image_value",
                binding_type=binding_type,
                fallback=image_to_image_value,
            )

        return cls(
            workflow_id=str(entry.get("workflow_id") or "").strip(),
            node_id=str(entry.get("node_id") or "").strip(),
            field_path=str(entry.get("field_path") or "").strip(),
            binding_type=binding_type,
            custom_value=custom_value,
            text_to_image_value=text_to_image_value,
            image_to_image_value=image_to_image_value,
        )


def _resolve_mode_switch_entry_value(
    entry: dict[str, Any],
    *,
    suffix: str,
    binding_type: str,
    fallback: str,
) -> str:
    type_specific_key = f"{binding_type}_{suffix}"
    type_specific_value = str(entry.get(type_specific_key) or "").strip()
    return type_specific_value or fallback


@dataclass
class WorkflowRuntimeConfig:
    """Connection details for a workflow execution backend (e.g. ComfyUI)."""

    base_url: str = "http://127.0.0.1:8188"
    api_key: str = ""
    poll_interval_seconds: float = 1.0
    timeout_seconds: int = 300

    @classmethod
    def from_raw(cls, raw_config: Any) -> WorkflowRuntimeConfig:
        config_dict = raw_config if isinstance(raw_config, dict) else {}
        return cls(
            base_url=str(config_dict.get("base_url") or "http://127.0.0.1:8188").strip().rstrip("/"),
            api_key=str(config_dict.get("api_key") or "").strip(),
            poll_interval_seconds=float(config_dict.get("poll_interval_seconds") or 1.0),
            timeout_seconds=int(config_dict.get("timeout_seconds") or 300),
        )

    def with_overrides(self, *, base_url_override: str, api_key_override: str) -> WorkflowRuntimeConfig:
        return WorkflowRuntimeConfig(
            base_url=(base_url_override.strip().rstrip("/") if base_url_override.strip() else self.base_url),
            api_key=(api_key_override.strip() if api_key_override.strip() else self.api_key),
            poll_interval_seconds=self.poll_interval_seconds,
            timeout_seconds=self.timeout_seconds,
        )


@dataclass
class WorkflowConfig:
    """A single configured workflow entry (e.g. a ComfyUI graph)."""

    workflow_id: str
    display_name: str
    workflow_content_raw: str
    priority: int = 0
    enabled: bool = True
    retry_count: int = -1
    max_generation_count: int = -1
    send_strategy: str = "follow_global"
    fake_forward_mode: str = "follow_global"
    fake_forward_custom_qq: str = ""
    runtime_base_url_override: str = ""
    runtime_api_key_override: str = ""
    supported_modes: list[str] = field(default_factory=lambda: ["text_to_image"])
    workflow_engine: str = DEFAULT_WORKFLOW_ENGINE
    kind: str = "workflow"
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_template_entry(cls, entry: dict[str, Any]) -> WorkflowConfig:
        workflow_id = str(entry.get("workflow_id") or "").strip() or str(
            entry.get("display_name") or "未命名工作流"
        ).strip()
        display_name = workflow_id or "未命名工作流"

        workflow_engine = _normalize_workflow_engine(
            entry.get("__template_key")
            or entry.get("_template")
            or entry.get("template")
            or entry.get("workflow_engine")
            or entry.get("workflow_type")
        )

        return cls(
            workflow_id=workflow_id,
            display_name=display_name,
            workflow_content_raw=str(entry.get("workflow_content") or ""),
            priority=resolve_priority_value(entry, default_priority=10),
            enabled=bool(entry.get("enabled", True)),
            retry_count=int(entry.get("retry_count", -1)),
            max_generation_count=int(entry.get("max_generation_count", -1)),
            send_strategy=parse_entry_send_strategy(entry.get("send_strategy")),
            fake_forward_mode=parse_entry_fake_forward_mode(entry.get("fake_forward_mode")),
            fake_forward_custom_qq=normalize_custom_qq(entry.get("fake_forward_custom_qq")),
            runtime_base_url_override=str(entry.get("runtime_base_url_override") or "").strip(),
            runtime_api_key_override=str(entry.get("runtime_api_key_override") or "").strip(),
            supported_modes=_normalize_supported_modes(entry.get("supported_modes")),
            workflow_engine=workflow_engine,
            raw=entry,
        )

    def model_key(self) -> str:
        return f"workflow|{self.workflow_engine}|{self.workflow_id}|{self.display_name}"

    def parsed_workflow_content(self) -> dict[str, Any]:
        try:
            parsed_content = json.loads(self.workflow_content_raw or "{}")
        except json.JSONDecodeError as exc:
            raise GenerationError(f"工作流「{self.display_name}」的 JSON 解析失败: {exc}") from exc

        if not isinstance(parsed_content, dict):
            raise GenerationError(f"工作流「{self.display_name}」的内容必须是 JSON 对象")

        return parsed_content

    def resolve_runtime_config(self, default_runtime: WorkflowRuntimeConfig) -> WorkflowRuntimeConfig:
        return default_runtime.with_overrides(
            base_url_override=self.runtime_base_url_override,
            api_key_override=self.runtime_api_key_override,
        )

    def supports_mode(self, mode: str) -> bool:
        return mode in self.supported_modes


def _normalize_workflow_engine(raw_value: Any) -> str:
    engine = str(raw_value or DEFAULT_WORKFLOW_ENGINE).strip().lower()
    if engine in SUPPORTED_WORKFLOW_ENGINES:
        return engine
    return DEFAULT_WORKFLOW_ENGINE


def normalize_supported_modes(
    raw_value: Any,
    *,
    default_modes: list[str] | None = None,
) -> list[str]:
    if isinstance(raw_value, str) and raw_value.strip().lower() == "both":
        raw_modes = ["text_to_image", "image_to_image"]
    elif isinstance(raw_value, list):
        raw_modes = raw_value
    elif isinstance(raw_value, str):
        raw_modes = [raw_value]
    else:
        raw_modes = []

    normalized_modes: list[str] = []
    for raw_mode in raw_modes:
        mode = str(raw_mode or "").strip().lower()
        if mode in SUPPORTED_WORKFLOW_MODES and mode not in normalized_modes:
            normalized_modes.append(mode)

    fallback_modes = default_modes or ["text_to_image"]
    return normalized_modes or list(fallback_modes)


def _normalize_supported_modes(raw_value: Any) -> list[str]:
    return normalize_supported_modes(raw_value)


def describe_mode(mode: str) -> str:
    if mode == "image_to_image":
        return "改图"
    return "文生图"
