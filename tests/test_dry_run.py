from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from monarch_money_tools.cli import app
from monarch_money_tools.storage import write_json

runner = CliRunner()


def _write_review_plan(tmp_path: Path) -> None:
    plan = {
        "generatedAt": "2026-05-24T00:00:00Z",
        "summary": {"plannedUpdateCount": 2, "deferredCount": 0},
        "updates": [
            {
                "transactionId": "t1",
                "date": "2026-05-01",
                "merchantName": "Acme Coffee",
                "accountName": "Checking",
                "amount": -5.25,
                "currentCategory": "Shopping",
                "suggestedCategory": "Dining",
                "categoryId": "cat-dining",
                "confidence": 0.92,
                "action": "recategorize",
                "setNeedsReview": False,
            },
            {
                "transactionId": "t2",
                "date": "2026-05-02",
                "merchantName": "Gas Station",
                "accountName": "Checking",
                "amount": -45.00,
                "currentCategory": "Uncategorized",
                "suggestedCategory": "Auto & Transport",
                "categoryId": "cat-auto",
                "confidence": 0.88,
                "action": "recategorize",
                "setNeedsReview": False,
            },
        ],
    }
    write_json(tmp_path / "data/review/latest/review-plan.json", plan)


def _write_clear_review_plan(tmp_path: Path) -> None:
    plan = {
        "generatedAt": "2026-05-24T00:00:00Z",
        "summary": {"plannedUpdateCount": 1, "deferredCount": 0, "trustedCategories": ["Dining"]},
        "updates": [
            {
                "transactionId": "t3",
                "date": "2026-05-03",
                "merchantName": "Sushi Place",
                "accountName": "Checking",
                "amount": -32.00,
                "currentCategory": "Dining",
                "suggestedCategory": "Dining",
                "categoryId": "cat-dining",
                "currentNeedsReview": True,
                "setNeedsReview": False,
                "confidence": 0.99,
                "action": "clear_review",
                "rationale": "Dining is trusted.",
            }
        ],
        "deferred": [],
    }
    write_json(tmp_path / "data/review/latest/clear-review-plan.json", plan)


def _write_cleanup_plan(tmp_path: Path) -> None:
    plan = {
        "generatedAt": "2026-05-24T00:00:00Z",
        "summary": {
            "taxonomyMigrationCount": 1,
            "merchantConsistencyCount": 0,
            "readyCount": 1,
            "blockedCount": 0,
        },
        "candidates": [
            {
                "transactionId": "t4",
                "date": "2026-05-04",
                "merchantName": "Mechanic Shop",
                "accountName": "Checking",
                "amount": -200.00,
                "currentCategory": "Auto Maintenance",
                "suggestedCategory": "Auto Maintenance & Fees",
                "categoryId": "cat-auto-maint",
                "confidence": 1.0,
                "source": "taxonomy_migration",
                "requiresNewCategory": False,
                "setNeedsReview": False,
            }
        ],
    }
    write_json(tmp_path / "data/cleanup/latest/cleanup-plan.json", plan)


def _write_llm_review_plan(tmp_path: Path) -> None:
    plan = {
        "generatedAt": "2026-05-24T00:00:00Z",
        "summary": {"updateCount": 2, "highConfidenceCount": 1, "lowConfidenceCount": 1},
        "updates": [
            {
                "transactionId": "t5",
                "date": "2026-05-05",
                "merchantName": "Amazon",
                "accountName": "Checking",
                "amount": -34.99,
                "currentCategory": "Uncategorized",
                "suggestedCategory": "Shopping",
                "categoryId": "cat-shopping",
                "confidence": 0.95,
                "source": "llm_review",
                "setNeedsReview": False,
            },
            {
                "transactionId": "t6",
                "date": "2026-05-06",
                "merchantName": "Mystery Store",
                "accountName": "Checking",
                "amount": -12.00,
                "currentCategory": "Uncategorized",
                "suggestedCategory": "Shopping",
                "categoryId": "cat-shopping",
                "confidence": 0.70,
                "source": "llm_review",
                "setNeedsReview": False,
            },
        ],
    }
    write_json(tmp_path / "data/review/latest/llm-review-plan.json", plan)


def test_apply_reviews_dry_run_prints_table_and_skips_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_review_plan(tmp_path)

    api_called = []
    monkeypatch.setattr(
        "monarch_money_tools.cli.run_async",
        lambda coro: api_called.append(coro) or {},
    )

    result = runner.invoke(app, ["apply-reviews", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert not api_called, "API should not be called during dry-run"
    assert "Acme Coffee" in result.output
    assert "Gas Station" in result.output
    assert "Dining" in result.output


def test_apply_clear_reviews_dry_run_prints_table_and_skips_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_clear_review_plan(tmp_path)

    api_called = []
    monkeypatch.setattr(
        "monarch_money_tools.cli.run_async",
        lambda coro: api_called.append(coro) or {},
    )

    result = runner.invoke(app, ["apply-clear-reviews", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert not api_called
    assert "Sushi Place" in result.output
    assert "Dining" in result.output


def test_apply_cleanup_dry_run_prints_table_and_skips_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_cleanup_plan(tmp_path)

    api_called = []
    monkeypatch.setattr(
        "monarch_money_tools.cli.run_async",
        lambda coro: api_called.append(coro) or {},
    )

    result = runner.invoke(app, ["apply-cleanup", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert not api_called
    assert "Mechanic Shop" in result.output
    assert "Auto Maintenance & Fees" in result.output


def test_apply_llm_review_dry_run_prints_table_and_skips_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_llm_review_plan(tmp_path)

    api_called = []
    monkeypatch.setattr(
        "monarch_money_tools.cli.run_async",
        lambda coro: api_called.append(coro) or {},
    )

    result = runner.invoke(app, ["apply-llm-review", "--dry-run", "--min-confidence", "0.85"])

    assert result.exit_code == 0, result.output
    assert not api_called
    assert "Amazon" in result.output
    assert "Mystery Store" not in result.output
