from __future__ import annotations

from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from monarch_money_tools.cli import app
from monarch_money_tools.storage import write_json


def test_cli_run_writes_reports(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    source = Path.cwd() / "tests/fixtures/monarch_transactions.csv"
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["run", str(source)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "data/normalized/latest/bundle.json").exists()
    assert (tmp_path / "data/analysis/latest/analysis.json").exists()
    assert (tmp_path / "reports/latest/summary.md").exists()


def test_cli_run_uses_existing_normalized_bundle(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    source = Path.cwd() / "tests/fixtures/monarch_transactions.csv"
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    imported = runner.invoke(app, ["import", str(source)])
    assert imported.exit_code == 0, imported.output

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0, result.output
    assert "Input bundle:" in result.output
    assert (tmp_path / "data/analysis/latest/analysis.json").exists()
    assert (tmp_path / "reports/latest/summary.md").exists()


def test_cli_run_without_input_prints_actionable_error(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "Missing input:" in result.output
    assert "monarch pull" in result.output
    assert "Traceback" not in result.output


def test_grouped_data_run_alias_works(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    source = Path.cwd() / "tests/fixtures/monarch_transactions.csv"
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["data", "run", str(source)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "reports/latest/summary.md").exists()


def test_grouped_review_apply_alias_dry_run(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    write_json(
        tmp_path / "data/review/latest/review-plan.json",
        {
            "generatedAt": "2026-05-24T00:00:00Z",
            "summary": {"plannedUpdateCount": 1, "deferredCount": 0},
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
                }
            ],
        },
    )
    runner = CliRunner()

    result = runner.invoke(app, ["review", "apply", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Acme Coffee" in result.output


def test_grouped_review_plan_prints_apply_dry_run_table_with_amount(
    tmp_path: Path,
    normalized_bundle: dict[str, Any],
) -> None:
    target = next(
        transaction
        for transaction in normalized_bundle["transactions"]
        if transaction["merchantName"] == "Acme Coffee"
        and transaction["categoryName"] == "Shopping"
    )
    target["needsReview"] = True
    write_json(tmp_path / "data/normalized/latest/bundle.json", normalized_bundle)
    runner = CliRunner()

    result = runner.invoke(app, ["review", "plan"])

    assert result.exit_code == 0, result.output
    assert "Review plan written" in result.output
    assert "Dry run - 1 updates" in result.output
    assert "Amount" in result.output
    assert "-$5.95" in result.output
    assert "Acme Coffee" in result.output
