from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or unsafe."""


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"Invalid boolean value: {value!r}")


def _parse_int(value: str | None, *, default: int, name: str, minimum: int) -> int:
    if value is None or value == "":
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc

    if parsed < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return parsed


def _parse_float(value: str | None, *, default: float, name: str, minimum: float) -> float:
    if value is None or value == "":
        return default

    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc

    if parsed < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return parsed


def _parse_log_level(value: str | None) -> str:
    if value is None or value == "":
        return "INFO"

    normalized = value.strip().upper()
    allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if normalized not in allowed:
        raise ConfigurationError(
            f"JFROG_LOG_LEVEL must be one of {', '.join(sorted(allowed))}"
        )
    return normalized


def _normalize_base_url(raw_url: str, *, allow_insecure_http: bool) -> str:
    base_url = raw_url.strip().rstrip("/")
    parsed = urlparse(base_url)

    if not parsed.scheme or not parsed.netloc:
        raise ConfigurationError("JFROG_URL must be an absolute URL")

    if parsed.scheme == "http" and not allow_insecure_http:
        raise ConfigurationError(
            "JFROG_URL must use HTTPS unless JFROG_ALLOW_INSECURE_HTTP=true"
        )

    if parsed.scheme not in {"http", "https"}:
        raise ConfigurationError("JFROG_URL must use http or https")

    if parsed.username or parsed.password:
        raise ConfigurationError("JFROG_URL must not include credentials")

    if parsed.query or parsed.fragment:
        raise ConfigurationError("JFROG_URL must not include a query string or fragment")

    return base_url


def _load_dotenv_files() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    def _load_env_file(path: Path) -> bool:
        if not path.exists():
            return False
        loaded = load_dotenv(path, override=False)
        if loaded:
            os.environ.setdefault("JFROG_ENV_DIR", str(path.parent))
        return loaded

    explicit_env_file = os.getenv("JFROG_ENV_FILE")
    if explicit_env_file:
        _load_env_file(Path(explicit_env_file))
        return

    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    candidates.extend(parent / ".env" for parent in Path(sys.executable).resolve().parents[:4])

    seen: set[Path] = set()
    for candidate in candidates:
        normalized = candidate.resolve()
        if normalized in seen:
            continue
        seen.add(normalized)
        if _load_env_file(normalized):
            return


@dataclass(frozen=True)
class JFrogSettings:
    base_url: str
    access_token: str
    access_token_source: str = "environment"
    ca_bundle: str | None = None
    request_timeout_seconds: float = 20.0
    default_page_size: int = 50
    max_page_size: int = 200
    max_depth: int = 5
    max_aql_limit: int = 500
    cache_ttl_seconds: int = 60
    verify_ssl: bool = True
    trust_env: bool = False
    log_level: str = "INFO"

    @property
    def artifactory_url(self) -> str:
        if self.base_url.endswith("/artifactory"):
            return self.base_url
        return f"{self.base_url}/artifactory"

    @property
    def httpx_verify(self) -> bool | str:
        if self.ca_bundle:
            return self.ca_bundle
        return self.verify_ssl

    @property
    def insecure_tls(self) -> bool:
        return not self.verify_ssl and not self.ca_bundle


def _load_token(env: Mapping[str, str]) -> tuple[str, str]:
    token = env.get("JFROG_ACCESS_TOKEN")
    if token and token.strip():
        return token.strip(), "environment"

    token_file = env.get("JFROG_ACCESS_TOKEN_FILE")
    if not token_file:
        raise ConfigurationError(
            "Missing required JFROG_ACCESS_TOKEN or JFROG_ACCESS_TOKEN_FILE"
        )

    token_path = Path(token_file)
    if not token_path.is_absolute() and env.get("JFROG_ENV_DIR"):
        token_path = Path(env["JFROG_ENV_DIR"]) / token_path
    try:
        file_token = token_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read JFROG_ACCESS_TOKEN_FILE: {token_path}"
        ) from exc

    if not file_token:
        raise ConfigurationError("JFROG_ACCESS_TOKEN_FILE is empty")
    return file_token, "file"


def _normalize_ca_bundle(raw_path: str | None) -> str | None:
    if not raw_path:
        return None

    ca_path = Path(raw_path)
    if not ca_path.exists():
        raise ConfigurationError(f"JFROG_CA_BUNDLE does not exist: {raw_path}")
    if not ca_path.is_file():
        raise ConfigurationError(f"JFROG_CA_BUNDLE must be a file: {raw_path}")
    return str(ca_path)


def load_settings(environ: Mapping[str, str] | None = None) -> JFrogSettings:
    if environ is None:
        _load_dotenv_files()

    env = environ if environ is not None else os.environ

    raw_url = env.get("JFROG_URL")
    if not raw_url:
        raise ConfigurationError("Missing required environment variable JFROG_URL")

    token, token_source = _load_token(env)
    allow_insecure_http = _parse_bool(env.get("JFROG_ALLOW_INSECURE_HTTP"), default=False)
    ca_bundle = _normalize_ca_bundle(env.get("JFROG_CA_BUNDLE"))

    default_page_size = _parse_int(
        env.get("JFROG_DEFAULT_PAGE_SIZE"),
        default=50,
        name="JFROG_DEFAULT_PAGE_SIZE",
        minimum=1,
    )
    max_page_size = _parse_int(
        env.get("JFROG_MAX_PAGE_SIZE"),
        default=200,
        name="JFROG_MAX_PAGE_SIZE",
        minimum=1,
    )
    max_aql_limit = _parse_int(
        env.get("JFROG_MAX_AQL_LIMIT"),
        default=500,
        name="JFROG_MAX_AQL_LIMIT",
        minimum=1,
    )

    if default_page_size > max_page_size:
        raise ConfigurationError(
            "JFROG_DEFAULT_PAGE_SIZE must be less than or equal to JFROG_MAX_PAGE_SIZE"
        )

    return JFrogSettings(
        base_url=_normalize_base_url(raw_url, allow_insecure_http=allow_insecure_http),
        access_token=token,
        access_token_source=token_source,
        ca_bundle=ca_bundle,
        request_timeout_seconds=_parse_float(
            env.get("JFROG_REQUEST_TIMEOUT_SECONDS"),
            default=20.0,
            name="JFROG_REQUEST_TIMEOUT_SECONDS",
            minimum=0.1,
        ),
        default_page_size=default_page_size,
        max_page_size=max_page_size,
        max_depth=_parse_int(
            env.get("JFROG_MAX_DEPTH"),
            default=5,
            name="JFROG_MAX_DEPTH",
            minimum=1,
        ),
        max_aql_limit=max_aql_limit,
        cache_ttl_seconds=_parse_int(
            env.get("JFROG_CACHE_TTL_SECONDS"),
            default=60,
            name="JFROG_CACHE_TTL_SECONDS",
            minimum=0,
        ),
        verify_ssl=_parse_bool(env.get("JFROG_VERIFY_SSL"), default=True),
        trust_env=_parse_bool(env.get("JFROG_TRUST_ENV"), default=False),
        log_level=_parse_log_level(env.get("JFROG_LOG_LEVEL")),
    )
