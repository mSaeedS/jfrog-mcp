from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from jfrog_mcp.app.tools import repositories, storage


def repositories_resource() -> dict[str, Any]:
    return repositories.list_repositories()


def repo_resource(repoKey: str) -> dict[str, Any]:
    return storage.list_path(repo_key=unquote(repoKey), path="")


def repo_path_resource(repoKey: str, path: str) -> dict[str, Any]:
    return storage.get_item_info(repo_key=unquote(repoKey), path=unquote(path))


def register_jfrog_resources(mcp: Any) -> None:
    @mcp.resource(
        "jfrog://repositories",
        name="jfrog_repositories",
        description="List JFrog repositories.",
        mime_type="application/json",
    )
    def jfrog_repositories() -> dict[str, Any]:
        return repositories_resource()

    @mcp.resource(
        "jfrog://repo/{repoKey}",
        name="jfrog_repo_root",
        description="List the root path of a JFrog repository.",
        mime_type="application/json",
    )
    def jfrog_repo_root(repoKey: str) -> dict[str, Any]:
        return repo_resource(repoKey)

    @mcp.resource(
        "jfrog://repo/{repoKey}/path/{path}",
        name="jfrog_repo_path",
        description="Get metadata for a JFrog repository path. Encode slashes as %2F.",
        mime_type="application/json",
    )
    def jfrog_repo_path(repoKey: str, path: str) -> dict[str, Any]:
        return repo_path_resource(repoKey, path)
