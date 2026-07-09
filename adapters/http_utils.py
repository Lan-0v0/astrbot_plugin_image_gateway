from __future__ import annotations

from typing import Any


def extract_error_message(data: Any, status: int, *, fallback: str = "") -> str:
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            if err.get("message"):
                return str(err["message"])
            if err.get("code"):
                return str(err["code"])
        if isinstance(err, str):
            return err

        base_resp = data.get("base_resp")
        if isinstance(base_resp, dict):
            status_msg = base_resp.get("status_msg")
            if status_msg:
                return str(status_msg)
            status_code = base_resp.get("status_code")
            if status_code not in (None, 0):
                return f"status_code={status_code}"

        if data.get("message"):
            return str(data["message"])
        if data.get("code"):
            return str(data["code"])

        output = data.get("output")
        if isinstance(output, dict):
            if output.get("message"):
                return str(output["message"])
            if output.get("code"):
                return str(output["code"])

    if fallback:
        return fallback
    return f"HTTP {status}"