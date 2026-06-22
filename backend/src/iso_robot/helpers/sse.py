from __future__ import annotations

import json
from typing import Any


def format_sse(event: str, data: Any) -> str:
    """Encode one Server-Sent Event frame.

    ``data`` is JSON-encoded unless it is already a string. Multi-line payloads
    are split across ``data:`` lines as the SSE spec requires.
    """
    if isinstance(data, str):
        payload = data
    else:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    lines = [f"event: {event}"]
    for line in payload.split("\n"):
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


def sse_comment(text: str = "") -> str:
    """A comment/heartbeat frame (ignored by clients, keeps the connection warm)."""
    return f": {text}\n\n"
