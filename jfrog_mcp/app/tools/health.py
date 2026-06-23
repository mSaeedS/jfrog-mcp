from __future__ import annotations

import json
from typing import Any

from jfrog_mcp.app.config import ConfigurationError, load_settings
from jfrog_mcp.app.jfrog_client import JFrogApiError, JFrogClient
from jfrog_mcp.app.security import normalize_item_path, validate_repo_key


def _error_details(exc: JFrogApiError) -> dict[str, Any]:
    message = str(exc)
    details: dict[str, Any] = {
        "message": message[:300],
    }
    if exc.status_code is not None:
        details["status_code"] = exc.status_code
    return details


def _sort_probe_aql(*, repo_key: str, path: str) -> str:
    criteria: dict[str, Any] = {"repo": repo_key, "type": "file"}
    if path:
        criteria["$and"] = [
            {
                "$or": [
                    {"path": path},
                    {"path": {"$match": f"{path}/*"}},
                ]
            }
        ]

    criteria_json = json.dumps(criteria, separators=(",", ":"))
    return (
        f"items.find({criteria_json})"
        '.include("repo","path","name","modified")'
        '.sort({"$desc":["modified"]})'
        ".limit(1)"
    )


def _probe_capabilities(
    *,
    client: JFrogClient,
    repo_key: str | None,
    path: str | None,
) -> dict[str, Any]:
    if not repo_key:
        return {
            "checked": False,
            "reason": "repo_key is required for live repository feature probes",
        }

    validated_repo = validate_repo_key(repo_key)
    normalized_path = normalize_item_path(path)
    result: dict[str, Any] = {
        "checked": True,
        "repo": validated_repo,
        "path": normalized_path,
    }

    try:
        client.list_path(
            repo_key=validated_repo,
            path=normalized_path,
            depth=1,
            include_folders=True,
            include_timestamps=False,
        )
    except JFrogApiError as exc:
        result["storage_list"] = {
            "supported": False,
            "error": _error_details(exc),
        }
    else:
        result["storage_list"] = {"supported": True}

    try:
        client.run_aql(_sort_probe_aql(repo_key=validated_repo, path=normalized_path))
    except JFrogApiError as exc:
        result["aql_sort"] = {
            "supported": False,
            "error": _error_details(exc),
        }
    else:
        result["aql_sort"] = {"supported": True}

    return result


def ping() -> dict[str, Any]:
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        return {
            "status": "error",
            "auth": "not_configured",
            "base_url": None,
            "error": str(exc),
        }

    try:
        with JFrogClient(settings) as client:
            jfrog_response = client.ping()
    except JFrogApiError as exc:
        return {
            "status": "error",
            "auth": "failed",
            "base_url": settings.base_url,
            "artifactory_url": settings.artifactory_url,
            "error": str(exc),
        }

    return {
        "status": "ok",
        "auth": "authenticated",
        "base_url": settings.base_url,
        "artifactory_url": settings.artifactory_url,
        "jfrog_response": jfrog_response,
    }


def capabilities(
    *,
    repo_key: str | None = None,
    path: str | None = None,
    live_probe: bool = False,
) -> dict[str, Any]:
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        return {
            "status": "error",
            "configured": False,
            "error": str(exc),
        }

    response: dict[str, Any] = {
        "status": "ok",
        "configured": True,
        "base_url": settings.base_url,
        "artifactory_url": settings.artifactory_url,
        "access_token_source": settings.access_token_source,
        "tls": {
            "verify_ssl": settings.verify_ssl,
            "ca_bundle_configured": bool(settings.ca_bundle),
            "insecure_tls": settings.insecure_tls,
        },
        "network": {
            "trust_env": settings.trust_env,
        },
        "logging": {
            "level": settings.log_level,
        },
        "read_only": True,
        "default_page_size": settings.default_page_size,
        "max_page_size": settings.max_page_size,
        "max_depth": settings.max_depth,
        "max_aql_limit": settings.max_aql_limit,
        "portable_aql_projection": True,
        "aql_sort_used_by_default": False,
        "storage_list_fallback": "metadata_children",
        "file_content_download": False,
        "generic_tools": [
            "jfrog_find_files",
            "jfrog_latest_files",
            "jfrog_get_tree",
            "jfrog_list_path",
        ],
    }

    if live_probe:
        try:
            with JFrogClient(settings) as client:
                response["live_probe"] = _probe_capabilities(
                    client=client,
                    repo_key=repo_key,
                    path=path,
                )
        except (JFrogApiError, ValueError) as exc:
            response["live_probe"] = {
                "checked": False,
                "error": str(exc)[:300],
            }

    return response


def register_health_tools(mcp: Any) -> None:
    @mcp.tool()
    def jfrog_ping() -> dict[str, Any]:
        """Check JFrog URL and token authentication without returning secrets."""
        return ping()

    @mcp.tool()
    def jfrog_capabilities(
        repo_key: str | None = None,
        path: str | None = None,
        live_probe: bool = False,
    ) -> dict[str, Any]:
        """Describe JFrog MCP limits, compatibility behavior, and enabled features."""
        return capabilities(repo_key=repo_key, path=path, live_probe=live_probe)
