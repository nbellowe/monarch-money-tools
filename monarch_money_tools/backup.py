from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import backups_dir, data_dir, root_dir
from .storage import ensure_dir, write_json

JsonObject = dict[str, Any]


def create_pre_cleanup_backup() -> JsonObject:
    workspace = root_dir()
    created_at = datetime.now(UTC)
    backup_dir = backups_dir() / f"pre-cleanup-{created_at.strftime('%Y%m%d-%H%M%S')}"
    ensure_dir(backup_dir)

    sources = [
        (data_dir(), backup_dir / "data"),
        (workspace / "reports", backup_dir / "reports"),
    ]
    for source, destination in sources:
        if not source.exists():
            continue
        shutil.copytree(source, destination, ignore=_ignore_data_backups, dirs_exist_ok=True)

    manifest: JsonObject = {
        "createdAt": created_at.isoformat().replace("+00:00", "Z"),
        "backupPath": str(backup_dir),
        "sourcePaths": ["data", "reports"],
        "excludedPaths": ["data/backups"],
        "fileCounts": {
            "data": _count_files(backup_dir / "data"),
            "reports": _count_files(backup_dir / "reports"),
        },
        "gitStatusShort": _git_status_short(workspace),
    }
    write_json(backup_dir / "manifest.json", manifest)
    return manifest


def verify_pre_cleanup_backup(manifest: JsonObject) -> list[str]:
    backup_path = Path(str(manifest.get("backupPath") or ""))
    required = [
        backup_path / "data/raw/latest",
        backup_path / "data/normalized/latest",
        backup_path / "data/rules/latest",
        backup_path / "data/review/latest",
        backup_path / "reports/latest",
    ]
    return [str(path) for path in required if not path.exists()]


def _ignore_data_backups(source: str, names: list[str]) -> set[str]:
    if Path(source).resolve() == data_dir().resolve() and "backups" in names:
        return {"backups"}
    return set()


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def _git_status_short(workspace: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]
