from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from monarch_money_tools.csv_adapter import import_transactions_from_csv
from monarch_money_tools.monarch_api import clean_cookie_header, csrf_from_cookie
from monarch_money_tools.normalizer import (
    normalize_accounts,
    normalize_categories,
    normalize_transactions,
)
from monarch_money_tools.review import apply_clear_review_plan, apply_review_plan, build_review_plan
from monarch_money_tools.storage import write_json


def test_build_review_plan_recategorizes_unreviewed_transaction(
    tmp_path: Path, monkeypatch
) -> None:
    imported = import_transactions_from_csv(Path.cwd() / "tests/fixtures/monarch_transactions.csv")
    transactions = normalize_transactions(
        imported.transactions, imported.accounts, imported.categories
    )
    categories = normalize_categories(imported.categories)
    accounts = normalize_accounts(imported.accounts)

    target = next(
        item
        for item in transactions
        if item["merchantName"] == "Acme Coffee" and item["categoryName"] == "Shopping"
    )
    target["needsReview"] = True

    monkeypatch.chdir(tmp_path)
    write_json(
        tmp_path / "data/normalized/latest/bundle.json",
        {
            "transactions": transactions,
            "accounts": accounts,
            "categories": categories,
            "transactionRules": [],
        },
    )

    plan = build_review_plan()

    assert plan["summary"]["plannedUpdateCount"] == 1
    update = plan["updates"][0]
    assert update["transactionId"] == target["id"]
    assert update["suggestedCategory"] == "Dining"
    assert update["action"] == "recategorize_and_review"
    assert update["setNeedsReview"] is False


def test_apply_review_plan_accepts_updates_directly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t1", "categoryName": "Uncategorized", "needsReview": True}],
        "categories": [
            {"id": "c0", "name": "Uncategorized"},
            {"id": "c1", "name": "Dining"},
        ],
    }
    updates = [
        {
            "transactionId": "t1",
            "merchantName": "Coffee",
            "categoryId": "c1",
            "suggestedCategory": "Dining",
            "setNeedsReview": False,
        }
    ]
    with (
        patch(
            "monarch_money_tools.review.apply_transaction_updates", new_callable=AsyncMock
        ) as mock_apply,
        patch("monarch_money_tools.review.load_bundle", return_value=mini_bundle),
        patch("monarch_money_tools.review.write_json"),
    ):
        mock_apply.return_value = [{"id": "t1"}]
        result = asyncio.run(apply_review_plan(updates))

    mock_apply.assert_called_once_with(updates)
    assert result["requestedCount"] == 1
    # Receipt is written under data/review/revert/
    assert (tmp_path / "data" / "review" / "revert").exists()
    receipts = list((tmp_path / "data" / "review" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1


def test_apply_clear_review_plan_accepts_updates_directly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t2", "categoryName": "Transfer", "needsReview": True}],
        "categories": [{"id": "c2", "name": "Transfer"}],
    }
    updates = [
        {
            "transactionId": "t2",
            "merchantName": "Gas",
            "categoryId": "",
            "suggestedCategory": "Transfer",
            "setNeedsReview": False,
        }
    ]
    with (
        patch(
            "monarch_money_tools.review.apply_transaction_updates", new_callable=AsyncMock
        ) as mock_apply,
        patch("monarch_money_tools.review.load_bundle", return_value=mini_bundle),
        patch("monarch_money_tools.review.write_json"),
    ):
        mock_apply.return_value = [{"id": "t2"}]
        result = asyncio.run(apply_clear_review_plan(updates))

    mock_apply.assert_called_once_with(updates)
    assert result["requestedCount"] == 1
    receipts = list((tmp_path / "data" / "review" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1


def test_cookie_helpers_extract_browser_session_bits() -> None:
    cookie = "-b 'session_id=abc; csrftoken=token%20123; cf_clearance=xyz'"

    assert clean_cookie_header(cookie) == "session_id=abc; csrftoken=token%20123; cf_clearance=xyz"
    assert csrf_from_cookie(cookie) == "token 123"


from typer.testing import CliRunner

from monarch_money_tools.cmd.review import review_app


def test_review_revert_no_receipt_exits_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(review_app, ["revert"])
    assert result.exit_code == 1
    assert "No revert receipt found" in result.output


def test_review_revert_dry_run_shows_table(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.paths import review_revert_dir
    from monarch_money_tools.revert import build_revert_receipt, write_revert_receipt

    monkeypatch.chdir(tmp_path)
    receipt = build_revert_receipt(
        "monarch review apply",
        [
            {
                "type": "update_transaction",
                "entityId": "txn-1",
                "merchantName": "Starbucks",
                "before": {"categoryId": "cat-0", "categoryName": "Uncategorized", "needsReview": True},
                "after": {"categoryId": "cat-1", "categoryName": "Coffee Shops", "needsReview": False},
            }
        ],
    )
    write_revert_receipt(review_revert_dir(), receipt)

    runner = CliRunner()
    result = runner.invoke(review_app, ["revert", "--dry-run"])
    assert result.exit_code == 0
    assert "Starbucks" in result.output
    assert "Uncategorized" in result.output
