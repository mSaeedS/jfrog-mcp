from __future__ import annotations

from typing import Any

from jfrog_mcp.app.jfrog_client import JFrogApiError
from jfrog_mcp.app.models import shape_item_info, shape_storage_listing_item
from jfrog_mcp.app.pagination import clamp_limit, decode_cursor, encode_cursor, paginate_sequence
from jfrog_mcp.app.security import (
    normalize_item_path,
    validate_depth,
    validate_property_keys,
    validate_repo_key,
)
from jfrog_mcp.app.tools.common import tool_error, with_client


def _is_storage_list_unsupported(exc: JFrogApiError) -> bool:
    message = f"{exc} {exc.response_body or ''}".lower()
    return (
        "available only in artifactory pro" in message
        or "requires artifactory pro" in message
        or ("storage api" in message and "pro" in message)
    )


def _child_path(parent_path: str, child_uri: str) -> str:
    child_name = child_uri.lstrip("/")
    return "/".join(part for part in [parent_path, child_name] if part)


def _shape_metadata_child(
    parent_path: str,
    record: dict[str, Any],
    *,
    depth: int,
) -> dict[str, Any]:
    uri = str(record.get("uri") or "").lstrip("/")
    item_path = _child_path(parent_path, uri)
    is_folder = bool(record.get("folder"))
    return {
        "name": uri.rsplit("/", 1)[-1] if uri else "",
        "path": item_path,
        "type": "folder" if is_folder else "file",
        "depth": depth,
    }


def _metadata_listing(
    *,
    client: Any,
    repo_key: str,
    path: str,
    depth: int,
    include_folders: bool,
    include_files: bool,
    max_items: int,
) -> tuple[list[dict[str, Any]], bool]:
    items: list[dict[str, Any]] = []
    truncated = False

    def _walk(current_path: str, current_depth: int) -> None:
        nonlocal truncated
        if truncated:
            return

        data = client.get_item_info(repo_key=repo_key, path=current_path)
        children = data.get("children") if isinstance(data.get("children"), list) else []

        for child in children:
            if truncated:
                return

            is_folder = bool(child.get("folder"))
            if (is_folder and include_folders) or (not is_folder and include_files):
                items.append(_shape_metadata_child(current_path, child, depth=current_depth))
                if len(items) >= max_items:
                    truncated = True
                    return

            if is_folder and current_depth < depth:
                _walk(_child_path(current_path, str(child.get("uri") or "")), current_depth + 1)

    _walk(path, 1)
    return items, truncated


def list_path(
    *,
    repo_key: str,
    path: str | None = None,
    depth: int | None = None,
    include_folders: bool = True,
    include_timestamps: bool = True,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    try:
        def _call(settings: Any, client: Any) -> dict[str, Any]:
            validated_repo = validate_repo_key(repo_key)
            normalized_path = normalize_item_path(path)
            page_limit = clamp_limit(
                limit,
                default=settings.default_page_size,
                max_limit=settings.max_page_size,
            )
            validated_depth = validate_depth(
                depth,
                default=1,
                max_depth=settings.max_depth,
            )
            try:
                data = client.list_path(
                    repo_key=validated_repo,
                    path=normalized_path,
                    depth=validated_depth,
                    include_folders=include_folders,
                    include_timestamps=include_timestamps,
                )
                raw_files = data.get("files") if isinstance(data.get("files"), list) else []
                shaped = [
                    shape_storage_listing_item(normalized_path, record)
                    for record in raw_files
                    if include_folders or not record.get("folder")
                ]
                page = paginate_sequence(shaped, cursor=cursor, limit=page_limit)
                source = "storage_list"
                fallback_used = False
                truncated = False
                total_available = page.total_available
                next_cursor = page.next_cursor
                items = page.items
                offset = page.offset
            except JFrogApiError as exc:
                if not _is_storage_list_unsupported(exc):
                    raise

                offset = decode_cursor(cursor)
                max_items = offset + page_limit + 1
                shaped, truncated = _metadata_listing(
                    client=client,
                    repo_key=validated_repo,
                    path=normalized_path,
                    depth=validated_depth,
                    include_folders=include_folders,
                    include_files=True,
                    max_items=max_items,
                )
                items = shaped[offset : offset + page_limit]
                next_cursor = (
                    encode_cursor(offset + page_limit)
                    if truncated or offset + page_limit < len(shaped)
                    else None
                )
                total_available = None if truncated else len(shaped)
                source = "metadata_children"
                fallback_used = True

            return {
                "repo": validated_repo,
                "path": normalized_path,
                "depth": validated_depth,
                "items": items,
                "next_cursor": next_cursor,
                "limit": page_limit,
                "offset": offset,
                "total_available": total_available,
                "source": source,
                "fallback_used": fallback_used,
                "truncated": truncated,
            }

        return with_client(_call)
    except Exception as exc:
        raise tool_error(exc) from None


def get_item_info(*, repo_key: str, path: str | None = None) -> dict[str, Any]:
    try:
        def _call(_settings: Any, client: Any) -> dict[str, Any]:
            validated_repo = validate_repo_key(repo_key)
            normalized_path = normalize_item_path(path)
            data = client.get_item_info(repo_key=validated_repo, path=normalized_path)
            return shape_item_info(validated_repo, normalized_path, data)

        return with_client(_call)
    except Exception as exc:
        raise tool_error(exc) from None


def get_item_properties(
    *,
    repo_key: str,
    path: str | None = None,
    property_keys: list[str] | None = None,
) -> dict[str, Any]:
    try:
        def _call(_settings: Any, client: Any) -> dict[str, Any]:
            validated_repo = validate_repo_key(repo_key)
            normalized_path = normalize_item_path(path)
            keys = validate_property_keys(property_keys)
            data = client.get_item_properties(
                repo_key=validated_repo,
                path=normalized_path,
                property_keys=keys,
            )
            return {
                "repo": validated_repo,
                "path": normalized_path,
                "properties": data.get("properties", {}),
                "uri": data.get("uri"),
            }

        return with_client(_call)
    except Exception as exc:
        raise tool_error(exc) from None


def get_item_stats(*, repo_key: str, path: str | None = None) -> dict[str, Any]:
    try:
        def _call(_settings: Any, client: Any) -> dict[str, Any]:
            validated_repo = validate_repo_key(repo_key)
            normalized_path = normalize_item_path(path)
            data = client.get_item_stats(repo_key=validated_repo, path=normalized_path)
            return {
                "repo": validated_repo,
                "path": normalized_path,
                "download_count": data.get("downloadCount"),
                "last_downloaded": data.get("lastDownloaded"),
                "last_downloaded_by": data.get("lastDownloadedBy"),
                "remote_download_count": data.get("remoteDownloadCount"),
                "remote_last_downloaded": data.get("remoteLastDownloaded"),
            }

        return with_client(_call)
    except Exception as exc:
        raise tool_error(exc) from None


def get_tree(
    *,
    repo_key: str,
    path: str | None = None,
    depth: int | None = None,
    include_files: bool = True,
    include_folders: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    try:
        def _call(settings: Any, client: Any) -> dict[str, Any]:
            validated_repo = validate_repo_key(repo_key)
            normalized_path = normalize_item_path(path)
            page_limit = clamp_limit(
                limit,
                default=settings.default_page_size,
                max_limit=settings.max_page_size,
            )
            validated_depth = validate_depth(
                depth,
                default=2,
                max_depth=settings.max_depth,
            )
            items, truncated = _metadata_listing(
                client=client,
                repo_key=validated_repo,
                path=normalized_path,
                depth=validated_depth,
                include_folders=include_folders,
                include_files=include_files,
                max_items=page_limit,
            )
            return {
                "repo": validated_repo,
                "path": normalized_path,
                "depth": validated_depth,
                "items": items,
                "limit": page_limit,
                "truncated": truncated,
                "source": "metadata_children",
            }

        return with_client(_call)
    except Exception as exc:
        raise tool_error(exc) from None


def register_storage_tools(mcp: Any) -> None:
    @mcp.tool()
    def jfrog_list_path(
        repo_key: str,
        path: str | None = None,
        depth: int | None = None,
        include_folders: bool = True,
        include_timestamps: bool = True,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List files and folders under one JFrog repository path."""
        return list_path(
            repo_key=repo_key,
            path=path,
            depth=depth,
            include_folders=include_folders,
            include_timestamps=include_timestamps,
            limit=limit,
            cursor=cursor,
        )

    @mcp.tool()
    def jfrog_get_item_info(repo_key: str, path: str | None = None) -> dict[str, Any]:
        """Get metadata for one JFrog file or folder."""
        return get_item_info(repo_key=repo_key, path=path)

    @mcp.tool()
    def jfrog_get_item_properties(
        repo_key: str,
        path: str | None = None,
        property_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get properties for one JFrog file or folder."""
        return get_item_properties(
            repo_key=repo_key,
            path=path,
            property_keys=property_keys,
        )

    @mcp.tool()
    def jfrog_get_item_stats(repo_key: str, path: str | None = None) -> dict[str, Any]:
        """Get download statistics for one JFrog file or folder."""
        return get_item_stats(repo_key=repo_key, path=path)

    @mcp.tool()
    def jfrog_get_tree(
        repo_key: str,
        path: str | None = None,
        depth: int | None = None,
        include_files: bool = True,
        include_folders: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Get a bounded file/folder tree using storage metadata traversal."""
        return get_tree(
            repo_key=repo_key,
            path=path,
            depth=depth,
            include_files=include_files,
            include_folders=include_folders,
            limit=limit,
        )
