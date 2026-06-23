from jfrog_mcp.app.config import JFrogSettings
from jfrog_mcp.app.tools import health


def test_capabilities_reports_security_and_runtime_settings(monkeypatch):
    settings = JFrogSettings(
        base_url="https://example.jfrog.io",
        access_token="token",
        access_token_source="file",
        ca_bundle="company-ca.pem",
        log_level="WARNING",
    )
    monkeypatch.setattr(health, "load_settings", lambda: settings)

    result = health.capabilities()

    assert result["access_token_source"] == "file"
    assert result["tls"] == {
        "verify_ssl": True,
        "ca_bundle_configured": True,
        "insecure_tls": False,
    }
    assert result["network"] == {"trust_env": False}
    assert result["logging"]["level"] == "WARNING"
    assert result["portable_aql_projection"] is True


def test_capabilities_live_probe_uses_requested_repo_and_path(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    captured = {}

    class FakeClient:
        def __init__(self, _settings):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return None

        def list_path(self, **kwargs):
            captured["list_path"] = kwargs
            return {"files": []}

        def run_aql(self, query):
            captured["aql"] = query
            return {"results": []}

    monkeypatch.setattr(health, "load_settings", lambda: settings)
    monkeypatch.setattr(health, "JFrogClient", FakeClient)

    result = health.capabilities(
        repo_key="libs-release-local",
        path="com/acme",
        live_probe=True,
    )

    assert result["live_probe"]["storage_list"] == {"supported": True}
    assert result["live_probe"]["aql_sort"] == {"supported": True}
    assert captured["list_path"]["repo_key"] == "libs-release-local"
    assert captured["list_path"]["path"] == "com/acme"
    assert '"repo":"libs-release-local"' in captured["aql"]
    assert '"path":"com/acme"' in captured["aql"]


def test_capabilities_live_probe_requires_repo_key(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    monkeypatch.setattr(health, "load_settings", lambda: settings)

    result = health.capabilities(live_probe=True)

    assert result["live_probe"]["checked"] is False
    assert "repo_key is required" in result["live_probe"]["reason"]
