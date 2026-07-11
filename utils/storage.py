from __future__ import annotations

import base64
import binascii
import re
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
import aiohttp

from astrbot.api import logger

_VALID_IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}


def _decode_base64_image(value: str) -> bytes:
    raw_value = (value or "").strip()
    if raw_value.startswith("data:image/") and "," in raw_value:
        raw_value = raw_value.split(",", 1)[1]
    normalized_value = "".join(raw_value.split())
    try:
        image_data = base64.b64decode(normalized_value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("图片数据不是有效的 base64 内容") from exc
    if not image_data:
        raise ValueError("图片数据不能为空")
    return image_data


def _normalize_image_format(value: str) -> str:
    normalized_value = re.sub(r"[^a-z0-9]", "", (value or "").lower())
    if normalized_value == "jpe":
        normalized_value = "jpg"
    return normalized_value if normalized_value in _VALID_IMAGE_FORMATS else "png"


async def save_base64_image(
    base64_string: str,
    output_dir: Path,
    *,
    prefix: str = "image",
    fmt: str = "png",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_data = _decode_base64_image(base64_string)
    fmt = _normalize_image_format(fmt)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    image_path = output_dir / f"{prefix}_{timestamp}_{unique_id}.{fmt}"
    async with aiofiles.open(image_path, "wb") as file:
        await file.write(image_data)
    logger.debug(f"Saved image to {image_path}")
    return image_path


async def download_image(
    session: aiohttp.ClientSession,
    url: str,
    output_dir: Path,
    prefix: str = "image",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ValueError(f"下载图片失败: HTTP {resp.status}")
        content = await resp.read()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    suffix = "png"
    if "." in url.split("?")[0].split("/")[-1]:
        suffix = _normalize_image_format(url.split("?")[0].split(".")[-1])
    image_path = output_dir / f"{prefix}_{timestamp}_{unique_id}.{suffix}"
    async with aiofiles.open(image_path, "wb") as file:
        await file.write(content)
    return image_path


async def save_binary_image(
    image_bytes: bytes,
    output_dir: Path,
    *,
    prefix: str = "image",
    fmt: str = "png",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    fmt = _normalize_image_format(fmt)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    image_path = output_dir / f"{prefix}_{timestamp}_{unique_id}.{fmt}"
    async with aiofiles.open(image_path, "wb") as file:
        await file.write(image_bytes)
    logger.debug(f"Saved image to {image_path}")
    return image_path
