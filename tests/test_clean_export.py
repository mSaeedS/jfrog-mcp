import subprocess
import sys
import zipfile
from contextlib import suppress
from pathlib import Path


def test_clean_export_zip_uses_allowlist():
    output = Path("dist/test-clean-export.zip")
    output.parent.mkdir(exist_ok=True)
    if output.exists():
        with suppress(PermissionError):
            output.unlink()

    try:
        subprocess.run(
            [sys.executable, "bin/build-clean-zip.py", str(output)],
            check=True,
        )

        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
    finally:
        if output.exists():
            with suppress(PermissionError):
                output.unlink()

    assert "README.md" in names
    assert "Dockerfile" in names
    assert ".env.example" in names
    assert "jfrog_mcp/app/server.py" in names
    assert "tests/test_config.py" in names
    assert not any(name == ".env" or name.endswith("/.env") for name in names)
    assert not any(name.endswith("/jfrog-token") for name in names)
    assert not any(name.startswith(".secrets/") for name in names)
    assert not any(name.startswith(".venv/") for name in names)
    assert not any(name.startswith("dist/") for name in names)
