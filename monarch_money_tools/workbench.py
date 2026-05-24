from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .paths import data_dir, normalized_latest_dir, reports_latest_dir, root_dir
from .storage import ensure_dir, write_json, write_text

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class MonarchDataset:
    bundle: JsonObject
    root: Path

    @property
    def transactions(self) -> list[JsonObject]:
        return list(self.bundle.get("transactions") or [])

    @property
    def accounts(self) -> list[JsonObject]:
        return list(self.bundle.get("accounts") or [])

    @property
    def categories(self) -> list[JsonObject]:
        return list(self.bundle.get("categories") or [])

    @property
    def exported_at(self) -> str:
        return str(self.bundle.get("exportedAt") or "")

    def category_by_name(self) -> dict[str, JsonObject]:
        return {str(category.get("name")): category for category in self.categories}

    def account_by_id(self) -> dict[str, JsonObject]:
        return {str(account.get("id")): account for account in self.accounts}

    def scoped_transactions(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
        owner: str | None = None,
        account_contains: list[str] | None = None,
        include_pending: bool = False,
    ) -> list[JsonObject]:
        account_patterns = [pattern.lower() for pattern in account_contains or []]
        owner_pattern = owner.lower() if owner else None
        results: list[JsonObject] = []
        for transaction in self.transactions:
            if not include_pending and transaction.get("isPending"):
                continue
            transaction_date = parse_date(str(transaction.get("date") or ""))
            if start and (transaction_date is None or transaction_date < start):
                continue
            if end and (transaction_date is None or transaction_date > end):
                continue
            account_name = str(transaction.get("accountName") or "").lower()
            transaction_owner = str(transaction.get("owner") or "").lower()
            if (
                owner_pattern
                and owner_pattern not in account_name
                and owner_pattern not in transaction_owner
            ):
                continue
            if any(pattern not in account_name for pattern in account_patterns):
                continue
            results.append(transaction)
        return results


def load_latest_dataset(root: Path | None = None) -> MonarchDataset:
    workspace = root or root_dir()
    bundle_path = workspace / "data" / "normalized" / "latest" / "bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError("No normalized bundle found. Run `uv run monarch pull` first.")
    return MonarchDataset(
        bundle=json.loads(bundle_path.read_text(encoding="utf-8")), root=workspace
    )


def investigation_dir(slug: str, root: Path | None = None) -> Path:
    workspace = root or root_dir()
    return workspace / "data" / "investigations" / slug


def write_investigation_artifacts(
    slug: str,
    *,
    summary: JsonObject,
    rows: list[JsonObject],
    markdown: str,
    root: Path | None = None,
) -> Path:
    workspace = root or root_dir()
    output_dir = investigation_dir(slug, workspace)
    ensure_dir(output_dir)
    payload = {
        "generatedAt": now_iso(),
        "summary": summary,
        "rows": rows,
    }
    write_json(output_dir / "result.json", payload)
    write_rows_csv(output_dir / "result.csv", rows)
    write_text(output_dir / "result.md", markdown)
    ensure_dir(workspace / "reports" / "latest")
    write_text(workspace / "reports" / "latest" / f"{slug}.md", markdown)
    return output_dir


def write_rows_csv(path: Path, rows: list[JsonObject]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_cell(row.get(key)) for key in fieldnames})


def csv_cell(value: object) -> object:
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return value


def parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def today_utc() -> date:
    return datetime.now(UTC).date()


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "JsonObject",
    "MonarchDataset",
    "data_dir",
    "investigation_dir",
    "load_latest_dataset",
    "normalized_latest_dir",
    "parse_date",
    "reports_latest_dir",
    "root_dir",
    "today_utc",
    "write_investigation_artifacts",
]
