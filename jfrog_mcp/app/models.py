from __future__ import annotations

from typing import Any


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def shape_repository(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": record.get("key"),
        "type": record.get("type") or record.get("rclass"),
        "package_type": record.get("packageType") or record.get("package_type"),
        "description": record.get("description"),
        "url": record.get("url"),
        "project": record.get("projectKey") or record.get("project"),
    }


def shape_storage_listing_item(parent_path: str, record: dict[str, Any]) -> dict[str, Any]:
    uri = str(record.get("uri") or "").lstrip("/")
    path = "/".join(part for part in [parent_path, uri] if part)
    is_folder = bool(record.get("folder"))

    return {
        "name": uri.rsplit("/", 1)[-1] if uri else "",
        "path": path,
        "type": "folder" if is_folder else "file",
        "size": _coerce_int(record.get("size")),
        "last_modified": record.get("lastModified") or record.get("last_modified"),
        "sha1": record.get("sha1"),
        "sha2": record.get("sha2"),
        "md_timestamps": record.get("mdTimestamps") or record.get("md_timestamps"),
    }


def shape_item_info(repo_key: str, path: str, record: dict[str, Any]) -> dict[str, Any]:
    checksums = record.get("checksums") if isinstance(record.get("checksums"), dict) else {}
    original_checksums = (
        record.get("originalChecksums")
        if isinstance(record.get("originalChecksums"), dict)
        else {}
    )
    is_folder = "children" in record
    children = record.get("children") if isinstance(record.get("children"), list) else []

    return {
        "repo": repo_key,
        "path": path,
        "uri": record.get("uri"),
        "type": "folder" if is_folder else "file",
        "download_uri": record.get("downloadUri"),
        "size": _coerce_int(record.get("size")),
        "created": record.get("created"),
        "created_by": record.get("createdBy"),
        "last_modified": record.get("lastModified"),
        "modified_by": record.get("modifiedBy"),
        "last_updated": record.get("lastUpdated"),
        "mime_type": record.get("mimeType"),
        "checksums": {
            "md5": checksums.get("md5"),
            "sha1": checksums.get("sha1"),
            "sha256": checksums.get("sha256"),
        },
        "original_checksums": {
            "md5": original_checksums.get("md5"),
            "sha1": original_checksums.get("sha1"),
            "sha256": original_checksums.get("sha256"),
        },
        "child_count": len(children),
        "children_preview": children[:50],
    }


def shape_aql_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo": record.get("repo"),
        "path": record.get("path"),
        "name": record.get("name"),
        "type": record.get("type"),
        "size": _coerce_int(record.get("size")),
        "created": record.get("created"),
        "created_by": record.get("created_by") or record.get("createdBy"),
        "modified": record.get("modified"),
        "modified_by": record.get("modified_by") or record.get("modifiedBy"),
    }
