from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from jfrog_mcp.app.config import ConfigurationError, load_settings
from jfrog_mcp.app.resources import register_jfrog_resources
from jfrog_mcp.app.tools.health import register_health_tools
from jfrog_mcp.app.tools.repositories import register_repository_tools
from jfrog_mcp.app.tools.search import register_search_tools
from jfrog_mcp.app.tools.storage import register_storage_tools


def configure_logging() -> None:
    try:
        level = load_settings().log_level
    except ConfigurationError:
        level = os.getenv("JFROG_LOG_LEVEL", "INFO").strip().upper() or "INFO"

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_server() -> FastMCP:
    mcp = FastMCP(
        "jfrog-mcp",
        json_response=True,
        instructions=(
            "Read-only JFrog Artifactory metadata tools. "
            "List repositories first, list explicit paths next, "
            "and fetch item details only on request."
        ),
    )
    register_health_tools(mcp)
    register_repository_tools(mcp)
    register_storage_tools(mcp)
    register_search_tools(mcp)
    register_jfrog_resources(mcp)
    return mcp


mcp = create_server()


def main() -> None:
    configure_logging()
    transport = os.getenv("JFROG_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "streamable-http", "sse"}:
        raise RuntimeError("JFROG_MCP_TRANSPORT must be stdio, streamable-http, or sse")
    mcp.run(transport=transport)
