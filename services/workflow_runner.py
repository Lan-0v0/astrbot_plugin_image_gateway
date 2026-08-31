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
from astrbot.api import logger

from ..adapters.base import GenerationError
from ..utils.storage import save_binary_image
from .workflow_config import WorkflowConfig, WorkflowNodeBinding, WorkflowRuntimeConfig
from .workflow_merge import merge_workflow_payload


class ComfyUIWorkflowRunner:
    """Submit ComfyUI workflows for both text-to-image and image-to-image modes."""

    # Extra waiting granted while ComfyUI still reports the prompt as queued.
    QUEUE_GRACE_SECONDS = 60
    MAX_QUEUE_GRACE_ROUNDS = 30

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
        logger.info(
            f"工作流「{workflow_config.display_name}」已提交 ComfyUI，prompt_id={prompt_id}，"
            f"轮询超时 {runtime_config.timeout_seconds}s"
        )
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
        logger.info(
            f"ComfyUI 任务 {prompt_id} 返回 {len(image_references)} 张图片，"
            f"将取回前 {min(len(image_references), max(1, count))} 张"
        )

        saved_paths: list[Path] = []
        for image_reference in image_references[: max(1, count)]:
            image_bytes = await self._download_image(session, runtime_config.base_url, headers, image_reference)
            saved_paths.append(await save_binary_image(image_bytes, output_dir, prefix="comfyui"))
        logger.info(f"ComfyUI 任务 {prompt_id} 图片取回完成，已保存 {len(saved_paths)} 张，准备发送")
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
        """Poll ``/history`` until the prompt produces outputs.

        The deadline is only enforced when ComfyUI has actually stopped working on
        the prompt. A queued or running prompt keeps the wait alive in grace
        windows, because abandoning a job that ComfyUI is still executing throws
        away an image that lands moments later — the timeout is meant to catch a
        lost job, not a slow one.
        """
        url = f"{base_url}/history/{prompt_id}"
        poll_interval_seconds = max(0.1, poll_interval_seconds)
        deadline = time.monotonic() + max(1, timeout_seconds)
        grace_rounds_left = self.MAX_QUEUE_GRACE_ROUNDS
        polls = 0

        while True:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    message = self._extract_error_message(data, resp.status)
                    raise GenerationError(f"ComfyUI 查询任务失败: {message}")
                polls += 1
                if isinstance(data, dict) and prompt_id in data:
                    history_entry = data[prompt_id]
                    if isinstance(history_entry, dict):
                        if history_entry.get("outputs"):
                            logger.info(
                                f"ComfyUI 任务 {prompt_id} 已完成（轮询 {polls} 次），开始取回图片"
                            )
                            return history_entry
                        history_error = self._extract_history_error(history_entry)
                        if history_error:
                            raise GenerationError(
                                f"ComfyUI 任务执行失败: {history_error}"
                            )

            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds > 0:
                await asyncio.sleep(min(poll_interval_seconds, remaining_seconds))
                continue

            # Deadline reached. Only give up if ComfyUI no longer has the prompt:
            # the image is often written between the last poll and this check.
            if not await self._is_prompt_active(session, base_url, headers, prompt_id):
                break
            if grace_rounds_left <= 0:
                raise GenerationError(
                    "ComfyUI 任务仍在队列中但已超过等待上限，"
                    f"已等待约 {int(timeout_seconds + self.MAX_QUEUE_GRACE_ROUNDS * self.QUEUE_GRACE_SECONDS)}s，"
                    "请提高该工作流的超时时间或检查 ComfyUI 是否卡住"
                )
            grace_rounds_left -= 1
            deadline = time.monotonic() + self.QUEUE_GRACE_SECONDS
            logger.info(
                f"ComfyUI 任务 {prompt_id} 已超过设定超时但仍在队列中执行，"
                f"继续等待 {self.QUEUE_GRACE_SECONDS}s（剩余宽限 {grace_rounds_left} 轮）"
            )
            await asyncio.sleep(poll_interval_seconds)

        raise GenerationError(
            f"ComfyUI 任务超时，未在指定时间内完成（已轮询 {polls} 次，"
            "且 ComfyUI 队列中已无该任务）"
        )

    async def _is_prompt_active(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        headers: dict[str, str],
        prompt_id: str,
    ) -> bool:
        """Report whether ComfyUI still lists the prompt as running or pending.

        A failure to read ``/queue`` is treated as "still active" so a transient
        error on the liveness check cannot discard a job that is fine.
        """
        try:
            async with session.get(f"{base_url}/queue", headers=headers) as resp:
                if resp.status != 200:
                    return True
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            logger.warning(f"ComfyUI 队列状态查询失败，按仍在执行处理: {exc}")
            return True

        if not isinstance(data, dict):
            return True
        for queue_key in ("queue_running", "queue_pending"):
            entries = data.get(queue_key)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, (list, tuple)):
                    continue
                # Queue items are tuples of (number, prompt_id, prompt, extra, outputs).
                if any(str(field) == prompt_id for field in entry[:2]):
                    return True
        return False

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
        """Collect output images, listing saved results before temporary previews.

        Workflows built on node packs such as Impact Pack often contain a
        PreviewImage node alongside SaveImage. Preview images land in ComfyUI's
        ``temp`` directory and get cleaned up, so taking them first can download
        the wrong picture or fail outright even though the real output exists.
        """
        saved_references: list[dict[str, str]] = []
        temporary_references: list[dict[str, str]] = []
        outputs = history_entry.get("outputs") or {}
        if not isinstance(outputs, dict):
            return []

        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            images = node_output.get("images")
            if not isinstance(images, list):
                continue
            for image_entry in images:
                if not isinstance(image_entry, dict) or not image_entry.get("filename"):
                    continue
                image_type = str(image_entry.get("type") or "").strip().lower()
                if image_type and image_type != "output":
                    temporary_references.append(image_entry)
                else:
                    saved_references.append(image_entry)
        return saved_references + temporary_references

    async def _download_image(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        headers: dict[str, str],
        image_reference: dict[str, str],
    ) -> bytes:
        filename = str(image_reference.get("filename") or "").strip()
        if not filename:
            raise GenerationError("ComfyUI 输出缺少图片文件名")

        last_error = ""
        attempts = self._build_download_attempts(base_url, image_reference)
        for attempt_index, (params, url) in enumerate(attempts, start=1):
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    image_bytes = await resp.read()
                    if image_bytes:
                        return image_bytes
                    last_error = "返回了空图片数据"
                else:
                    last_error = await self._describe_download_failure(resp)
            logger.warning(
                f"ComfyUI 下载图片 {filename} 第 {attempt_index}/{len(attempts)} 次尝试失败"
                f"（{url}，参数 {params}）: {last_error}"
            )

        raise GenerationError(f"ComfyUI 下载图片失败: {last_error or '未知错误'}")

    @staticmethod
    def _build_download_attempts(
        base_url: str,
        image_reference: dict[str, str],
    ) -> list[tuple[dict[str, str], str]]:
        """Build the ordered ``/view`` attempts used to fetch one finished image.

        ``subfolder`` and ``type`` are only sent when non-empty. ComfyUI runs its
        path-traversal guard whenever ``subfolder`` is *present* in the query, and
        that guard compares ``os.path.abspath(...)`` against its raw configured
        output dir — so an output dir written with forward slashes or a trailing
        separator makes an empty ``subfolder=`` return HTTP 403 even though the
        image generated fine. Omitting the empty value skips the guard entirely.

        ``/api/view`` is retried afterwards because reverse proxies in front of
        ComfyUI commonly expose only the ``/api`` prefixed routes.
        """
        params: dict[str, str] = {"filename": str(image_reference.get("filename") or "").strip()}

        subfolder = str(image_reference.get("subfolder") or "").strip()
        if subfolder:
            params["subfolder"] = subfolder

        image_type = str(image_reference.get("type") or "").strip()
        if image_type:
            params["type"] = image_type

        attempts: list[tuple[dict[str, str], str]] = [
            (params, f"{base_url}/view"),
            (params, f"{base_url}/api/view"),
        ]

        if subfolder:
            # Last resort for the guard above: ComfyUI reduces the filename with
            # ``os.path.basename``, so a root-level retry can still resolve.
            params_without_subfolder = {
                key: value for key, value in params.items() if key != "subfolder"
            }
            attempts.append((params_without_subfolder, f"{base_url}/view"))

        return attempts

    @staticmethod
    async def _describe_download_failure(resp: aiohttp.ClientResponse) -> str:
        """Turn a failed ``/view`` response into an actionable message."""
        detail = ""
        try:
            detail = (await resp.text())[:200].strip()
        except Exception:
            detail = ""

        if resp.status == 403:
            return (
                "HTTP 403（ComfyUI 拒绝了图片下载请求，"
                "通常是 ComfyUI 输出目录配置或反向代理限制导致，图片其实已生成）"
            )
        if detail:
            return f"HTTP {resp.status}: {detail}"
        return f"HTTP {resp.status}"

    @staticmethod
    def _extract_error_message(data: Any, status: int) -> str:
        if isinstance(data, dict):
            error_field = data.get("error")
            if isinstance(error_field, dict) and error_field.get("message"):
                return str(error_field["message"])
            if isinstance(error_field, str):
                return error_field
        return f"HTTP {status}"
