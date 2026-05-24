from __future__ import annotations

from pathlib import Path

from monarch_money_tools.csv_adapter import import_transactions_from_csv
from monarch_money_tools.monarch_api import clean_cookie_header, csrf_from_cookie
from monarch_money_tools.normalizer import (
    normalize_accounts,
    normalize_categories,
    normalize_transactions,
)
from monarch_money_tools.review import build_review_plan
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


def test_cookie_helpers_extract_browser_session_bits() -> None:
    cookie = "-b 'session_id=abc; csrftoken=token%20123; cf_clearance=xyz'"

    assert clean_cookie_header(cookie) == "session_id=abc; csrftoken=token%20123; cf_clearance=xyz"
    assert csrf_from_cookie(cookie) == "token 123"
