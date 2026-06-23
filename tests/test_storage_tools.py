from jfrog_mcp.app.config import JFrogSettings
from jfrog_mcp.app.jfrog_client import JFrogApiError
from jfrog_mcp.app.tools import storage


class _StorageFallbackClient:
    def list_path(self, **_kwargs):
        raise JFrogApiError("This REST API is available only in Artifactory Pro")

    def get_item_info(self, *, repo_key, path):
        assert repo_key == "libs-release-local"
        assert path == ""
        return {
            "children": [
                {"uri": "/com", "folder": True},
                {"uri": "/root.jar", "folder": False},
            ]
        }


class _StorageFallbackResponseBodyClient(_StorageFallbackClient):
    def list_path(self, **_kwargs):
        raise JFrogApiError(
            "JFrog returned HTTP 400",
            status_code=400,
            response_body="Storage API list mode requires Artifactory Pro",
        )


class _TreeClient:
    def get_item_info(self, *, repo_key, path):
        assert repo_key == "libs-release-local"
        if path == "":
            return {
                "children": [
                    {"uri": "/com", "folder": True},
                    {"uri": "/root.jar", "folder": False},
                ]
            }
        if path == "com":
            return {"children": [{"uri": "/app.jar", "folder": False}]}
        return {"children": []}


def test_list_path_falls_back_to_metadata_children(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")

    monkeypatch.setattr(
        storage,
        "with_client",
        lambda fn: fn(settings, _StorageFallbackClient()),
    )

    result = storage.list_path(repo_key="libs-release-local", limit=10)

    assert result["source"] == "metadata_children"
    assert result["fallback_used"] is True
    assert result["items"] == [
        {"name": "com", "path": "com", "type": "folder", "depth": 1},
        {"name": "root.jar", "path": "root.jar", "type": "file", "depth": 1},
    ]


def test_list_path_falls_back_when_pro_error_is_in_response_body(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")

    monkeypatch.setattr(
        storage,
        "with_client",
        lambda fn: fn(settings, _StorageFallbackResponseBodyClient()),
    )

    result = storage.list_path(repo_key="libs-release-local", limit=10)

    assert result["source"] == "metadata_children"
    assert result["fallback_used"] is True


def test_get_tree_walks_metadata_children(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")

    monkeypatch.setattr(
        storage,
        "with_client",
        lambda fn: fn(settings, _TreeClient()),
    )

    result = storage.get_tree(repo_key="libs-release-local", depth=2, limit=10)

    assert result["source"] == "metadata_children"
    assert result["items"] == [
        {"name": "com", "path": "com", "type": "folder", "depth": 1},
        {"name": "app.jar", "path": "com/app.jar", "type": "file", "depth": 2},
        {"name": "root.jar", "path": "root.jar", "type": "file", "depth": 1},
    ]
