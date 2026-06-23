import os

import pytest

from jfrog_mcp.app.tools import health, repositories, storage

LIVE_ENV_VARS = ("JFROG_TEST_URL", "JFROG_TEST_TOKEN", "JFROG_TEST_REPO")


def _has_live_env() -> bool:
    return all(os.getenv(name) for name in LIVE_ENV_VARS)


pytestmark = pytest.mark.skipif(
    not _has_live_env(),
    reason="Set JFROG_TEST_URL, JFROG_TEST_TOKEN, and JFROG_TEST_REPO to run live tests.",
)


@pytest.fixture
def live_env(monkeypatch):
    monkeypatch.setenv("JFROG_URL", os.environ["JFROG_TEST_URL"])
    monkeypatch.setenv("JFROG_ACCESS_TOKEN", os.environ["JFROG_TEST_TOKEN"])
    monkeypatch.delenv("JFROG_ACCESS_TOKEN_FILE", raising=False)
    monkeypatch.delenv("JFROG_ENV_FILE", raising=False)
    return os.environ["JFROG_TEST_REPO"]


def test_live_ping_authenticates(live_env):
    result = health.ping()

    assert result["status"] == "ok"
    assert result["auth"] == "authenticated"


def test_live_lists_repositories_and_reads_test_repo_root(live_env):
    repo_key = live_env

    listed = repositories.list_repositories(limit=200)
    keys = {repo["key"] for repo in listed["repositories"]}

    assert repo_key in keys

    info = storage.get_item_info(repo_key=repo_key)

    assert info["repo"] == repo_key
    assert info["path"] == ""
