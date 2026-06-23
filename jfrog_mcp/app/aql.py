from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from jfrog_mcp.app.security import (
    normalize_item_path,
    validate_name_pattern,
    validate_repo_key,
)

DEFAULT_AQL_FIELDS = [
    "repo",
    "path",
    "name",
    "type",
    "size",
    "created",
    "created_by",
    "modified",
    "modified_by",
]


def normalize_aql_datetime(value: str | None, *, end_of_day: bool = False) -> str | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        time_part = "23:59:59.999Z" if end_of_day else "00:00:00.000Z"
        return f"{raw}T{time_part}"

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid datetime value: {value!r}") from exc

    if parsed.tzinfo is None:
        return raw

    return (
        parsed.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def build_items_search_aql(
    *,
    repo_keys: list[str],
    path: str | None,
    name_pattern: str | None,
    modified_after: str | None,
    modified_before: str | None,
    limit: int,
    offset: int,
) -> str:
    repos = [validate_repo_key(repo_key) for repo_key in repo_keys]
    if not repos:
        raise ValueError("At least one repo_key is required")

    criteria: dict[str, Any] = {"type": "file"}
    and_terms: list[dict[str, Any]] = []

    if len(repos) == 1:
        criteria["repo"] = repos[0]
    else:
        and_terms.append({"$or": [{"repo": repo_key} for repo_key in repos]})

    normalized_path = normalize_item_path(path)
    if normalized_path:
        and_terms.append(
            {
                "$or": [
                    {"path": normalized_path},
                    {"path": {"$match": f"{normalized_path}/*"}},
                ]
            }
        )

    normalized_name_pattern = validate_name_pattern(name_pattern)
    if normalized_name_pattern:
        criteria["name"] = {"$match": normalized_name_pattern}

    modified_filter: dict[str, str] = {}
    normalized_after = normalize_aql_datetime(modified_after)
    normalized_before = normalize_aql_datetime(modified_before, end_of_day=True)
    if normalized_after:
        modified_filter["$gte"] = normalized_after
    if normalized_before:
        modified_filter["$lte"] = normalized_before
    if modified_filter:
        criteria["modified"] = modified_filter

    if and_terms:
        criteria["$and"] = and_terms

    include_fields = ",".join(json.dumps(field) for field in DEFAULT_AQL_FIELDS)
    criteria_json = json.dumps(criteria, separators=(",", ":"))
    return (
        f"items.find({criteria_json})"
        f".include({include_fields})"
        f".offset({offset})"
        f".limit({limit})"
    )
