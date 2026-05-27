from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from monarch_money_tools.paths import cleanup_revert_dir, review_revert_dir, rules_revert_dir
from monarch_money_tools.revert import (
    build_revert_receipt,
    execute_revert,
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


def test_execute_revert_update_transaction(tmp_path) -> None:
    receipt = build_revert_receipt(
        "monarch review apply",
        [
            {
                "type": "update_transaction",
                "entityId": "txn-1",
                "merchantName": "Starbucks",
                "before": {
                    "categoryId": "cat-0",
                    "categoryName": "Uncategorized",
                    "needsReview": True,
                },
                "after": {
                    "categoryId": "cat-1",
                    "categoryName": "Coffee Shops",
                    "needsReview": False,
                },
            }
        ],
    )
    receipt_path = tmp_path / "revert-test.json"
    write_revert_receipt(tmp_path, receipt)
    receipt_path = find_latest_receipt(tmp_path)

    with patch(
        "monarch_money_tools.revert.apply_transaction_updates", new_callable=AsyncMock
    ) as mock_apply:
        mock_apply.return_value = [{"id": "txn-1"}]
        result = asyncio.run(execute_revert(receipt_path))

    mock_apply.assert_called_once_with(
        [
            {
                "transactionId": "txn-1",
                "merchantName": "Starbucks",
                "suggestedCategory": "Uncategorized",
                "categoryId": "cat-0",
                "setNeedsReview": True,
            }
        ]
    )
    assert result["revertedCount"] == 1
    assert result["skippedCount"] == 0
    updated = read_json(receipt_path)
    assert updated["reverted"] is True
    assert "revertedAt" in updated


def test_execute_revert_create_rule(tmp_path) -> None:
    receipt = build_revert_receipt(
        "monarch rules push",
        [
            {
                "type": "create_rule",
                "entityId": "rule-xyz",
                "ruleName": "Starbucks → Coffee Shops",
                "before": None,
                "after": {"monarchRuleId": "rule-xyz"},
            }
        ],
    )
    write_revert_receipt(tmp_path, receipt)
    receipt_path = find_latest_receipt(tmp_path)

    with patch(
        "monarch_money_tools.revert.delete_monarch_rule", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.return_value = {"deleted": True}
        result = asyncio.run(execute_revert(receipt_path))

    mock_delete.assert_called_once_with("rule-xyz")
    assert result["revertedCount"] == 1
    assert result["skippedCount"] == 0
    updated = read_json(receipt_path)
    assert updated["reverted"] is True


def test_execute_revert_skips_unknown_type(tmp_path) -> None:
    receipt = build_revert_receipt(
        "monarch future apply",
        [{"type": "future_operation", "entityId": "x"}],
    )
    write_revert_receipt(tmp_path, receipt)
    receipt_path = find_latest_receipt(tmp_path)

    result = asyncio.run(execute_revert(receipt_path))
    assert result["revertedCount"] == 0
    assert result["skippedCount"] == 1
    assert read_json(receipt_path)["reverted"] is True
