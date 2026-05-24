from __future__ import annotations

from pathlib import Path

from monarch_money_tools.normalizer import normalize_merchant_name
from monarch_money_tools.recurring import analyze_recurring, run_recurring
from monarch_money_tools.storage import write_json


def test_analyze_recurring_detects_cadences_and_statuses() -> None:
    bundle = _bundle(
        [
            _txn("stream-1", "2026-01-01", "Stream Co", -10.00),
            _txn("stream-2", "2026-02-01", "Stream Co", -10.00),
            _txn("stream-3", "2026-03-01", "Stream Co", -10.00),
            _txn("stream-4", "2026-04-01", "Stream Co", -10.00),
            _txn("stream-5", "2026-05-01", "Stream Co", -12.00),
            _txn("gym-1", "2026-04-10", "Weekly Gym", -5.00),
            _txn("gym-2", "2026-04-17", "Weekly Gym", -5.00),
            _txn("gym-3", "2026-04-24", "Weekly Gym", -5.00),
            _txn("gym-4", "2026-05-01", "Weekly Gym", -5.00),
            _txn("insurance-1", "2024-05-01", "Annual Insurance", -100.00),
            _txn("insurance-2", "2025-05-01", "Annual Insurance", -100.00),
            _txn("insurance-3", "2026-05-01", "Annual Insurance", -100.00),
            _txn("old-cloud-1", "2026-01-15", "Old Cloud", -6.00),
            _txn("old-cloud-2", "2026-02-15", "Old Cloud", -6.00),
            _txn("old-cloud-3", "2026-03-15", "Old Cloud", -6.00),
            _txn("trial-1", "2026-02-01", "Trial App", 0.00),
            _txn("trial-2", "2026-03-01", "Trial App", -9.99),
            _txn("trial-3", "2026-04-01", "Trial App", -9.99),
            _txn("every-1", "2026-02-07", "Every 21", -15.00),
            _txn("every-2", "2026-02-28", "Every 21", -15.00),
            _txn("every-3", "2026-03-21", "Every 21", -15.00),
            _txn("every-4", "2026-04-11", "Every 21", -15.00),
            _txn("every-5", "2026-05-02", "Every 21", -15.00),
        ]
    )

    report = analyze_recurring(bundle)
    by_merchant = {pattern["merchantName"]: pattern for pattern in report["patterns"]}

    assert by_merchant["Stream Co"]["cadence"] == "monthly"
    assert by_merchant["Stream Co"]["status"] == "price_drift"
    assert by_merchant["Stream Co"]["priceDriftPct"] == 0.2
    assert by_merchant["Weekly Gym"]["cadence"] == "weekly"
    assert by_merchant["Weekly Gym"]["status"] == "stable"
    assert by_merchant["Annual Insurance"]["cadence"] == "annual"
    assert by_merchant["Old Cloud"]["status"] == "cancelled"
    assert by_merchant["Trial App"]["status"] == "trial_conversion"
    assert by_merchant["Every 21"]["cadenceType"] == "irregular"
    assert by_merchant["Every 21"]["cadence"] == "every 21 days"
    assert report["summary"]["priceDriftCount"] == 1
    assert report["summary"]["cancelledCount"] == 1
    assert report["summary"]["trialConversionCount"] == 1


def test_min_occurrences_is_configurable() -> None:
    bundle = _bundle(
        [
            _txn("two-1", "2026-01-01", "Two Charge", -10.00),
            _txn("two-2", "2026-02-01", "Two Charge", -10.00),
        ]
    )

    assert len(analyze_recurring(bundle, min_occurrences=2)["patterns"]) == 1
    assert analyze_recurring(bundle, min_occurrences=3)["patterns"] == []


def test_run_recurring_writes_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_json(
        tmp_path / "data/normalized/latest/bundle.json",
        _bundle(
            [
                _txn("music-1", "2026-01-01", "Music Service", -8.00),
                _txn("music-2", "2026-02-01", "Music Service", -8.00),
                _txn("music-3", "2026-03-01", "Music Service", -8.00),
            ]
        ),
    )

    report = run_recurring()

    assert report["summary"]["patternCount"] == 1
    assert (tmp_path / "reports/latest/recurring.md").exists()
    assert (tmp_path / "reports/latest/recurring.csv").exists()


def _bundle(transactions: list[dict[str, object]]) -> dict[str, object]:
    return {
        "exportedAt": "2026-05-02T00:00:00Z",
        "transactions": transactions,
        "accounts": [],
        "categories": [],
    }


def _txn(
    transaction_id: str,
    transaction_date: str,
    merchant: str,
    amount: float,
) -> dict[str, object]:
    return {
        "id": transaction_id,
        "date": transaction_date,
        "merchantName": merchant,
        "normalizedMerchant": normalize_merchant_name(merchant),
        "signedAmount": amount,
        "categoryName": "Subscriptions",
        "accountName": "Checking",
        "isPending": False,
    }
