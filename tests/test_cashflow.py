from __future__ import annotations

from monarch_money_tools.cashflow import classify_transactions
from monarch_money_tools.profile import CashflowConfig, IncomePatternConfig, UserProfile

BASE_TXN = {
    "id": "t1",
    "date": "2026-05-01",
    "merchantName": "Acme Corp Payroll",
    "categoryName": "Paychecks",
    "groupName": "Income",
    "signedAmount": 5000.0,
    "accountName": "Checking",
    "needsReview": False,
    "isPending": False,
}


def _profile_with_patterns() -> UserProfile:
    cashflow = CashflowConfig(
        income_sources=[IncomePatternConfig(pattern="Acme Corp Payroll")],
        reimbursement_patterns=[IncomePatternConfig(pattern="Expensify")],
        transfer_patterns=[IncomePatternConfig(pattern="Zelle from")],
    )
    return UserProfile(cashflow=cashflow)


def test_classify_salary_by_pattern() -> None:
    txn = {**BASE_TXN, "merchantName": "Acme Corp Payroll", "signedAmount": 5000.0}
    results = classify_transactions([txn], _profile_with_patterns())
    assert results[0]["classification"] == "salary"
    assert results[0]["manual_review"] is False


def test_classify_reimbursement_by_pattern() -> None:
    txn = {**BASE_TXN, "merchantName": "Expensify", "categoryName": "Other Income"}
    results = classify_transactions([txn], _profile_with_patterns())
    assert results[0]["classification"] == "reimbursement"


def test_classify_transfer_by_pattern() -> None:
    txn = {**BASE_TXN, "merchantName": "Zelle from Alex", "categoryName": "Transfer"}
    results = classify_transactions([txn], _profile_with_patterns())
    assert results[0]["classification"] == "transfer"


def test_classify_investment_proceeds_by_category() -> None:
    txn = {**BASE_TXN, "merchantName": "Vanguard", "categoryName": "Sell Investment"}
    results = classify_transactions([txn], None)
    assert results[0]["classification"] == "investment_proceeds"


def test_classify_salary_by_category_heuristic_when_no_profile() -> None:
    txn = {**BASE_TXN, "merchantName": "Unknown Payroll", "categoryName": "Paychecks"}
    results = classify_transactions([txn], None)
    assert results[0]["classification"] == "salary"


def test_classify_spending_as_default() -> None:
    txn = {**BASE_TXN, "merchantName": "Starbucks", "categoryName": "Dining", "signedAmount": -5.0}
    results = classify_transactions([txn], _profile_with_patterns())
    assert results[0]["classification"] == "spending"


def test_date_filter_start() -> None:
    txns = [
        {**BASE_TXN, "id": "a", "date": "2026-01-01"},
        {**BASE_TXN, "id": "b", "date": "2026-06-01"},
    ]
    results = classify_transactions(txns, None, start="2026-03-01")
    assert len(results) == 1
    assert results[0]["id"] == "b"


def test_date_filter_end() -> None:
    txns = [
        {**BASE_TXN, "id": "a", "date": "2026-01-01"},
        {**BASE_TXN, "id": "b", "date": "2026-06-01"},
    ]
    results = classify_transactions(txns, None, end="2026-03-01")
    assert len(results) == 1
    assert results[0]["id"] == "a"
