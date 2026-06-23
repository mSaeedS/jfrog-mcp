import pytest

from jfrog_mcp.app.security import (
    normalize_item_path,
    validate_package_type,
    validate_repo_key,
    validate_repo_type,
)


def test_validate_repo_key_rejects_slashes():
    with pytest.raises(ValueError):
        validate_repo_key("libs/release")


def test_validate_repo_key_rejects_raw_url():
    with pytest.raises(ValueError, match="raw URL"):
        validate_repo_key("https://example.jfrog.io/artifactory/libs")


def test_normalize_item_path_strips_outer_slashes():
    assert normalize_item_path("/com/acme/app.jar") == "com/acme/app.jar"


def test_normalize_item_path_rejects_parent_segments():
    with pytest.raises(ValueError, match=r"\.\."):
        normalize_item_path("com/../secret")


def test_validate_repo_type_normalizes_known_values():
    assert validate_repo_type("LOCAL") == "local"


def test_validate_repo_type_rejects_unknown_values():
    with pytest.raises(ValueError, match="type"):
        validate_repo_type("private")


def test_validate_package_type_normalizes_known_values():
    assert validate_package_type("MAVEN") == "maven"


def test_validate_package_type_rejects_unknown_values():
    with pytest.raises(ValueError, match="package_type"):
        validate_package_type("unknown")
