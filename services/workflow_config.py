from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..adapters.base import GenerationError
from .send_strategy import parse_entry_send_strategy

SUPPORTED_WORKFLOW_TYPES = {"comfyui"}

SUPPORTED_BINDING_TYPES = {
    "prompt_positive",
    "prompt_negative",
    "image_input",
    "seed",
    "custom_text",
    "custom_number",
}


@dataclass
class WorkflowNodeBinding:
    """A single ``node_id + field_path`` override applied to a workflow payload."""

    workflow_id: str
    node_id: str
    field_path: str
    binding_type: str
    custom_value: str = ""

    @classmethod
    def from_template_entry(cls, entry: dict[str, Any]) -> WorkflowNodeBinding:
        binding_type = str(entry.get("binding_type") or "custom_text").strip().lower()
        if binding_type not in SUPPORTED_BINDING_TYPES:
            binding_type = "custom_text"

        return cls(
            workflow_id=str(entry.get("workflow_id") or "").strip(),
            node_id=str(entry.get("node_id") or "").strip(),
            field_path=str(entry.get("field_path") or "").strip(),
            binding_type=binding_type,
            custom_value=str(entry.get("custom_value") or ""),
        )


@dataclass
class WorkflowRuntimeConfig:
    """Connection details for a workflow execution backend (e.g. ComfyUI)."""

    base_url: str = "http://127.0.0.1:8188"
    api_key: str = ""
    poll_interval_seconds: float = 1.0
    timeout_seconds: int = 180

    @classmethod
    def from_raw(cls, raw_config: Any) -> WorkflowRuntimeConfig:
        config_dict = raw_config if isinstance(raw_config, dict) else {}
        return cls(
            base_url=str(config_dict.get("base_url") or "http://127.0.0.1:8188").strip().rstrip("/"),
            api_key=str(config_dict.get("api_key") or "").strip(),
            poll_interval_seconds=float(config_dict.get("poll_interval_seconds") or 1.0),
            timeout_seconds=int(config_dict.get("timeout_seconds") or 180),
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
    workflow_type: str
    workflow_content_raw: str
    priority: int = 0
    enabled: bool = True
    retry_count: int = -1
    max_generation_count: int = -1
    send_strategy: str = "follow_global"
    runtime_base_url_override: str = ""
    runtime_api_key_override: str = ""
    kind: str = "workflow"
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_template_entry(cls, entry: dict[str, Any]) -> WorkflowConfig:
        workflow_type = str(entry.get("workflow_type") or "comfyui").strip().lower()
        if workflow_type not in SUPPORTED_WORKFLOW_TYPES:
            workflow_type = "comfyui"

        workflow_id = str(entry.get("workflow_id") or "").strip() or str(
            entry.get("display_name") or "未命名工作流"
        ).strip()

        return cls(
            workflow_id=workflow_id,
            display_name=str(entry.get("display_name") or "未命名工作流"),
            workflow_type=workflow_type,
            workflow_content_raw=str(entry.get("workflow_content") or ""),
            priority=int(entry.get("priority") or 0),
            enabled=bool(entry.get("enabled", True)),
            retry_count=int(entry.get("retry_count", -1)),
            max_generation_count=int(entry.get("max_generation_count", -1)),
            send_strategy=parse_entry_send_strategy(entry.get("send_strategy")),
            runtime_base_url_override=str(entry.get("runtime_base_url_override") or "").strip(),
            runtime_api_key_override=str(entry.get("runtime_api_key_override") or "").strip(),
            raw=entry,
        )

    def model_key(self) -> str:
        return f"workflow|{self.workflow_type}|{self.workflow_id}|{self.display_name}"

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
