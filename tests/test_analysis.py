from __future__ import annotations

from pathlib import Path

from monarch_money_tools.analysis import prepare_analysis
from monarch_money_tools.csv_adapter import import_transactions_from_csv
from monarch_money_tools.normalizer import (
    normalize_accounts,
    normalize_categories,
    normalize_transactions,
)


def test_prepare_analysis_finds_category_and_owner_reviews() -> None:
    imported = import_transactions_from_csv(Path("tests/fixtures/monarch_transactions.csv"))
    bundle = {
        "transactions": normalize_transactions(
            imported.transactions, imported.accounts, imported.categories
        ),
        "accounts": normalize_accounts(imported.accounts),
        "categories": normalize_categories(imported.categories),
        "transactionRules": [],
    }

    analysis = prepare_analysis(bundle)

    assert analysis["summary"]["transactionCount"] == 10
    assert analysis["summary"]["miscategorizationCount"] >= 1
    assert analysis["summary"]["ownerReviewCount"] >= 1
    assert analysis["heuristicRuleOpportunities"]
    assert analysis["miscategorizations"][0]["suggestedCategory"] == "Dining"
