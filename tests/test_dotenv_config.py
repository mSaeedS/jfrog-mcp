from pathlib import Path

from jfrog_mcp.app.config import load_settings

TEST_DATA = Path(".tmp/test-data/dotenv")


def _write_dotenv(directory_name: str, text: str) -> Path:
    directory = TEST_DATA / directory_name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".env").write_text(text, encoding="utf-8")
    return directory.resolve()


def test_load_settings_reads_dotenv_from_current_directory(monkeypatch):
    dotenv_dir = _write_dotenv(
        "current-dir",
        "JFROG_URL=https://example.jfrog.io\n"
        "JFROG_ACCESS_TOKEN=from-dotenv\n",
    )
    monkeypatch.chdir(dotenv_dir)
    monkeypatch.delenv("JFROG_ENV_FILE", raising=False)
    monkeypatch.delenv("JFROG_URL", raising=False)
    monkeypatch.delenv("JFROG_ACCESS_TOKEN", raising=False)

    settings = load_settings()

    assert settings.base_url == "https://example.jfrog.io"
    assert settings.access_token == "from-dotenv"


def test_real_environment_wins_over_dotenv(monkeypatch):
    dotenv_dir = _write_dotenv(
        "env-wins",
        "JFROG_URL=https://dotenv.example.jfrog.io\n"
        "JFROG_ACCESS_TOKEN=from-dotenv\n",
    )
    monkeypatch.chdir(dotenv_dir)
    monkeypatch.delenv("JFROG_ENV_FILE", raising=False)
    monkeypatch.setenv("JFROG_URL", "https://env.example.jfrog.io")
    monkeypatch.setenv("JFROG_ACCESS_TOKEN", "from-env")

    settings = load_settings()

    assert settings.base_url == "https://env.example.jfrog.io"
    assert settings.access_token == "from-env"
