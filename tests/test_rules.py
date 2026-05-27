from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from monarch_money_tools.cmd.rules import rules_app
from monarch_money_tools.rules import (
    apply_rules_plan,
    build_apply_plan,
    build_push_rule_payload,
    match_transactions,
)
from monarch_money_tools.storage import read_json, write_json


def test_build_apply_plan_filters_to_requested_rule(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_json(
        tmp_path / "data/normalized/latest/bundle.json",
        {
            "transactions": [
                {
                    "id": "food-1",
                    "merchantName": "Cafe",
                    "categoryName": "Uncategorized",
                    "accountName": "Card",
                    "signedAmount": -12,
                    "needsReview": True,
                    "isPending": False,
                },
                {
                    "id": "gas-1",
                    "merchantName": "Fuel",
                    "categoryName": "Uncategorized",
                    "accountName": "Card",
                    "signedAmount": -40,
                    "needsReview": True,
                    "isPending": False,
                },
            ],
            "categories": [
                {"id": "cat-food", "name": "Restaurants & Bars"},
                {"id": "cat-gas", "name": "Gas"},
            ],
        },
    )
    write_json(
        tmp_path / "data/rules/latest/rule-suggestions.json",
        {
            "rules": [
                {
                    "id": "food",
                    "name": "Food rule",
                    "enabled": True,
                    "match": {"merchantNames": ["Cafe"], "needsReview": True},
                    "action": {
                        "setCategory": "Restaurants & Bars",
                        "setCategoryId": "cat-food",
                        "clearNeedsReview": True,
                    },
                },
                {
                    "id": "gas",
                    "name": "Gas rule",
                    "enabled": True,
                    "match": {"merchantNames": ["Fuel"], "needsReview": True},
                    "action": {
                        "setCategory": "Gas",
                        "setCategoryId": "cat-gas",
                        "clearNeedsReview": True,
                    },
                },
            ]
        },
    )

    plan = build_apply_plan(rules_filter=["food"])

    assert plan["summary"]["updateCount"] == 1
    assert plan["updates"][0]["transactionId"] == "food-1"
    assert plan["updates"][0]["amount"] == -12
    assert plan["updates"][0]["ruleId"] == "food"


def test_match_transactions_supports_pattern_and_needs_review_filter() -> None:
    transactions = [
        {"merchantName": "Tst* Cafe", "categoryName": "Dining", "needsReview": True},
        {"merchantName": "Tst* Cafe", "categoryName": "Dining", "needsReview": False},
    ]
    rule = {"match": {"merchantPattern": "Tst*", "needsReview": True}}

    matched = match_transactions(rule, transactions)

    assert len(matched) == 1
    assert matched[0]["needsReview"] is True


def test_build_push_rule_payload_with_merchant_names() -> None:
    rule = {
        "match": {"merchantNames": ["Coffee Shop", "Cafe"], "needsReview": True},
        "action": {"setCategory": "Dining", "clearNeedsReview": True},
    }
    payload = build_push_rule_payload(rule, category_id="cat-123")
    assert payload["setCategoryAction"] == "cat-123"
    assert payload["reviewStatusAction"] == "reviewed"
    assert len(payload["merchantNameCriteria"]) == 2
    assert payload["merchantNameCriteria"][0]["operator"] == "eq"
    assert payload["merchantNameCriteria"][0]["value"] == "coffee shop"


def test_build_push_rule_payload_with_merchant_pattern() -> None:
    rule = {
        "match": {"merchantPattern": "AMZN", "needsReview": True},
        "action": {"setCategory": "Shopping", "clearNeedsReview": False},
    }
    payload = build_push_rule_payload(rule, category_id="cat-shop")
    assert payload["merchantNameCriteria"][0]["operator"] == "contains"
    assert payload["merchantNameCriteria"][0]["value"] == "amzn"
    assert "reviewStatusAction" not in payload


def test_build_push_rule_payload_no_category() -> None:
    rule = {
        "match": {"merchantNames": ["Venmo"]},
        "action": {"clearNeedsReview": True},
    }
    payload = build_push_rule_payload(rule, category_id=None)
    assert "setCategoryAction" not in payload
    assert payload["reviewStatusAction"] == "reviewed"


def test_apply_rules_plan_emits_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t5", "categoryName": "Uncategorized", "needsReview": True}],
        "categories": [
            {"id": "c0", "name": "Uncategorized"},
            {"id": "c6", "name": "Dining"},
        ],
    }
    canned_plan = {
        "updates": [
            {
                "transactionId": "t5",
                "merchantName": "Chipotle",
                "suggestedCategory": "Dining",
                "categoryId": "c6",
                "clearNeedsReview": True,
                "ruleName": "Chipotle rule",
                "addTag": None,
            }
        ]
    }
    with (
        patch("monarch_money_tools.rules.build_apply_plan", return_value=canned_plan),
        patch(
            "monarch_money_tools.rules.apply_transaction_updates", new_callable=AsyncMock
        ) as mock_apply,
        patch("monarch_money_tools.rules.load_bundle", return_value=mini_bundle),
    ):
        mock_apply.return_value = [{"id": "t5"}]
        result = asyncio.run(apply_rules_plan())

    assert result["appliedCount"] == 1
    receipts = list((tmp_path / "data" / "rules" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1


def test_push_rule_emits_create_rule_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "rules" / "latest").mkdir(parents=True)
    write_json(
        tmp_path / "data" / "rules" / "latest" / "rule-suggestions.json",
        {
            "rules": [
                {
                    "id": "rule-local-1",
                    "name": "Chipotle → Dining",
                    "enabled": True,
                    "match": {"merchantNames": ["Chipotle"]},
                    "action": {"setCategory": "Dining", "clearNeedsReview": True},
                }
            ]
        },
    )

    fake_result = {"transactionRule": {"id": "monarch-rule-99", "order": 1}, "errors": None}

    def _mock_run_async(coro: object) -> object:
        # Close the coroutine to prevent "never awaited" RuntimeWarning before returning
        # the fake result (run_async is synchronous from the caller's perspective).
        if hasattr(coro, "close"):
            coro.close()
        return fake_result

    runner = CliRunner()
    with patch("monarch_money_tools.cmd.rules.run_async", side_effect=_mock_run_async):
        result = runner.invoke(rules_app, ["push", "rule-local-1", "--yes"])

    assert result.exit_code == 0, result.output
    receipts = list((tmp_path / "data" / "rules" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1
    receipt = read_json(receipts[0])
    assert receipt["operations"][0]["type"] == "create_rule"
    assert receipt["operations"][0]["entityId"] == "monarch-rule-99"


def test_rules_revert_no_receipt_exits_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(rules_app, ["revert"])
    assert result.exit_code == 1
    assert "No revert receipt found" in result.output


def test_rules_revert_dry_run_shows_table(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.paths import rules_revert_dir
    from monarch_money_tools.revert import build_revert_receipt, write_revert_receipt

    monkeypatch.chdir(tmp_path)
    receipt = build_revert_receipt(
        "monarch rules apply",
        [
            {
                "type": "update_transaction",
                "entityId": "txn-3",
                "merchantName": "Chipotle",
                "before": {
                    "categoryId": "cat-0",
                    "categoryName": "Uncategorized",
                    "needsReview": True,
                },
                "after": {
                    "categoryId": "cat-6",
                    "categoryName": "Dining",
                    "needsReview": False,
                },
            }
        ],
    )
    write_revert_receipt(rules_revert_dir(), receipt)

    runner = CliRunner()
    result = runner.invoke(rules_app, ["revert", "--dry-run"])
    assert result.exit_code == 0
    assert "Chipotle" in result.output
