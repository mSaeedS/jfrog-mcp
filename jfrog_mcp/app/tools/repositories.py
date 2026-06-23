from __future__ import annotations

from typing import Any

from jfrog_mcp.app.models import shape_repository
from jfrog_mcp.app.pagination import clamp_limit, paginate_sequence
from jfrog_mcp.app.security import (
    validate_package_type,
    validate_project_key,
    validate_repo_type,
)
from jfrog_mcp.app.tools.common import tool_error, with_client


def list_repositories(
    *,
    type: str | None = None,
    package_type: str | None = None,
    project: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    try:
        def _call(settings: Any, client: Any) -> dict[str, Any]:
            page_limit = clamp_limit(
                limit,
                default=settings.default_page_size,
                max_limit=settings.max_page_size,
            )
            records = client.list_repositories(
                repo_type=validate_repo_type(type),
                package_type=validate_package_type(package_type),
                project=validate_project_key(project),
            )
            shaped = [shape_repository(record) for record in records]
            page = paginate_sequence(shaped, cursor=cursor, limit=page_limit)
            return {
                "repositories": page.items,
                "next_cursor": page.next_cursor,
                "limit": page.limit,
                "offset": page.offset,
                "total_available": page.total_available,
            }

        return with_client(_call)
    except Exception as exc:
        raise tool_error(exc) from None


def register_repository_tools(mcp: Any) -> None:
    @mcp.tool()
    def jfrog_list_repositories(
        type: str | None = None,
        package_type: str | None = None,
        project: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List JFrog repositories with optional filters and cursor pagination."""
        return list_repositories(
            type=type,
            package_type=package_type,
            project=project,
            limit=limit,
            cursor=cursor,
        )
