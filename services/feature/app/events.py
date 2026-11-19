"""
Turns raw Kafka bytes into a clean Python dict.

user-event already validated these, but a consumer should never fully trust
its input: someone could publish to the topic directly, or an old message
could have a different shape. A bad message gets skipped, never crashes us.
"""

import json
from datetime import datetime, timezone


def parse_event(raw: bytes) -> dict | None:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    user_id = data.get("user_id")
    video_id = data.get("video_id")
    if not user_id or not video_id:
        return None

    watch_ms = data.get("watch_ms") or 0
    if not isinstance(watch_ms, int) or watch_ms < 0:
        return None

    timestamp = parse_timestamp(data.get("ts"))

    return {
        "user_id": user_id,
        "video_id": video_id,
        "watched": bool(data.get("watched")),
        "watch_ms": watch_ms,
        "model_version": data.get("model_version") or None,
        "ts": timestamp,
    }


def parse_timestamp(value) -> datetime:
    """Go sends RFC 3339 with nanoseconds, e.g. 2026-11-18T19:05:39.209199844Z.
    Python only handles microseconds, so we trim the extra digits."""
    if not isinstance(value, str) or not value:
        return datetime.now(timezone.utc)

    text = value.replace("Z", "+00:00")
    if "." in text:
        main_part, rest = text.split(".", 1)
        digits = ""
        suffix = ""
        for index, char in enumerate(rest):
            if char.isdigit():
                digits += char
            else:
                suffix = rest[index:]
                break
        text = main_part + "." + digits[:6] + suffix

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)
