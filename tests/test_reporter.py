from __future__ import annotations

from pathlib import Path

from monarch_money_tools.analyzer import run_analyze
from monarch_money_tools.exporter import run_export
from monarch_money_tools.reporter import run_report


def test_report_preserves_specialized_reports(tmp_path: Path, monkeypatch) -> None:
    source = Path.cwd() / "tests/fixtures/monarch_transactions.csv"
    monkeypatch.chdir(tmp_path)
    run_export(source)
    run_analyze()
    specialized = tmp_path / "reports/latest/cashflow-analysis.md"
    specialized.parent.mkdir(parents=True)
    specialized.write_text("# Existing Cashflow\n", encoding="utf-8")

    run_report()

    assert specialized.read_text(encoding="utf-8") == "# Existing Cashflow\n"
    assert (tmp_path / "reports/latest/summary.md").exists()
