from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from monarch_money_tools.cli import app


def test_cli_run_writes_reports(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    source = Path.cwd() / "tests/fixtures/monarch_transactions.csv"
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["run", str(source)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "data/normalized/latest/bundle.json").exists()
    assert (tmp_path / "data/analysis/latest/analysis.json").exists()
    assert (tmp_path / "reports/latest/summary.md").exists()
