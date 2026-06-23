import asyncio

from jfrog_mcp.app import resources
from jfrog_mcp.app.server import create_server


def test_server_registers_jfrog_resources():
    server = create_server()

    concrete_uris = {
        str(resource.uri) for resource in asyncio.run(server.list_resources())
    }
    template_uris = {
        template.uriTemplate
        for template in asyncio.run(server.list_resource_templates())
    }

    assert "jfrog://repositories" in concrete_uris
    assert "jfrog://repo/{repoKey}" in template_uris
    assert "jfrog://repo/{repoKey}/path/{path}" in template_uris


def test_repositories_resource_reuses_repository_tool(monkeypatch):
    expected = {"repositories": [{"key": "libs-release-local"}]}
    monkeypatch.setattr(
        resources.repositories,
        "list_repositories",
        lambda: expected,
    )

    assert resources.repositories_resource() == expected


def test_repo_path_resource_decodes_uri_segments(monkeypatch):
    captured = {}

    def fake_get_item_info(*, repo_key, path):
        captured["repo_key"] = repo_key
        captured["path"] = path
        return {"repo": repo_key, "path": path}

    monkeypatch.setattr(resources.storage, "get_item_info", fake_get_item_info)

    result = resources.repo_path_resource("libs-release-local", "com%2Facme")

    assert result == {"repo": "libs-release-local", "path": "com/acme"}
    assert captured == {
        "repo_key": "libs-release-local",
        "path": "com/acme",
    }
