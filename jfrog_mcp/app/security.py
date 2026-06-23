from __future__ import annotations

import re
from collections.abc import Iterable

_REPO_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_PROPERTY_KEY_RE = re.compile(r"^[A-Za-z0-9_.:/@*-]{1,160}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_REPO_TYPES = frozenset({"local", "remote", "virtual", "federated", "distribution"})
_PACKAGE_TYPES = frozenset(
    {
        "bower",
        "cargo",
        "chef",
        "cocoapods",
        "composer",
        "conan",
        "cran",
        "debian",
        "docker",
        "gems",
        "generic",
        "gitlfs",
        "go",
        "gradle",
        "helm",
        "ivy",
        "maven",
        "nuget",
        "opkg",
        "p2",
        "pub",
        "puppet",
        "pypi",
        "rpm",
        "sbt",
        "swift",
        "terraform",
        "vagrant",
        "yum",
    }
)


def reject_raw_url(value: str, field_name: str) -> None:
    if _URL_SCHEME_RE.match(value.strip()):
        raise ValueError(f"{field_name} must not be a raw URL")


def reject_control_chars(value: str, field_name: str) -> None:
    if _CONTROL_RE.search(value):
        raise ValueError(f"{field_name} must not contain control characters")


def validate_repo_key(repo_key: str) -> str:
    value = repo_key.strip()
    reject_raw_url(value, "repo_key")
    reject_control_chars(value, "repo_key")

    if not _REPO_KEY_RE.fullmatch(value):
        raise ValueError(
            "repo_key may contain only letters, numbers, dot, underscore, and hyphen"
        )
    return value


def validate_project_key(project: str | None) -> str | None:
    if project is None:
        return None
    return validate_repo_key(project)


def _validate_enum(value: str | None, field_name: str, allowed: frozenset[str]) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized:
        return None

    reject_raw_url(normalized, field_name)
    reject_control_chars(normalized, field_name)
    if normalized not in allowed:
        raise ValueError(f"{field_name} must be one of {', '.join(sorted(allowed))}")
    return normalized


def validate_repo_type(repo_type: str | None) -> str | None:
    return _validate_enum(repo_type, "type", _REPO_TYPES)


def validate_package_type(package_type: str | None) -> str | None:
    return _validate_enum(package_type, "package_type", _PACKAGE_TYPES)


def normalize_item_path(path: str | None) -> str:
    if path is None:
        return ""

    value = path.strip()
    if value in {"", ".", "/"}:
        return ""

    reject_raw_url(value, "path")
    reject_control_chars(value, "path")

    if "\\" in value:
        raise ValueError("path must use forward slashes")

    segments = [segment for segment in value.strip("/").split("/") if segment]
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError("path must not contain . or .. segments")

    return "/".join(segments)


def validate_depth(depth: int | None, *, default: int, max_depth: int) -> int:
    if depth is None:
        return default
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if depth > max_depth:
        raise ValueError(f"depth must not exceed {max_depth}")
    return depth


def validate_property_keys(property_keys: Iterable[str] | None) -> list[str] | None:
    if property_keys is None:
        return None

    keys = [key.strip() for key in property_keys if key and key.strip()]
    for key in keys:
        reject_raw_url(key, "property_keys")
        reject_control_chars(key, "property_keys")
        if "," in key:
            raise ValueError("property_keys entries must not contain commas")
        if not _PROPERTY_KEY_RE.fullmatch(key):
            raise ValueError(f"Invalid JFrog property key: {key!r}")
    return keys or None


def validate_name_pattern(name_pattern: str | None) -> str | None:
    if name_pattern is None:
        return None

    value = name_pattern.strip()
    if not value:
        return None

    reject_raw_url(value, "name_pattern")
    reject_control_chars(value, "name_pattern")

    if "/" in value or "\\" in value:
        raise ValueError("name_pattern must not contain path separators")
    if len(value) > 160:
        raise ValueError("name_pattern is too long")
    return value


def redact_secrets(message: str, secrets: Iterable[str | None]) -> str:
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted
