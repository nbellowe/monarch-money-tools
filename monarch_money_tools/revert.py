from __future__ import annotations

from pathlib import Path
from typing import Any

from .storage import ensure_dir, now_iso, read_json, timestamp_slug, write_json

JsonObject = dict[str, Any]


def snapshot_transaction_before(txn_id: str, bundle: JsonObject) -> JsonObject:
    """
    Look up txn_id in bundle["transactions"] and return its current field values
    as a before-dict: {categoryId, categoryName, needsReview}.

    categoryId is resolved from bundle["categories"] by matching categoryName.
    Returns {} if the transaction is not found (apply still proceeds; revert
    will skip that operation with a warning).
    """
    cat_by_name: dict[str, str] = {
        str(c.get("name", "")): str(c.get("id", ""))
        for c in (bundle.get("categories") or [])
    }
    txn = next(
        (t for t in (bundle.get("transactions") or []) if str(t.get("id", "")) == str(txn_id)),
        None,
    )
    if txn is None:
        return {}
    category_name = str(txn.get("categoryName") or "")
    return {
        "categoryId": cat_by_name.get(category_name, ""),
        "categoryName": category_name,
        "needsReview": bool(txn.get("needsReview")),
    }


def build_revert_receipt(command: str, operations: list[JsonObject]) -> JsonObject:
    """Construct the receipt envelope: {createdAt, command, reverted: False, operations}."""
    return {
        "createdAt": now_iso(),
        "command": command,
        "reverted": False,
        "operations": operations,
    }


def write_revert_receipt(revert_dir: Path, receipt: JsonObject) -> Path:
    """
    Write receipt to revert_dir/revert-<ts>.json.
    Creates the directory if it does not exist. Returns the path written.
    """
    ensure_dir(revert_dir)
    path = revert_dir / f"revert-{timestamp_slug()}.json"
    write_json(path, receipt)
    return path


def find_latest_receipt(revert_dir: Path) -> Path | None:
    """
    Return the path of the most recent receipt in revert_dir where reverted == False.
    Returns None if the directory does not exist or no eligible receipt is found.
    """
    if not revert_dir.exists():
        return None
    receipts = sorted(revert_dir.glob("revert-*.json"), key=lambda p: p.name, reverse=True)
    for path in receipts:
        try:
            data = read_json(path)
            if not data.get("reverted"):
                return path
        except Exception:
            continue
    return None
