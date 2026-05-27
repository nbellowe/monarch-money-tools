from __future__ import annotations

from typing import Annotated

import typer

from ..paths import cleanup_latest_dir
from ..review_cleanup import run_review_cleanup
from ..storage import read_json
from ..taxonomy_cleanup import (
    apply_cleanup_plan,
    build_taxonomy_cleanup_plan,
    filter_cleanup_candidates,
    load_decisions,
)
from ._utils import _format_amount, console, exit_with_file_error, print_dry_run_table, run_async

cleanup_app = typer.Typer(help="Taxonomy and merchant cleanup commands.", no_args_is_help=True)


@cleanup_app.command("plan")
def cleanup_plan_command(
    show_rejected: Annotated[
        bool,
        typer.Option("--show-rejected", help="Include rejected candidates in the summary count."),
    ] = False,
) -> None:
    """Generate deterministic taxonomy cleanup candidates (migrations + merchant history)."""
    try:
        plan = build_taxonomy_cleanup_plan()
    except FileNotFoundError as error:
        exit_with_file_error(error)
    s = plan["summary"]
    cats = plan.get("categoriesToCreate") or []
    decisions = load_decisions()
    rejected_ids = {tid for tid, decision in decisions.items() if decision == "rejected"}
    ready_count = int(s["readyCount"])
    hidden_rejected = 0
    if not show_rejected:
        hidden_rejected = sum(
            1
            for candidate in plan.get("candidates", [])
            if candidate["transactionId"] in rejected_ids
            and not candidate.get("requiresNewCategory")
        )
        ready_count -= hidden_rejected

    console.print(
        "[green]Cleanup plan written:[/] data/cleanup/latest "
        f"({s['taxonomyMigrationCount']} taxonomy migrations, "
        f"{s['merchantConsistencyCount']} merchant consistency, "
        f"{ready_count} ready, {s['blockedCount']} blocked)"
    )
    if hidden_rejected:
        console.print(
            f"[dim]{hidden_rejected} rejected candidates hidden. "
            "Use --show-rejected to include them.[/]"
        )
    if cats:
        console.print(
            f"[yellow]Create these {len(cats)} categories in Monarch first "
            f"before applying blocked candidates:[/] "
            + ", ".join(f"{c['group']}/{c['name']}" for c in cats)
        )


@cleanup_app.command("review")
def review_cleanup_command() -> None:
    """Interactively accept, reject, or skip taxonomy cleanup candidates one at a time."""
    run_review_cleanup()


@cleanup_app.command("apply")
def apply_cleanup_command(
    yes: Annotated[
        bool, typer.Option("--yes", help="Apply the cleanup plan without an interactive prompt.")
    ] = False,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help="Apply at most this many updates.")
    ] = None,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            help="Filter to a specific source: taxonomy_migration or merchant_history.",
        ),
    ] = None,
    skip_blocked: Annotated[
        bool,
        typer.Option(
            "--skip-blocked",
            help="Skip candidates that require a new category (default: True).",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be applied without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Apply the latest taxonomy cleanup plan to Monarch."""
    plan_path = cleanup_latest_dir() / "cleanup-plan.json"
    if not plan_path.exists():
        console.print("[red]No cleanup plan found.[/] Run `monarch cleanup plan` first.")
        raise typer.Exit(1)

    plan = read_json(plan_path)
    candidates = filter_cleanup_candidates(
        plan, load_decisions(), skip_blocked=skip_blocked, source=source, limit=limit
    )
    blocked_count = sum(1 for c in plan.get("candidates", []) if c.get("requiresNewCategory"))

    if not candidates:
        console.print("[yellow]No applicable candidates to apply.[/]")
        if blocked_count:
            console.print(
                f"[yellow]{blocked_count} candidates are blocked pending new category creation.[/] "
                "See `data/cleanup/latest/cleanup-blocked.csv`."
            )
        raise typer.Exit(0)

    if dry_run:
        print_dry_run_table(
            f"Dry run - {len(candidates)} updates",
            candidates,
            [
                ("Merchant", None),
                ("Amount", "right"),
                ("Current Category", None),
                ("Suggested", None),
                ("Confidence", "right"),
                ("Source", None),
            ],
            lambda c: (
                c["merchantName"],
                _format_amount(c.get("amount")),
                c["currentCategory"],
                c["suggestedCategory"],
                f"{float(c.get('confidence', 0)):.0%}",
                c.get("source", ""),
            ),
            width=100,
        )
        return

    if not yes:
        confirmed = typer.confirm(
            f"Apply {len(candidates)} cleanup updates to Monarch via the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_cleanup_plan(candidates))
    console.print(f"[green]Applied cleanup updates:[/] {result['appliedCount']}")
