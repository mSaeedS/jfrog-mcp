import pytest

from jfrog_mcp.app.config import JFrogSettings
from jfrog_mcp.app.tools import repositories


class _RepositoryClient:
    def __init__(self):
        self.filters = None

    def list_repositories(self, *, repo_type, package_type, project):
        self.filters = {
            "repo_type": repo_type,
            "package_type": package_type,
            "project": project,
        }
        return [
            {
                "key": "libs-release-local",
                "type": "LOCAL",
                "packageType": "maven",
            }
        ]


def test_list_repositories_validates_and_normalizes_filters(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    client = _RepositoryClient()

    monkeypatch.setattr(repositories, "with_client", lambda fn: fn(settings, client))

    result = repositories.list_repositories(type="LOCAL", package_type="MAVEN")

    assert client.filters == {
        "repo_type": "local",
        "package_type": "maven",
        "project": None,
    }
    assert result["repositories"][0]["key"] == "libs-release-local"


def test_list_repositories_rejects_invalid_type(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    client = _RepositoryClient()

    monkeypatch.setattr(repositories, "with_client", lambda fn: fn(settings, client))

    with pytest.raises(RuntimeError, match="type"):
        repositories.list_repositories(type="private")

    assert client.filters is None
