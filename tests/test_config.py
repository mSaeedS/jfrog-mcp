from pathlib import Path

import pytest

from jfrog_mcp.app.config import ConfigurationError, load_settings

TEST_DATA = Path(".tmp/test-data/config")


def _write_test_file(relative_path: str, text: str) -> Path:
    path = TEST_DATA / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.resolve()


def test_load_settings_accepts_base_jfrog_url():
    settings = load_settings(
        {
            "JFROG_URL": "https://example.jfrog.io/",
            "JFROG_ACCESS_TOKEN": "token",
        }
    )

    assert settings.base_url == "https://example.jfrog.io"
    assert settings.artifactory_url == "https://example.jfrog.io/artifactory"
    assert settings.access_token_source == "environment"
    assert settings.trust_env is False


def test_load_settings_accepts_artifactory_url():
    settings = load_settings(
        {
            "JFROG_URL": "https://example.jfrog.io/artifactory/",
            "JFROG_ACCESS_TOKEN": "token",
        }
    )

    assert settings.artifactory_url == "https://example.jfrog.io/artifactory"


def test_load_settings_rejects_plain_http_by_default():
    with pytest.raises(ConfigurationError, match="HTTPS"):
        load_settings(
            {
                "JFROG_URL": "http://example.local",
                "JFROG_ACCESS_TOKEN": "token",
            }
        )


def test_load_settings_rejects_credentials_in_url():
    with pytest.raises(ConfigurationError, match="credentials"):
        load_settings(
            {
                "JFROG_URL": "https://admin:secret@example.jfrog.io",
                "JFROG_ACCESS_TOKEN": "token",
            }
        )


def test_load_settings_allows_plain_http_when_explicit():
    settings = load_settings(
        {
            "JFROG_URL": "http://example.local",
            "JFROG_ACCESS_TOKEN": "token",
            "JFROG_ALLOW_INSECURE_HTTP": "true",
        }
    )

    assert settings.base_url == "http://example.local"


def test_load_settings_reads_token_file():
    token_file = _write_test_file("access-value", "from-file")

    settings = load_settings(
        {
            "JFROG_URL": "https://example.jfrog.io",
            "JFROG_ACCESS_TOKEN_FILE": str(token_file),
        }
    )

    assert settings.access_token == "from-file"
    assert settings.access_token_source == "file"


def test_load_settings_resolves_token_file_relative_to_env_dir():
    token_dir = (TEST_DATA / "env-dir").resolve()
    token_dir.mkdir(parents=True, exist_ok=True)
    (token_dir / "access-value").write_text("from-file", encoding="utf-8")

    settings = load_settings(
        {
            "JFROG_URL": "https://example.jfrog.io",
            "JFROG_ACCESS_TOKEN_FILE": "access-value",
            "JFROG_ENV_DIR": str(token_dir),
        }
    )

    assert settings.access_token == "from-file"
    assert settings.access_token_source == "file"


def test_load_settings_prefers_environment_token_over_token_file():
    settings = load_settings(
        {
            "JFROG_URL": "https://example.jfrog.io",
            "JFROG_ACCESS_TOKEN": "from-env",
            "JFROG_ACCESS_TOKEN_FILE": "unused-token-file",
        }
    )

    assert settings.access_token == "from-env"
    assert settings.access_token_source == "environment"


def test_load_settings_uses_ca_bundle():
    ca_bundle = _write_test_file("company-ca.pem", "test ca")

    settings = load_settings(
        {
            "JFROG_URL": "https://example.jfrog.io",
            "JFROG_ACCESS_TOKEN": "token",
            "JFROG_CA_BUNDLE": str(ca_bundle),
        }
    )

    assert settings.ca_bundle == str(ca_bundle)
    assert settings.httpx_verify == str(ca_bundle)
    assert settings.insecure_tls is False


def test_load_settings_rejects_missing_token_file():
    with pytest.raises(ConfigurationError, match="Could not read JFROG_ACCESS_TOKEN_FILE"):
        load_settings(
            {
                "JFROG_URL": "https://example.jfrog.io",
                "JFROG_ACCESS_TOKEN_FILE": "missing-token",
            }
        )


def test_load_settings_rejects_invalid_log_level():
    with pytest.raises(ConfigurationError, match="JFROG_LOG_LEVEL"):
        load_settings(
            {
                "JFROG_URL": "https://example.jfrog.io",
                "JFROG_ACCESS_TOKEN": "token",
                "JFROG_LOG_LEVEL": "chatty",
            }
        )


def test_load_settings_can_enable_environment_proxy_settings():
    settings = load_settings(
        {
            "JFROG_URL": "https://example.jfrog.io",
            "JFROG_ACCESS_TOKEN": "token",
            "JFROG_TRUST_ENV": "true",
        }
    )

    assert settings.trust_env is True
