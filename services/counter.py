from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiofiles

from astrbot.api import logger


class GenerationCounter:
    def __init__(self, counter_file: Path):
        self.counter_file = counter_file
        self._counts: dict[str, int] = {}
        self._loaded = False
        self._lock = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        async with self._lock:
            await self._ensure_loaded_unlocked()

    async def _ensure_loaded_unlocked(self) -> None:
        if self._loaded:
            return

        if not self.counter_file.exists():
            self._counts = {}
            self._loaded = True
            return
        try:
            async with aiofiles.open(self.counter_file, "r", encoding="utf-8") as file:
                content = await file.read()
            data = json.loads(content or "{}")
            if isinstance(data, dict):
                self._counts = {str(k): int(v) for k, v in data.items()}
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"读取生成计数失败，将重新初始化: {exc}")
            self._counts = {}
        self._loaded = True

    async def get_count(self, model_key: str) -> int:
        async with self._lock:
            await self._ensure_loaded_unlocked()
            return self._counts.get(model_key, 0)

    async def add_count(self, model_key: str, delta: int) -> int:
        async with self._lock:
            await self._ensure_loaded_unlocked()
            current = self._counts.get(model_key, 0) + delta
            self._counts[model_key] = current
            await self._save()
            return current

    async def _save(self) -> None:
        self.counter_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.counter_file.with_suffix(f"{self.counter_file.suffix}.tmp")
        try:
            async with aiofiles.open(temp_file, "w", encoding="utf-8") as file:
                await file.write(json.dumps(self._counts, ensure_ascii=False, indent=2))
            temp_file.replace(self.counter_file)
        finally:
            temp_file.unlink(missing_ok=True)
