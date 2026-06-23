from mcp.server.fastmcp import FastMCP

from jfrog_mcp.app.server import mcp


def test_server_import_registers_fastmcp_instance():
    assert isinstance(mcp, FastMCP)
