#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ALLOWED_FILES = (
    "README.md",
    "pyproject.toml",
    "package.json",
    "Dockerfile",
    ".env.example",
    ".gitignore",
    ".dockerignore",
)
ALLOWED_DIRS = ("bin", "jfrog_mcp", "tests")
EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    ".secrets",
    ".git",
    ".agents",
    ".codex",
    "dist",
    "build",
}
EXCLUDED_FILENAMES = {".env", "jfrog-token"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _iter_allowed_paths(root: Path, output_path: Path) -> list[Path]:
    paths: list[Path] = []

    for file_name in ALLOWED_FILES:
        path = root / file_name
        if path.is_file():
            paths.append(path)

    for directory_name in ALLOWED_DIRS:
        directory = root / directory_name
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if path.resolve() == output_path:
                continue
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if path.name in EXCLUDED_FILENAMES:
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            paths.append(path)

    return sorted(paths, key=lambda path: path.as_posix())


def build_zip(output: Path) -> int:
    root = Path(__file__).resolve().parents[1]
    output_path = output if output.is_absolute() else root / output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    paths = _iter_allowed_paths(root, output_path.resolve())
    if not paths:
        print("No files matched clean export allow-list", file=sys.stderr)
        return 1

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(root).as_posix())

    print(f"Wrote {output_path} with {len(paths)} files")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a clean allow-listed source zip for jfrog-mcp."
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="dist/jfrog-mcp-clean.zip",
        help="Output zip path, relative to the project root by default.",
    )
    args = parser.parse_args()
    return build_zip(Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
