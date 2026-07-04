from __future__ import annotations

import base64
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
import aiohttp

from astrbot.api import logger


async def save_base64_image(
    base64_string: str,
    output_dir: Path,
    *,
    prefix: str = "image",
    fmt: str = "png",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_data = base64.b64decode(base64_string)
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
        suffix = url.split("?")[0].split(".")[-1][:5] or "png"
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    image_path = output_dir / f"{prefix}_{timestamp}_{unique_id}.{fmt}"
    async with aiofiles.open(image_path, "wb") as file:
        await file.write(image_bytes)
    logger.debug(f"Saved image to {image_path}")
    return image_path
