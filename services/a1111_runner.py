from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

import aiohttp

from ..adapters.base import GenerationError
from ..utils.storage import save_base64_image
from .workflow_config import WorkflowConfig, WorkflowNodeBinding, WorkflowRuntimeConfig
from .workflow_merge import merge_workflow_payload


class A1111WorkflowRunner:
    """Submit A1111 Stable Diffusion WebUI txt2img / img2img requests."""

    async def generate_text_to_image(
        self,
        prompt: str,
        count: int,
        workflow_config: WorkflowConfig,
        node_bindings: list[WorkflowNodeBinding],
        runtime_config: WorkflowRuntimeConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        return await self._generate(
            prompt=prompt,
            count=count,
            mode="text_to_image",
            input_images=None,
            workflow_config=workflow_config,
            node_bindings=node_bindings,
            runtime_config=runtime_config,
            output_dir=output_dir,
            session=session,
        )

    async def generate_image_to_image(
        self,
        prompt: str,
        input_images: list[str],
        workflow_config: WorkflowConfig,
        node_bindings: list[WorkflowNodeBinding],
        runtime_config: WorkflowRuntimeConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        if not input_images:
            raise GenerationError(f"工作流「{workflow_config.display_name}」执行图生图时缺少输入图片")

        return await self._generate(
            prompt=prompt,
            count=1,
            mode="image_to_image",
            input_images=input_images,
            workflow_config=workflow_config,
            node_bindings=node_bindings,
            runtime_config=runtime_config,
            output_dir=output_dir,
            session=session,
        )

    async def _generate(
        self,
        *,
        prompt: str,
        count: int,
        mode: str,
        input_images: list[str] | None,
        workflow_config: WorkflowConfig,
        node_bindings: list[WorkflowNodeBinding],
        runtime_config: WorkflowRuntimeConfig,
        output_dir: Path,
        session: aiohttp.ClientSession,
    ) -> list[Path]:
        payload = merge_workflow_payload(
            workflow_config,
            node_bindings,
            mode=mode,
            positive_prompt=prompt,
            input_images=input_images,
        )

        if mode == "image_to_image":
            init_images = self._resolve_init_images(payload, input_images or [])
            payload["init_images"] = init_images
            endpoint = "img2img"
        else:
            payload.pop("init_images", None)
            endpoint = "txt2img"

        payload.setdefault("batch_size", 1)
        payload.setdefault("n_iter", 1)
        try:
            batch_size = int(payload.get("batch_size") or 1)
        except (TypeError, ValueError, OverflowError) as exc:
            raise GenerationError("A1111 batch_size 必须是整数") from exc
        payload["batch_size"] = max(1, min(count, batch_size))
        payload["n_iter"] = 1

        url = f"{runtime_config.base_url}/sdapi/v1/{endpoint}"
        headers = self._build_headers(runtime_config)
        data = await self._post_json(session, url, headers, payload, workflow_config.display_name)

        images = data.get("images")
        if not isinstance(images, list) or not images:
            raise GenerationError(f"工作流「{workflow_config.display_name}」未返回任何图片输出")

        saved_paths: list[Path] = []
        for image_data in images[: max(1, count)]:
            if not isinstance(image_data, str) or not image_data.strip():
                continue
            saved_paths.append(
                await save_base64_image(image_data, output_dir, prefix="a1111")
            )

        if not saved_paths:
            raise GenerationError(f"工作流「{workflow_config.display_name}」返回的图片数据无效")
        return saved_paths

    @staticmethod
    def _build_headers(runtime_config: WorkflowRuntimeConfig) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if runtime_config.api_key:
            headers["Authorization"] = f"Bearer {runtime_config.api_key}"
        return headers

    @staticmethod
    def _resolve_init_images(payload: dict[str, Any], input_images: list[str]) -> list[str]:
        existing = payload.get("init_images")
        if isinstance(existing, list) and existing:
            normalized: list[str] = []
            for item in existing:
                if isinstance(item, str) and item.strip():
                    normalized.append(A1111WorkflowRunner._strip_data_url(item))
            if normalized:
                return normalized

        if not input_images:
            raise GenerationError("A1111 图生图缺少输入图片")

        return [A1111WorkflowRunner._strip_data_url(input_images[0])]

    @staticmethod
    def _strip_data_url(value: str) -> str:
        raw = (value or "").strip()
        if raw.startswith("data:image/") and "," in raw:
            raw = raw.split(",", 1)[-1]
        normalized_raw = "".join(raw.split())
        try:
            image_bytes = base64.b64decode(normalized_raw, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise GenerationError("输入图片不是有效的 base64 数据") from exc
        if not image_bytes:
            raise GenerationError("输入图片不是有效的 base64 数据")
        return normalized_raw

    async def _post_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        display_name: str,
    ) -> dict[str, Any]:
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                message = self._extract_error_message(data, resp.status)
                raise GenerationError(f"A1111 提交任务失败: {message}")
            if not isinstance(data, dict):
                raise GenerationError(f"工作流「{display_name}」返回格式异常")
            return data

    @staticmethod
    def _extract_error_message(data: Any, status: int) -> str:
        if isinstance(data, dict):
            if data.get("detail"):
                return str(data["detail"])
            if data.get("error"):
                return str(data["error"])
            if data.get("message"):
                return str(data["message"])
        return f"HTTP {status}"