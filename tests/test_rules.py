from __future__ import annotations

from pathlib import Path

from monarch_money_tools.rules import build_apply_plan, build_push_rule_payload, match_transactions
from monarch_money_tools.storage import write_json


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
