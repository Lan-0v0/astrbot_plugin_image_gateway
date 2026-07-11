from __future__ import annotations

import re

from astrbot.api import logger
from astrbot.api.all import Image
from astrbot.core.message.components import Reply


async def collect_input_images(event) -> list[str]:
    """Collect base64 image payloads from the current message and quoted replies."""
    images: list[str] = []

    message_obj = getattr(event, "message_obj", None)
    message = getattr(message_obj, "message", None) if message_obj else None
    if not message:
        return images

    for comp in message:
        if isinstance(comp, Image):
            try:
                images.append(await comp.convert_to_base64())
            except Exception as exc:
                logger.warning(f"转换消息图片失败: {exc}")
        elif isinstance(comp, Reply) and comp.chain:
            for reply_comp in comp.chain:
                if isinstance(reply_comp, Image):
                    try:
                        images.append(await reply_comp.convert_to_base64())
                    except Exception as exc:
                        logger.warning(f"转换引用图片失败: {exc}")
    return images


def parse_command_text(event, command_name: str) -> str:
    """Extract trailing text after a slash command from the raw message string.

    The parser accepts both standard whitespace-separated forms and punctuation-separated
    forms such as ``/改图，生成奶龙捧腹大笑`` or ``改图：变成奶龙捧腹大笑`` so explicit commands do not
    fall through to the natural-language LLM path.
    """
    raw = (getattr(event, "message_str", None) or "").strip()
    if not raw:
        return ""

    normalized = re.sub(r"\s+", " ", raw)
    delimiter_pattern = r"(?:\s+|[，,、:：;；。.!！？?]+)"
    command_pattern = re.compile(
        rf"^(?:/|／)?\s*{re.escape(command_name)}(?:{delimiter_pattern}(?P<prompt>.*)|$)"
    )
    match = command_pattern.match(normalized)
    if match:
        return (match.group("prompt") or "").strip()

    for prefix in [f"/{command_name}", f"/ {command_name}", f"／{command_name}", f"／ {command_name}"]:
        if normalized.startswith(prefix):
            return normalized[len(prefix) :].strip()
    return ""


def parse_count_and_prompt(text: str, default_count: int = 1) -> tuple[str, int]:
    """Parse `{prompt} {count?}` where count is an optional trailing integer."""
    text = (text or "").strip()
    if not text:
        return "", default_count

    parts = text.rsplit(maxsplit=1)
    if len(parts) == 2 and parts[1].isdigit():
        try:
            count = int(parts[1])
        except ValueError:
            return text, default_count
        return parts[0].strip(), max(1, count)
    return text, default_count
