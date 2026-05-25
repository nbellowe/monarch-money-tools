from __future__ import annotations

import sys
from pathlib import Path

from .exporter import resolve_csv_path
from .paths import analysis_latest_dir, normalized_latest_dir, reports_latest_dir, root_dir


def collect_checks() -> list[tuple[str, bool, str]]:
    csv_path = resolve_csv_path(None)
    gitignore = root_dir() / ".gitignore"
    ignored_paths = [
        ".env",
        ".monarch-home/",
        "data/",
        "reports/",
        "backups/",
        "exported/",
        "private/",
        "/profile.yaml",
        "*.pickle",
    ]
    ignore_text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""

    return [
        ("python", True, sys.version.split()[0]),
        ("csv source", csv_path is not None, str(csv_path) if csv_path else "not found"),
        (
            "normalized bundle",
            (normalized_latest_dir() / "bundle.json").exists(),
            str(normalized_latest_dir()),
        ),
        (
            "analysis bundle",
            (analysis_latest_dir() / "analysis.json").exists(),
            str(analysis_latest_dir()),
        ),
        ("reports", reports_latest_dir().exists(), str(reports_latest_dir())),
        (
            "private paths ignored",
            all(path in ignore_text for path in ignored_paths),
            ", ".join(path for path in ignored_paths if path not in ignore_text) or "ok",
        ),
    ]


def has_python_project() -> bool:
    return Path("pyproject.toml").exists()
