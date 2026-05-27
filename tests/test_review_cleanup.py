from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from monarch_money_tools.cli import app
from monarch_money_tools.storage import write_json
from monarch_money_tools.taxonomy_cleanup import load_decisions, save_decision


def _make_plan(tmp_path: Path) -> None:
    write_json(
        tmp_path / "data/cleanup/latest/cleanup-plan.json",
        {
            "candidates": [
                {
                    "transactionId": "txn-1",
                    "merchantName": "Mechanic",
                    "currentCategory": "Auto Maintenance",
                    "suggestedCategory": "Auto Maintenance & Fees",
                    "categoryId": "cat-1",
                    "confidence": 1.0,
                    "source": "taxonomy_migration",
                    "requiresNewCategory": False,
                    "setNeedsReview": False,
                    "date": "2026-01-01",
                    "amount": -100.0,
                    "accountName": "Checking",
                },
                {
                    "transactionId": "txn-2",
                    "merchantName": "Amazon",
                    "currentCategory": "Uncategorized",
                    "suggestedCategory": "Shopping",
                    "categoryId": "cat-2",
                    "confidence": 0.9,
                    "source": "merchant_history",
                    "requiresNewCategory": False,
                    "setNeedsReview": False,
                    "date": "2026-01-02",
                    "amount": -34.99,
                    "accountName": "Checking",
                },
            ]
        },
    )


def test_save_and_load_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    save_decision("txn-1", "accepted")
    save_decision("txn-2", "rejected")

    decisions = load_decisions()

    assert decisions["txn-1"] == "accepted"
    assert decisions["txn-2"] == "rejected"


def test_load_decisions_returns_empty_when_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_decisions() == {}


def test_apply_cleanup_respects_decision_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONARCH_DRY_RUN", raising=False)
    _make_plan(tmp_path)
    save_decision("txn-1", "accepted")
    save_decision("txn-2", "rejected")

    mini_bundle = {
        "transactions": [
            {"id": "txn-1", "categoryName": "Auto Maintenance", "needsReview": False},
            {"id": "txn-2", "categoryName": "Uncategorized", "needsReview": False},
        ],
        "categories": [
            {"id": "cat-1", "name": "Auto Maintenance & Fees"},
            {"id": "cat-2", "name": "Shopping"},
        ],
    }

    captured_updates = []

    def _capture(updates):  # type: ignore[no-untyped-def]
        captured_updates.extend(updates)
        return updates

    mock_apply = AsyncMock(side_effect=_capture)

    monkeypatch.setattr(
        "monarch_money_tools.taxonomy_cleanup.apply_transaction_updates",
        mock_apply,
    )
    monkeypatch.setattr(
        "monarch_money_tools.taxonomy_cleanup.load_bundle",
        lambda: mini_bundle,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["apply-cleanup", "--yes"])

    assert result.exit_code == 0, result.output
    assert len(captured_updates) == 1
    assert captured_updates[0]["transactionId"] == "txn-1"
