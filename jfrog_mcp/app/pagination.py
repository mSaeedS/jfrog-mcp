from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
_CURSOR_VERSION = 1


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    next_cursor: str | None
    offset: int
    limit: int
    total_available: int | None = None


def clamp_limit(limit: int | None, *, default: int, max_limit: int) -> int:
    if limit is None:
        return default
    if limit < 1:
        raise ValueError("limit must be at least 1")
    return min(limit, max_limit)


def encode_cursor(offset: int) -> str:
    payload = json.dumps({"v": _CURSOR_VERSION, "offset": offset}, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if cursor is None or cursor == "":
        return 0

    padding = "=" * (-len(cursor) % 4)
    try:
        payload = base64.urlsafe_b64decode(f"{cursor}{padding}").decode("utf-8")
        data = json.loads(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("cursor is invalid") from exc

    if data.get("v") != _CURSOR_VERSION:
        raise ValueError("cursor version is unsupported")

    offset = data.get("offset")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("cursor offset is invalid")
    return offset


def paginate_sequence(items: Sequence[T], *, cursor: str | None, limit: int) -> Page[T]:
    offset = decode_cursor(cursor)
    end = offset + limit
    page_items = list(items[offset:end])
    next_cursor = encode_cursor(end) if end < len(items) else None
    return Page(
        items=page_items,
        next_cursor=next_cursor,
        offset=offset,
        limit=limit,
        total_available=len(items),
    )
