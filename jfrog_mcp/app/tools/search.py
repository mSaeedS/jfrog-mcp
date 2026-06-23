from __future__ import annotations

from typing import Any

from jfrog_mcp.app.aql import build_items_search_aql
from jfrog_mcp.app.models import shape_aql_item, shape_repository
from jfrog_mcp.app.pagination import clamp_limit, decode_cursor, encode_cursor
from jfrog_mcp.app.security import (
    normalize_item_path,
    validate_name_pattern,
    validate_package_type,
    validate_repo_key,
)
from jfrog_mcp.app.tools.common import tool_error, with_client


def _shape_file_item(
    item: dict[str, Any],
    *,
    include_metadata: bool,
    include_full_path: bool,
) -> dict[str, Any]:
    shaped = {
        "name": item.get("name"),
        "path": item.get("path"),
    }
    if include_full_path:
        shaped["full_path"] = "/".join(
            part for part in [item.get("path"), item.get("name")] if part
        )
    if include_metadata:
        shaped.update(
            {
                "repo": item.get("repo"),
                "type": item.get("type"),
                "size": item.get("size"),
                "created": item.get("created"),
                "created_by": item.get("created_by"),
                "modified": item.get("modified"),
                "modified_by": item.get("modified_by"),
            }
        )
    return shaped


def _repo_keys_for_search(
    *,
    client: Any,
    repo_key: str | None,
    package_type: str | None,
) -> list[str]:
    if repo_key:
        return [validate_repo_key(repo_key)]

    validated_package_type = validate_package_type(package_type)
    if not validated_package_type:
        raise ValueError("repo_key is required unless package_type is provided")

    records = client.list_repositories(package_type=validated_package_type)
    repositories = [shape_repository(record) for record in records]
    repo_keys = [repo["key"] for repo in repositories if repo.get("key")]
    if not repo_keys:
        raise ValueError(
            f"No repositories found for package_type={validated_package_type!r}"
        )
    return repo_keys


def _search_items_with_client(
    *,
    client: Any,
    repo_key: str | None,
    path: str | None,
    name_pattern: str | None,
    package_type: str | None,
    modified_after: str | None,
    modified_before: str | None,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    offset = decode_cursor(cursor)
    repo_keys = _repo_keys_for_search(
        client=client,
        repo_key=repo_key,
        package_type=package_type,
    )
    normalized_path = normalize_item_path(path)
    normalized_name = validate_name_pattern(name_pattern)
    query = build_items_search_aql(
        repo_keys=repo_keys,
        path=normalized_path,
        name_pattern=normalized_name,
        modified_after=modified_after,
        modified_before=modified_before,
        limit=limit,
        offset=offset,
    )
    data = client.run_aql(query)
    raw_results = data.get("results") if isinstance(data.get("results"), list) else []
    results = [shape_aql_item(record) for record in raw_results]
    range_data = data.get("range") if isinstance(data.get("range"), dict) else {}
    total = range_data.get("total")
    end_pos = offset + len(results)
    has_more = end_pos < total if isinstance(total, int) else len(results) == limit
    next_cursor = encode_cursor(end_pos) if has_more else None

    return {
        "items": results,
        "next_cursor": next_cursor,
        "limit": limit,
        "offset": offset,
        "total_available": total,
        "repo_keys": repo_keys,
    }


def find_files(
    *,
    repo_key: str | None = None,
    path: str | None = None,
    name_pattern: str | None = None,
    package_type: str | None = None,
    modified_after: str | None = None,
    modified_before: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    include_metadata: bool = True,
    include_full_path: bool = True,
    summary_only: bool = False,
) -> dict[str, Any]:
    try:
        def _call(settings: Any, client: Any) -> dict[str, Any]:
            page_limit = clamp_limit(
                limit,
                default=settings.default_page_size,
                max_limit=settings.max_aql_limit,
            )
            result = _search_items_with_client(
                client=client,
                repo_key=repo_key,
                path=path,
                name_pattern=name_pattern,
                package_type=package_type,
                modified_after=modified_after,
                modified_before=modified_before,
                limit=page_limit,
                cursor=cursor,
            )
            shaped = [
                _shape_file_item(
                    item,
                    include_metadata=include_metadata,
                    include_full_path=include_full_path,
                )
                for item in result["items"]
            ]
            response = {
                "count": len(shaped),
                "next_cursor": result["next_cursor"],
                "limit": result["limit"],
                "offset": result["offset"],
                "total_available": result["total_available"],
                "repo_keys": result["repo_keys"],
            }
            if summary_only:
                response["items_preview"] = shaped[:10]
            else:
                response["items"] = shaped
            return response

        return with_client(_call)
    except Exception as exc:
        raise tool_error(exc) from None


def latest_files(
    *,
    repo_key: str | None = None,
    path: str | None = None,
    name_pattern: str | None = None,
    package_type: str | None = None,
    modified_after: str | None = None,
    modified_before: str | None = None,
    limit: int | None = None,
    scan_limit: int | None = None,
    include_metadata: bool = True,
    include_full_path: bool = True,
) -> dict[str, Any]:
    try:
        def _call(settings: Any, client: Any) -> dict[str, Any]:
            result_limit = clamp_limit(
                limit,
                default=min(20, settings.default_page_size),
                max_limit=settings.max_page_size,
            )
            max_scan = clamp_limit(
                scan_limit,
                default=settings.max_aql_limit,
                max_limit=settings.max_aql_limit * 10,
            )
            page_limit = min(settings.max_aql_limit, max_scan)
            items: list[dict[str, Any]] = []
            cursor = None
            complete_scan = True

            while len(items) < max_scan:
                result = _search_items_with_client(
                    client=client,
                    repo_key=repo_key,
                    path=path,
                    name_pattern=name_pattern,
                    package_type=package_type,
                    modified_after=modified_after,
                    modified_before=modified_before,
                    limit=min(page_limit, max_scan - len(items)),
                    cursor=cursor,
                )
                items.extend(result["items"])
                cursor = result["next_cursor"]
                if not cursor:
                    break
            else:
                complete_scan = False

            if cursor:
                complete_scan = False

            sorted_items = sorted(
                items,
                key=lambda item: item.get("modified") or "",
                reverse=True,
            )[:result_limit]
            response = {
                "items": [
                    _shape_file_item(
                        item,
                        include_metadata=include_metadata,
                        include_full_path=include_full_path,
                    )
                    for item in sorted_items
                ],
                "limit": result_limit,
                "scanned": len(items),
                "scan_limit": max_scan,
                "complete_scan": complete_scan,
                "result_is_exact": complete_scan,
                "reason": (
                    "scan completed"
                    if complete_scan
                    else "scan limit reached before all matching files were scanned"
                ),
                "sort": "modified_desc_client_side",
            }
            if not complete_scan:
                response["warning"] = (
                    "Result is based on a bounded scan and may not contain "
                    "the true latest files."
                )
                response["next_action"] = (
                    "Narrow repo_key, path, name_pattern, modified_after, "
                    "or modified_before, or increase scan_limit within server limits."
                )
            return response

        return with_client(_call)
    except Exception as exc:
        raise tool_error(exc) from None


def register_search_tools(mcp: Any) -> None:
    @mcp.tool()
    def jfrog_find_files(
        repo_key: str | None = None,
        path: str | None = None,
        name_pattern: str | None = None,
        package_type: str | None = None,
        modified_after: str | None = None,
        modified_before: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        include_metadata: bool = True,
        include_full_path: bool = True,
        summary_only: bool = False,
    ) -> dict[str, Any]:
        """Find files with generic filters and response shaping."""
        return find_files(
            repo_key=repo_key,
            path=path,
            name_pattern=name_pattern,
            package_type=package_type,
            modified_after=modified_after,
            modified_before=modified_before,
            limit=limit,
            cursor=cursor,
            include_metadata=include_metadata,
            include_full_path=include_full_path,
            summary_only=summary_only,
        )

    @mcp.tool()
    def jfrog_latest_files(
        repo_key: str | None = None,
        path: str | None = None,
        name_pattern: str | None = None,
        package_type: str | None = None,
        modified_after: str | None = None,
        modified_before: str | None = None,
        limit: int | None = None,
        scan_limit: int | None = None,
        include_metadata: bool = True,
        include_full_path: bool = True,
    ) -> dict[str, Any]:
        """Find latest files by client-side modified timestamp sorting."""
        return latest_files(
            repo_key=repo_key,
            path=path,
            name_pattern=name_pattern,
            package_type=package_type,
            modified_after=modified_after,
            modified_before=modified_before,
            limit=limit,
            scan_limit=scan_limit,
            include_metadata=include_metadata,
            include_full_path=include_full_path,
        )
