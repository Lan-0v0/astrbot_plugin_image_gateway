from __future__ import annotations

import asyncio
import base64
import binascii
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any

import aiohttp

from ..adapters.base import GenerationError
from ..utils.storage import save_binary_image
from .workflow_config import WorkflowConfig, WorkflowNodeBinding, WorkflowRuntimeConfig
from .workflow_merge import merge_workflow_payload


class ComfyUIWorkflowRunner:
    """Submit ComfyUI workflows for both text-to-image and image-to-image modes."""

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
        headers = self._build_headers(runtime_config)
        uploaded_image_names: list[str] = []
        if input_images:
            uploaded_image_names = await self._upload_input_images(
                session,
                runtime_config.base_url,
                headers,
                input_images,
            )

        payload = merge_workflow_payload(
            workflow_config,
            node_bindings,
            mode=mode,
            positive_prompt=prompt,
            input_images=uploaded_image_names,
        )

        client_id = str(uuid.uuid4())
        prompt_id = await self._submit_prompt(session, runtime_config.base_url, headers, payload, client_id)
        history_entry = await self._wait_for_history(
            session,
            runtime_config.base_url,
            headers,
            prompt_id,
            timeout_seconds=runtime_config.timeout_seconds,
            poll_interval_seconds=runtime_config.poll_interval_seconds,
        )

        image_references = self._extract_image_references(history_entry)
        if not image_references:
            raise GenerationError(f"工作流「{workflow_config.display_name}」未返回任何图片输出")

        saved_paths: list[Path] = []
        for image_reference in image_references[: max(1, count)]:
            image_bytes = await self._download_image(session, runtime_config.base_url, headers, image_reference)
            saved_paths.append(await save_binary_image(image_bytes, output_dir, prefix="comfyui"))
        return saved_paths

    @staticmethod
    def _build_headers(runtime_config: WorkflowRuntimeConfig) -> dict[str, str]:
        headers: dict[str, str] = {}
        if runtime_config.api_key:
            headers["Authorization"] = f"Bearer {runtime_config.api_key}"
        return headers

    async def _upload_input_images(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        headers: dict[str, str],
        input_images: list[str],
    ) -> list[str]:
        uploaded_images: list[str] = []
        for index, image_payload in enumerate(input_images):
            image_bytes, extension, mime_type = self._decode_base64_image(image_payload)
            filename = f"astrbot_input_{uuid.uuid4().hex[:12]}_{index}.{extension}"
            form = aiohttp.FormData()
            form.add_field(
                "image",
                image_bytes,
                filename=filename,
                content_type=mime_type,
            )
            url = f"{base_url}/upload/image"
            async with session.post(url, data=form, headers=headers) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    message = self._extract_error_message(data, resp.status)
                    raise GenerationError(f"ComfyUI 上传输入图片失败: {message}")

            uploaded_name = ""
            if isinstance(data, dict):
                uploaded_name = str(data.get("name") or data.get("filename") or "").strip()
            if not uploaded_name:
                raise GenerationError("ComfyUI 上传输入图片响应缺少文件名")
            uploaded_images.append(uploaded_name)
        return uploaded_images

    @staticmethod
    def _decode_base64_image(image_payload: str) -> tuple[bytes, str, str]:
        raw_payload = (image_payload or "").strip()
        mime_type = "image/png"
        extension = "png"

        if raw_payload.startswith("data:") and "," in raw_payload:
            header, raw_payload = raw_payload.split(",", 1)
            mime_type = header[5:].split(";", 1)[0] or mime_type
            guessed_extension = mimetypes.guess_extension(mime_type) or ".png"
            extension = guessed_extension.lstrip(".") or "png"

        try:
            image_bytes = base64.b64decode(
                "".join(raw_payload.split()), validate=True
            )
        except (ValueError, binascii.Error) as exc:
            raise GenerationError("输入图片不是有效的 base64 数据") from exc
        if not image_bytes:
            raise GenerationError("输入图片不是有效的 base64 数据")
        return image_bytes, extension, mime_type

    async def _submit_prompt(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        client_id: str,
    ) -> str:
        url = f"{base_url}/prompt"
        body = {"prompt": payload, "client_id": client_id}
        async with session.post(url, json=body, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                message = self._extract_error_message(data, resp.status)
                raise GenerationError(f"ComfyUI 提交任务失败: {message}")
            if not isinstance(data, dict) or not data.get("prompt_id"):
                raise GenerationError("ComfyUI 提交任务响应缺少 prompt_id")
            return str(data["prompt_id"])

    async def _wait_for_history(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        headers: dict[str, str],
        prompt_id: str,
        *,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> dict[str, Any]:
        url = f"{base_url}/history/{prompt_id}"
        poll_interval_seconds = max(0.1, poll_interval_seconds)
        deadline = time.monotonic() + max(1, timeout_seconds)

        while time.monotonic() < deadline:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    message = self._extract_error_message(data, resp.status)
                    raise GenerationError(f"ComfyUI 查询任务失败: {message}")
                if isinstance(data, dict) and prompt_id in data:
                    history_entry = data[prompt_id]
                    if isinstance(history_entry, dict):
                        if history_entry.get("outputs"):
                            return history_entry
                        history_error = self._extract_history_error(history_entry)
                        if history_error:
                            raise GenerationError(
                                f"ComfyUI 任务执行失败: {history_error}"
                            )

            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds > 0:
                await asyncio.sleep(min(poll_interval_seconds, remaining_seconds))

        raise GenerationError("ComfyUI 任务超时，未在指定时间内完成")

    @staticmethod
    def _extract_history_error(history_entry: dict[str, Any]) -> str:
        status = history_entry.get("status")
        if not isinstance(status, dict):
            return ""
        messages = status.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if not isinstance(message, list) or len(message) < 2:
                    continue
                details = message[1]
                if isinstance(details, dict):
                    error = details.get("exception_message") or details.get("error")
                    if error:
                        return str(error)
        status_text = str(status.get("status_str") or "").lower()
        if status_text in {"error", "failed"} or status.get("completed") is True:
            return status_text or "任务结束但没有图片输出"
        return ""

    @staticmethod
    def _extract_image_references(history_entry: dict[str, Any]) -> list[dict[str, str]]:
        image_references: list[dict[str, str]] = []
        outputs = history_entry.get("outputs") or {}
        if not isinstance(outputs, dict):
            return image_references

        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            images = node_output.get("images")
            if not isinstance(images, list):
                continue
            for image_entry in images:
                if isinstance(image_entry, dict) and image_entry.get("filename"):
                    image_references.append(image_entry)
        return image_references

    async def _download_image(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        headers: dict[str, str],
        image_reference: dict[str, str],
    ) -> bytes:
        params = {
            "filename": image_reference.get("filename", ""),
            "subfolder": image_reference.get("subfolder", ""),
            "type": image_reference.get("type", "output"),
        }
        url = f"{base_url}/view"
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                raise GenerationError(f"ComfyUI 下载图片失败: HTTP {resp.status}")
            return await resp.read()

    @staticmethod
    def _extract_error_message(data: Any, status: int) -> str:
        if isinstance(data, dict):
            error_field = data.get("error")
            if isinstance(error_field, dict) and error_field.get("message"):
                return str(error_field["message"])
            if isinstance(error_field, str):
                return error_field
        return f"HTTP {status}"
