from __future__ import annotations

import logging
import time
import uuid
from typing import Any
from urllib.parse import quote

import httpx

from jfrog_mcp.app.config import JFrogSettings
from jfrog_mcp.app.security import redact_secrets


class JFrogApiError(RuntimeError):
    """Raised when JFrog returns an error or cannot be reached safely."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


RepositoryCacheKey = tuple[str, str | None, str | None, str | None]
RepositoryCacheValue = tuple[float, list[dict[str, Any]]]

_REPOSITORY_CACHE: dict[RepositoryCacheKey, RepositoryCacheValue] = {}
logger = logging.getLogger("jfrog_mcp.client")


class JFrogClient:
    def __init__(
        self,
        settings: JFrogSettings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            verify=settings.httpx_verify,
            follow_redirects=True,
            trust_env=settings.trust_env,
        )

    def __enter__(self) -> JFrogClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def ping(self) -> str:
        response = self._request("GET", "/api/system/ping")
        return response.text.strip()

    def list_repositories(
        self,
        *,
        repo_type: str | None = None,
        package_type: str | None = None,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        cache_key = (self.settings.artifactory_url, repo_type, package_type, project)
        now = time.monotonic()
        cached = _REPOSITORY_CACHE.get(cache_key)
        if cached and self.settings.cache_ttl_seconds > 0:
            cached_at, records = cached
            if now - cached_at <= self.settings.cache_ttl_seconds:
                return records

        params: dict[str, str] = {}
        if repo_type:
            params["type"] = repo_type
        if package_type:
            params["packageType"] = package_type
        if project:
            params["project"] = project

        data = self._request_json("GET", "/api/repositories", params=params or None)
        if not isinstance(data, list):
            raise JFrogApiError("JFrog repositories response was not a list")

        _REPOSITORY_CACHE[cache_key] = (now, data)
        return data

    def list_path(
        self,
        *,
        repo_key: str,
        path: str,
        depth: int,
        include_folders: bool,
        include_timestamps: bool,
    ) -> dict[str, Any]:
        params = {
            "list": "1",
            "deep": "1" if depth > 1 else "0",
            "depth": str(depth),
            "listFolders": "1" if include_folders else "0",
            "mdTimestamps": "1" if include_timestamps else "0",
        }
        return self._request_json(
            "GET",
            self._storage_path(repo_key, path),
            params=params,
        )

    def get_item_info(self, *, repo_key: str, path: str) -> dict[str, Any]:
        return self._request_json("GET", self._storage_path(repo_key, path))

    def get_item_properties(
        self,
        *,
        repo_key: str,
        path: str,
        property_keys: list[str] | None,
    ) -> dict[str, Any]:
        property_value = ",".join(property_keys) if property_keys else ""
        return self._request_json(
            "GET",
            self._storage_path(repo_key, path),
            params=[("properties", property_value)],
        )

    def get_item_stats(self, *, repo_key: str, path: str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            self._storage_path(repo_key, path),
            params=[("stats", "")],
        )

    def run_aql(self, query: str) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/api/search/aql",
            content=query.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )

    def _storage_path(self, repo_key: str, item_path: str) -> str:
        encoded_segments = [quote(repo_key, safe="")]
        if item_path:
            encoded_segments.extend(quote(segment, safe="") for segment in item_path.split("/"))
        return f"/api/storage/{'/'.join(encoded_segments)}"

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Any | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = self._request(
            method,
            path,
            params=params,
            content=content,
            headers=headers,
        )
        try:
            return response.json()
        except ValueError as exc:
            raise JFrogApiError("JFrog response was not valid JSON") from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Any | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        request_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.settings.access_token}",
            "X-Request-ID": str(uuid.uuid4()),
        }
        if headers:
            request_headers.update(headers)

        url = f"{self.settings.artifactory_url}{path}"
        started = time.monotonic()
        try:
            response = self._http.request(
                method,
                url,
                params=params,
                content=content,
                headers=request_headers,
            )
        except httpx.HTTPError as exc:
            safe_message = redact_secrets(str(exc), [self.settings.access_token])
            elapsed_ms = round((time.monotonic() - started) * 1000, 2)
            logger.warning(
                "jfrog_request_failed",
                extra={
                    "method": method,
                    "path": path,
                    "duration_ms": elapsed_ms,
                    "error": safe_message,
                },
            )
            raise JFrogApiError(f"JFrog request failed: {safe_message}") from exc

        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        logger.info(
            "jfrog_request",
            extra={
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": elapsed_ms,
            },
        )

        if response.status_code >= 400:
            body = redact_secrets(response.text[:1000], [self.settings.access_token])
            raise JFrogApiError(
                f"JFrog returned HTTP {response.status_code}: {body or response.reason_phrase}",
                status_code=response.status_code,
                response_body=body,
            )

        return response
