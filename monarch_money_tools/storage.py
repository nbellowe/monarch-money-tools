from __future__ import annotations

import csv
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import normalized_latest_dir

JsonObject = dict[str, Any]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def reset_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    ensure_dir(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    ensure_dir(path.parent)
    path.write_text(value, encoding="utf-8")


def write_csv(path: Path, rows: list[JsonObject]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return value


def iso_date() -> str:
    return datetime.now(UTC).date().isoformat()


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def latest_csv_path(candidates: list[Path]) -> Path | None:
    files: list[Path] = []
    for directory in candidates:
        if directory.exists():
            files.extend(path for path in directory.iterdir() if path.suffix.lower() == ".csv")
    return sorted(files, key=lambda path: path.name, reverse=True)[0] if files else None


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def round2(value: float) -> float:
    return round(value * 100) / 100


def load_bundle() -> Any:
    path = normalized_latest_dir() / "bundle.json"
    if not path.exists():
        raise FileNotFoundError(
            "No normalized bundle found. Run `monarch pull` or `monarch import <csv>` first."
        )
    return read_json(path)
