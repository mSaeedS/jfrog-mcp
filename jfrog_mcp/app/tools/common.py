from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from jfrog_mcp.app.config import ConfigurationError, JFrogSettings, load_settings
from jfrog_mcp.app.jfrog_client import JFrogApiError, JFrogClient

T = TypeVar("T")


def get_settings() -> JFrogSettings:
    return load_settings()


def with_client(fn: Callable[[JFrogSettings, JFrogClient], T]) -> T:
    settings = get_settings()
    with JFrogClient(settings) as client:
        return fn(settings, client)


def tool_error(exc: Exception) -> RuntimeError:
    if isinstance(exc, (ConfigurationError, JFrogApiError, ValueError)):
        return RuntimeError(str(exc))
    return RuntimeError("Unexpected JFrog MCP error")
