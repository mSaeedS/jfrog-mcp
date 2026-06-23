import re

import pytest

from jfrog_mcp.app.config import JFrogSettings
from jfrog_mcp.app.tools import search


class _SearchClient:
    def run_aql(self, query):
        self.query = query
        return {
            "results": [
                {
                    "repo": "libs-release-local",
                    "path": "com/acme",
                    "name": "old.zip",
                    "type": "file",
                    "size": 10,
                    "created": "2026-01-01T00:00:00Z",
                    "created_by": "admin",
                    "modified": "2026-01-02T00:00:00Z",
                    "modified_by": "admin",
                },
                {
                    "repo": "libs-release-local",
                    "path": "com/acme",
                    "name": "new.zip",
                    "type": "file",
                    "size": 11,
                    "created": "2026-01-01T00:00:00Z",
                    "created_by": "admin",
                    "modified": "2026-01-03T00:00:00Z",
                    "modified_by": "admin",
                },
            ],
            "range": {"total": 2},
        }


class _PagedSearchClient:
    def __init__(self):
        self.items = [
            {
                "repo": "libs-release-local",
                "path": "com/acme",
                "name": "old.zip",
                "type": "file",
                "size": 10,
                "modified": "2026-01-02T00:00:00Z",
            },
            {
                "repo": "libs-release-local",
                "path": "com/acme",
                "name": "new.zip",
                "type": "file",
                "size": 11,
                "modified": "2026-01-03T00:00:00Z",
            },
        ]

    def run_aql(self, query):
        offset = int(re.search(r"\.offset\((\d+)\)", query).group(1))
        limit = int(re.search(r"\.limit\((\d+)\)", query).group(1))
        return {
            "results": self.items[offset : offset + limit],
            "range": {"total": len(self.items)},
        }


class _PackageSearchClient(_SearchClient):
    def list_repositories(self, *, package_type):
        self.package_type = package_type
        return [{"key": "libs-release-local", "packageType": package_type}]


def test_find_files_shapes_generic_results(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    client = _SearchClient()

    monkeypatch.setattr(search, "with_client", lambda fn: fn(settings, client))

    result = search.find_files(
        repo_key="libs-release-local",
        path="com/acme",
        name_pattern="*.zip",
        include_metadata=False,
    )

    assert result["count"] == 2
    assert result["items"][0] == {
        "name": "old.zip",
        "path": "com/acme",
        "full_path": "com/acme/old.zip",
    }
    assert ".sort(" not in client.query


def test_latest_files_sorts_client_side(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    client = _SearchClient()

    monkeypatch.setattr(search, "with_client", lambda fn: fn(settings, client))

    result = search.latest_files(
        repo_key="libs-release-local",
        path="com/acme",
        name_pattern="*.zip",
        limit=1,
    )

    assert result["sort"] == "modified_desc_client_side"
    assert result["complete_scan"] is True
    assert result["items"][0]["full_path"] == "com/acme/new.zip"


def test_find_files_validates_package_type_before_listing_repositories(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    client = _PackageSearchClient()

    monkeypatch.setattr(search, "with_client", lambda fn: fn(settings, client))

    result = search.find_files(package_type="MAVEN")

    assert client.package_type == "maven"
    assert result["repo_keys"] == ["libs-release-local"]


def test_find_files_rejects_invalid_package_type(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    client = _PackageSearchClient()

    monkeypatch.setattr(search, "with_client", lambda fn: fn(settings, client))

    with pytest.raises(RuntimeError, match="package_type"):
        search.find_files(package_type="unknown")


def test_latest_files_marks_scan_limited_results_inexact(monkeypatch):
    settings = JFrogSettings(base_url="https://example.jfrog.io", access_token="token")
    client = _PagedSearchClient()

    monkeypatch.setattr(search, "with_client", lambda fn: fn(settings, client))

    result = search.latest_files(repo_key="libs-release-local", limit=1, scan_limit=1)

    assert result["complete_scan"] is False
    assert result["result_is_exact"] is False
    assert result["reason"] == "scan limit reached before all matching files were scanned"
    assert "warning" in result
    assert "next_action" in result
