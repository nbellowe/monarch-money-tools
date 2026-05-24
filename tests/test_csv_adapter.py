from __future__ import annotations

from pathlib import Path

from monarch_money_tools.csv_adapter import import_transactions_from_csv, slugify, split_tags
from monarch_money_tools.normalizer import normalize_transactions

FIXTURE = Path("tests/fixtures/monarch_transactions.csv")


def test_import_transactions_from_csv_extracts_reference_data() -> None:
    imported = import_transactions_from_csv(FIXTURE)

    assert len(imported.transactions) == 10
    assert imported.accounts[0]["displayName"] == "Checking"
    assert {category["name"] for category in imported.categories} >= {"Dining", "Groceries"}


def test_normalized_transactions_keep_amount_signs_and_tags() -> None:
    imported = import_transactions_from_csv(FIXTURE)
    transactions = normalize_transactions(
        imported.transactions, imported.accounts, imported.categories
    )

    coffee = transactions[0]
    payroll = transactions[-1]
    assert coffee["signedAmount"] == -5.25
    assert coffee["amount"] == 5.25
    assert coffee["tags"] == ["coffee", "work"]
    assert payroll["signedAmount"] == 2500.0


def test_helpers() -> None:
    assert slugify("Credit Card Payment", "category") == "credit-card-payment"
    assert slugify("", "account") == "account-unknown"
    assert split_tags("a;b | c, d") == ["a", "b", "c", "d"]
