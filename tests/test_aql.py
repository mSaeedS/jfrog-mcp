import json

import pytest

from jfrog_mcp.app.aql import build_items_search_aql
from jfrog_mcp.app.pagination import encode_cursor


def test_build_items_search_aql_escapes_values_and_bounds_query():
    query = build_items_search_aql(
        repo_keys=["libs-release-local"],
        path="com/acme",
        name_pattern="*.jar",
        modified_after="2026-06-01",
        modified_before="2026-06-22",
        limit=50,
        offset=0,
    )

    assert query.startswith("items.find(")
    assert '"repo":"libs-release-local"' in query
    assert '"path":"com/acme"' in query
    assert '"name":{"$match":"*.jar"}' in query
    assert '"mime_type"' not in query
    assert ".sort(" not in query
    assert ".offset(0).limit(50)" in query


def test_build_items_search_aql_rejects_missing_repositories():
    with pytest.raises(ValueError):
        build_items_search_aql(
            repo_keys=[],
            path=None,
            name_pattern=None,
            modified_after=None,
            modified_before=None,
            limit=50,
            offset=0,
        )


def test_cursor_payload_remains_opaque_but_decodable():
    cursor = encode_cursor(123)
    padding = "=" * (-len(cursor) % 4)
    payload = json.loads(__import__("base64").urlsafe_b64decode(f"{cursor}{padding}"))

    assert payload == {"v": 1, "offset": 123}
