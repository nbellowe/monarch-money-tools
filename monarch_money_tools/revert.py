from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .monarch_api import apply_transaction_updates, delete_monarch_rule
from .storage import JsonObject, ensure_dir, now_iso, read_json, timestamp_slug, write_json

console = Console()


def snapshot_transaction_before(txn_id: str, bundle: JsonObject) -> JsonObject:
    """
    Look up txn_id in bundle["transactions"] and return its current field values
    as a before-dict: {categoryId, categoryName, needsReview}.

    categoryId is resolved from bundle["categories"] by matching categoryName.
    Returns {} if the transaction is not found (apply still proceeds; revert
    will skip that operation with a warning).
    """
    cat_by_name: dict[str, str] = {
        str(c.get("name", "")): str(c.get("id", "")) for c in (bundle.get("categories") or [])
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


async def execute_revert(receipt_path: Path) -> JsonObject:
    """
    Load the receipt at receipt_path, dispatch each operation to its inversion
    handler, mark receipt reverted=True, and overwrite the file.
    Returns {revertedAt, revertedCount, skippedCount}.
    """
    receipt = read_json(receipt_path)
    operations: list[JsonObject] = receipt.get("operations") or []
    reverted = 0
    skipped = 0
    for op in operations:
        success = await _invert_operation(op)
        if success:
            reverted += 1
        else:
            skipped += 1
    reverted_at = now_iso()
    receipt["reverted"] = True
    receipt["revertedAt"] = reverted_at
    write_json(receipt_path, receipt)
    return {"revertedAt": reverted_at, "revertedCount": reverted, "skippedCount": skipped}


async def _invert_operation(op: JsonObject) -> bool:
    """Dispatch one receipt operation to its inverse API call. Returns True on success."""
    op_type = str(op.get("type", ""))
    before: JsonObject = op.get("before") or {}

    match op_type:
        case "update_transaction":
            await apply_transaction_updates(
                [
                    {
                        "transactionId": str(op["entityId"]),
                        "merchantName": op.get("merchantName", ""),
                        "suggestedCategory": before.get("categoryName"),
                        "categoryId": before.get("categoryId"),
                        "setNeedsReview": before.get("needsReview"),
                    }
                ]
            )
            return True
        case "create_rule":
            await delete_monarch_rule(str(op["entityId"]))
            return True
        case _:
            console.print(f"[yellow]Unknown operation type '{op_type}', skipping.[/]")
            return False
