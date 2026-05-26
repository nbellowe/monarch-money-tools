from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from ..backup import create_pre_cleanup_backup, verify_pre_cleanup_backup
from ..cashflow import run_income_overlay
from ..doctor import collect_checks, has_python_project
from ..env import get_config
from ..exporter import resolve_csv_path, run_export
from ..recurring import run_recurring
from ..reporter import run_report
from ._utils import console, exit_with_file_error, run_async

data_app = typer.Typer(
    help="Data import, pull, analysis, and reporting commands.",
    no_args_is_help=True,
)


def resolve_run_bundle(csv_path: Path | None) -> Path:
    if csv_path is not None:
        return run_export(csv_path)
    configured_csv = resolve_csv_path(get_config().monarch_csv_path)
    if configured_csv is not None:
        return run_export(configured_csv)
    from ..paths import normalized_latest_dir

    bundle_path = normalized_latest_dir() / "bundle.json"
    if bundle_path.exists():
        return bundle_path
    raise FileNotFoundError(
        "No CSV or pulled data found. Run `monarch pull`, pass a CSV to "
        "`monarch run transactions.csv`, or run `monarch import transactions.csv`."
    )


@data_app.command("doctor")
def doctor_command() -> None:
    """Check local setup and generated artifact availability."""
    table = Table(title="Monarch Planner Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for name, ok, detail in collect_checks():
        table.add_row(name, "ok" if ok else "missing", detail)
    table.add_row("python project", "ok" if has_python_project() else "missing", "pyproject.toml")
    console.print(table)


@data_app.command("import")
def import_command(
    csv_path: Annotated[
        Path | None,
        typer.Argument(help="Path to a Monarch transaction CSV export."),
    ] = None,
) -> None:
    """Import and normalize a Monarch transaction CSV export."""
    try:
        bundle_path = run_export(csv_path)
    except FileNotFoundError as error:
        exit_with_file_error(error)
    console.print(f"[green]Wrote normalized bundle:[/] {bundle_path}")


@data_app.command("analyze")
def analyze_command() -> None:
    """Analyze normalized transactions for review and rule opportunities."""
    from ..analysis import run_analyze

    try:
        analysis = run_analyze()
    except FileNotFoundError as error:
        exit_with_file_error(error)
    summary = analysis["summary"]
    console.print(
        "[green]Analysis complete:[/] "
        f"{summary['miscategorizationCount']} category candidates, "
        f"{summary['ownerReviewCount']} owner candidates, "
        f"{summary['ruleOpportunityCount']} rule opportunities."
    )


@data_app.command("report")
def report_command() -> None:
    """Render Markdown and CSV reports from the latest analysis."""
    try:
        run_report()
    except FileNotFoundError as error:
        exit_with_file_error(error)
    console.print("[green]Reports written:[/] reports/latest")


@data_app.command("recurring")
def recurring_command(
    min_occurrences: Annotated[
        int,
        typer.Option(
            "--min-occurrences",
            min=2,
            help="Minimum transactions required before a recurring pattern qualifies.",
        ),
    ] = 2,
) -> None:
    """Detect recurring subscriptions, bills, transfers, and price drift."""
    report = run_recurring(min_occurrences=min_occurrences)
    summary = report["summary"]
    console.print(
        "[green]Recurring report written:[/] reports/latest/recurring.{md,csv} "
        f"({summary['patternCount']} patterns: "
        f"{summary['newCount']} new, "
        f"{summary['cancelledCount']} cancelled, "
        f"{summary['priceDriftCount']} price drift, "
        f"{summary['trialConversionCount']} trial conversions)"
    )


@data_app.command("income-overlay")
def income_overlay_command(
    start: Annotated[
        str | None,
        typer.Option("--start", help="Start date filter (YYYY-MM-DD, inclusive)."),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option("--end", help="End date filter (YYYY-MM-DD, inclusive)."),
    ] = None,
    profile_path: Annotated[
        Path | None,
        typer.Option("--profile", help="Path to profile.yaml (default: search cwd)."),
    ] = None,
) -> None:
    """Classify transactions as salary, reimbursement, transfer, investment, or spending."""
    from ..profile import ProfileNotFoundError, find_profile, load_profile

    profile = None
    try:
        resolved = profile_path or find_profile()
        if resolved:
            profile = load_profile(resolved)
    except ProfileNotFoundError:
        pass

    result = run_income_overlay(profile, start=start, end=end)
    summary = result["summary"]
    console.print(
        f"[green]Income overlay written:[/] data/cashflow/latest/ "
        f"({summary['transactionCount']} transactions)"
    )
    if summary["manualReviewCount"]:
        console.print(f"[yellow]{summary['manualReviewCount']} transactions need manual review.[/]")

    table = Table(title="Classification Summary")
    table.add_column("Classification")
    table.add_column("Count", justify="right")
    table.add_column("Total", justify="right")
    for row in summary["byLabel"]:
        table.add_row(row["label"], str(row["count"]), f"${row['total']:,.2f}")
    console.print(table)


@data_app.command("run")
def run_command(
    csv_path: Annotated[
        Path | None,
        typer.Argument(help="Path to a Monarch transaction CSV export."),
    ] = None,
) -> None:
    """Import if needed, then analyze and report in one safe read-only pass."""
    from ..analysis import run_analyze

    try:
        bundle_path = resolve_run_bundle(csv_path)
        analysis = run_analyze()
        run_report()
    except FileNotFoundError as error:
        exit_with_file_error(error)
    summary = analysis["summary"]
    console.print(f"[green]Input bundle:[/] {bundle_path}")
    console.print(
        "[green]Reports written:[/] reports/latest "
        f"({summary['miscategorizationCount']} category, "
        f"{summary['ownerReviewCount']} owner, "
        f"{summary['ruleOpportunityCount']} rule findings)"
    )


@data_app.command("backup")
def backup_command() -> None:
    """Back up current data/ and reports/ before cleanup or refresh work."""
    manifest = create_pre_cleanup_backup()
    missing = verify_pre_cleanup_backup(manifest)
    console.print(f"[green]Backup written:[/] {manifest['backupPath']}")
    console.print(
        "[cyan]File counts:[/] "
        f"data={manifest['fileCounts']['data']}, reports={manifest['fileCounts']['reports']}"
    )
    if missing:
        console.print("[red]Backup verification failed. Missing required paths:[/]")
        for path in missing:
            console.print(f"  - {path}")
        raise typer.Exit(1)


@data_app.command("pull")
def pull_command() -> None:
    """Pull Monarch data through the optional unofficial API adapter."""
    from ..monarch_api import pull_from_monarch_api

    bundle_path = run_async(pull_from_monarch_api())
    console.print(f"[green]Pulled Monarch data:[/] {bundle_path}")
