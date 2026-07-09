from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from astrbot.api import logger

DEFAULT_IMAGE_CACHE_CLEANUP_DAYS = 7


def parse_image_cache_cleanup_days(raw_value: Any) -> int | None:
    """Parse the configured image-cache retention window in days.

    Returns:
    - ``DEFAULT_IMAGE_CACHE_CLEANUP_DAYS`` when the field is missing
    - ``None`` when the user explicitly leaves the field blank
    - a positive integer when a valid numeric value is provided
    """
    if raw_value is None:
        return DEFAULT_IMAGE_CACHE_CLEANUP_DAYS

    if isinstance(raw_value, str):
        normalized_value = raw_value.strip()
        if not normalized_value:
            return None
        raw_value = normalized_value

    try:
        parsed_days = int(raw_value)
    except (TypeError, ValueError):
        logger.warning(
            "图片缓存定时清理配置无效，将回退到默认值 7 天"
        )
        return DEFAULT_IMAGE_CACHE_CLEANUP_DAYS

    if parsed_days <= 0:
        logger.warning(
            "图片缓存定时清理天数必须大于 0，留空可关闭清理；当前将视为关闭"
        )
        return None

    return parsed_days


def cleanup_expired_image_cache(
    images_dir: Path,
    *,
    retention_days: int | None,
    now: float | None = None,
) -> int:
    """Delete cached images older than the configured retention window."""
    if retention_days is None or retention_days <= 0 or not images_dir.exists():
        return 0

    current_time = time.time() if now is None else now
    expire_before = current_time - (retention_days * 86400)
    deleted_count = 0

    for path in images_dir.rglob("*"):
        if not path.is_file():
            continue

        try:
            if path.stat().st_mtime < expire_before:
                path.unlink()
                deleted_count += 1
        except Exception as exc:
            logger.warning(f"清理图片缓存失败: {path} ({exc})")

    return deleted_count
