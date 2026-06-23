import httpx
import pytest

from jfrog_mcp.app.config import JFrogSettings
from jfrog_mcp.app.jfrog_client import _REPOSITORY_CACHE, JFrogApiError, JFrogClient


def test_client_sends_bearer_token_and_artifactory_path():
    _REPOSITORY_CACHE.clear()
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["auth"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json=[
                {
                    "key": "libs-release-local",
                    "type": "LOCAL",
                    "packageType": "maven",
                }
            ],
        )

    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="secret-token")
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = JFrogClient(settings, http_client=http_client)

    repositories = client.list_repositories(package_type="maven")

    assert captured["path"] == "/artifactory/api/repositories"
    assert captured["auth"] == "Bearer secret-token"
    assert repositories[0]["key"] == "libs-release-local"


def test_client_redacts_token_from_errors():
    def handler(_request):
        return httpx.Response(401, text="bad token secret-token")

    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="secret-token")
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = JFrogClient(settings, http_client=http_client)

    with pytest.raises(JFrogApiError) as exc_info:
        client.ping()

    assert "secret-token" not in str(exc_info.value)
    assert "***" in str(exc_info.value)
    assert exc_info.value.status_code == 401
    assert exc_info.value.response_body == "bad token ***"
