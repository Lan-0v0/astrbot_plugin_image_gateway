from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image as PillowImage

from ..utils.config import parse_bool

FOLLOW_GLOBAL = "follow_global"
IMAGE_TO_PDF_ON = "on"
IMAGE_TO_PDF_OFF = "off"

_VALID_ENTRY_MODES = {FOLLOW_GLOBAL, IMAGE_TO_PDF_ON, IMAGE_TO_PDF_OFF}
_INVALID_FILENAME_CHARACTERS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class ImagePdfConfig:
    enabled: bool = False


def parse_global_image_to_pdf(raw_value: Any) -> ImagePdfConfig:
    return ImagePdfConfig(enabled=parse_bool(raw_value, False))


def parse_entry_image_to_pdf_mode(raw_value: Any) -> str:
    normalized_mode = str(raw_value or FOLLOW_GLOBAL).strip().lower()
    if normalized_mode not in _VALID_ENTRY_MODES:
        return FOLLOW_GLOBAL
    return normalized_mode


def resolve_effective_image_to_pdf(
    *,
    global_config: ImagePdfConfig,
    entry_mode: str,
) -> ImagePdfConfig:
    if entry_mode == IMAGE_TO_PDF_ON:
        return ImagePdfConfig(enabled=True)
    if entry_mode == IMAGE_TO_PDF_OFF:
        return ImagePdfConfig(enabled=False)
    return global_config


async def convert_images_to_pdf(
    image_paths: list[str | Path],
    output_dir: Path,
    entry_name: str,
) -> tuple[Path, str]:
    if not image_paths:
        raise ValueError("没有可转换为 PDF 的图片")

    pdf_filename = build_pdf_filename(entry_name)
    request_output_dir = output_dir / "pdf" / uuid.uuid4().hex
    pdf_path = request_output_dir / pdf_filename
    await asyncio.to_thread(
        _write_images_to_pdf,
        [Path(image_path) for image_path in image_paths],
        pdf_path,
    )
    return pdf_path, pdf_filename


def build_pdf_filename(entry_name: str) -> str:
    normalized_entry_name = _INVALID_FILENAME_CHARACTERS.sub("_", str(entry_name or "").strip())
    normalized_entry_name = normalized_entry_name.rstrip(". ") or "未命名条目"
    return f"Lanの{normalized_entry_name}.pdf"


def _write_images_to_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_pages: list[PillowImage.Image] = []

    try:
        for image_path in image_paths:
            with PillowImage.open(image_path) as source_image:
                source_image.load()
                pdf_pages.append(_convert_image_to_pdf_page(source_image))

        first_page, *additional_pages = pdf_pages
        first_page.save(
            pdf_path,
            format="PDF",
            save_all=True,
            append_images=additional_pages,
            resolution=100.0,
        )
    finally:
        for pdf_page in pdf_pages:
            pdf_page.close()


def _convert_image_to_pdf_page(source_image: PillowImage.Image) -> PillowImage.Image:
    if source_image.mode in {"RGBA", "LA"} or "transparency" in source_image.info:
        rgba_image = source_image.convert("RGBA")
        white_background = PillowImage.new("RGB", rgba_image.size, "white")
        white_background.paste(rgba_image, mask=rgba_image.getchannel("A"))
        rgba_image.close()
        return white_background
    return source_image.convert("RGB")
