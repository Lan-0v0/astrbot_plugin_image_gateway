from __future__ import annotations

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
    """Extract trailing text after a slash command from the raw message string."""
    raw = (getattr(event, "message_str", None) or "").strip()
    if not raw:
        return ""

    prefixes = [
        f"/{command_name}",
        f"/ {command_name}",
    ]
    for prefix in prefixes:
        if raw.startswith(prefix):
            return raw[len(prefix) :].strip()
    return ""


def parse_count_and_prompt(text: str, default_count: int = 1) -> tuple[str, int]:
    """Parse `{prompt} {count?}` where count is an optional trailing integer."""
    text = (text or "").strip()
    if not text:
        return "", default_count

    parts = text.rsplit(maxsplit=1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0].strip(), max(1, int(parts[1]))
    return text, default_count
