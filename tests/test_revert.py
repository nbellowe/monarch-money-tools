from __future__ import annotations

import json

from monarch_money_tools.paths import cleanup_revert_dir, review_revert_dir, rules_revert_dir
from monarch_money_tools.revert import (
    build_revert_receipt,
    find_latest_receipt,
    snapshot_transaction_before,
    write_revert_receipt,
)
from monarch_money_tools.storage import read_json


def test_revert_dir_helpers_are_under_data(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert review_revert_dir() == tmp_path / "data" / "review" / "revert"
    assert cleanup_revert_dir() == tmp_path / "data" / "cleanup" / "revert"
    assert rules_revert_dir() == tmp_path / "data" / "rules" / "revert"


_MINI_BUNDLE = {
    "transactions": [
        {"id": "txn-1", "categoryName": "Uncategorized", "needsReview": True},
        {"id": "txn-2", "categoryName": "Coffee Shops", "needsReview": False},
    ],
    "categories": [
        {"id": "cat-0", "name": "Uncategorized"},
        {"id": "cat-1", "name": "Coffee Shops"},
    ],
}


def test_snapshot_returns_before_fields() -> None:
    before = snapshot_transaction_before("txn-1", _MINI_BUNDLE)
    assert before == {"categoryId": "cat-0", "categoryName": "Uncategorized", "needsReview": True}


def test_snapshot_returns_empty_for_missing_transaction() -> None:
    before = snapshot_transaction_before("txn-unknown", _MINI_BUNDLE)
    assert before == {}


def test_build_revert_receipt_shape() -> None:
    ops = [{"type": "update_transaction", "entityId": "txn-1"}]
    receipt = build_revert_receipt("monarch review apply", ops)
    assert receipt["command"] == "monarch review apply"
    assert receipt["reverted"] is False
    assert receipt["operations"] == ops
    assert "createdAt" in receipt


def test_write_revert_receipt_creates_timestamped_file(tmp_path) -> None:
    receipt = build_revert_receipt("monarch review apply", [])
    path = write_revert_receipt(tmp_path, receipt)
    assert path.exists()
    assert path.name.startswith("revert-")
    assert path.suffix == ".json"
    stored = read_json(path)
    assert stored["command"] == "monarch review apply"


def test_find_latest_receipt_skips_reverted(tmp_path) -> None:
    old_receipt = build_revert_receipt("monarch review apply", [])
    old_receipt["reverted"] = True
    (tmp_path / "revert-2026-05-26T10-00-00Z.json").write_text(
        json.dumps(old_receipt), encoding="utf-8"
    )

    new_receipt = build_revert_receipt("monarch review apply", [])
    new_receipt["reverted"] = False
    new_path = tmp_path / "revert-2026-05-26T11-00-00Z.json"
    new_path.write_text(json.dumps(new_receipt), encoding="utf-8")

    found = find_latest_receipt(tmp_path)
    assert found == new_path


def test_find_latest_receipt_returns_none_when_all_reverted(tmp_path) -> None:
    receipt = build_revert_receipt("monarch review apply", [])
    receipt["reverted"] = True
    (tmp_path / "revert-2026-05-26T10-00-00Z.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    assert find_latest_receipt(tmp_path) is None


def test_find_latest_receipt_returns_none_for_empty_dir(tmp_path) -> None:
    assert find_latest_receipt(tmp_path) is None


def test_find_latest_receipt_returns_none_for_missing_dir(tmp_path) -> None:
    assert find_latest_receipt(tmp_path / "nonexistent") is None
