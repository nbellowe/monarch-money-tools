from __future__ import annotations

from typing import Annotated

import typer

from ..paths import review_latest_dir, review_revert_dir
from ..revert import execute_revert, find_latest_receipt
from ..review import (
    DEFAULT_CLEAR_REVIEW_CATEGORIES,
    apply_clear_review_plan,
    apply_review_plan,
    build_clear_review_plan,
    build_review_plan,
)
from ..storage import read_json
from ._utils import _format_amount, console, exit_with_file_error, print_dry_run_table, run_async

review_app = typer.Typer(help="Needs-Review planning and apply commands.", no_args_is_help=True)

_REVIEW_COLUMNS = [
    ("Merchant", None),
    ("Amount", "right"),
    ("Current Category", None),
    ("Suggested", None),
    ("Confidence", "right"),
]


@review_app.command("plan")
def plan_reviews_command(
    min_confidence: Annotated[
        float,
        typer.Option(
            "--min-confidence",
            min=0.0,
            max=1.0,
            help="Minimum confidence required before planning an update.",
        ),
    ] = 0.78,
    include_pending: Annotated[
        bool,
        typer.Option("--include-pending", help="Include pending transactions in the plan."),
    ] = False,
    skip_already_correct: Annotated[
        bool,
        typer.Option(
            "--skip-already-correct",
            help="Do not clear review status when the category already matches history.",
        ),
    ] = False,
) -> None:
    """Plan category/review updates for transactions marked Needs Review."""
    try:
        plan = build_review_plan(
            min_confidence=min_confidence,
            include_pending=include_pending,
            review_correct_categories=not skip_already_correct,
        )
    except FileNotFoundError as error:
        exit_with_file_error(error)
    summary = plan["summary"]
    console.print(
        "[green]Review plan written:[/] data/review/latest/review-plan.json "
        f"({summary['plannedUpdateCount']} planned, {summary['deferredCount']} deferred)"
    )
    updates = list(plan.get("updates") or [])
    if updates:
        print_dry_run_table(
            f"Dry run - {len(updates)} updates",
            updates,
            _REVIEW_COLUMNS,
            lambda u: (
                u["merchantName"],
                _format_amount(u.get("amount")),
                u["currentCategory"],
                u["suggestedCategory"],
                f"{float(u.get('confidence', 0)):.0%}",
            ),
        )


@review_app.command("apply")
def apply_reviews_command(
    yes: Annotated[
        bool, typer.Option("--yes", help="Apply without an interactive prompt.")
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many planned updates."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be applied without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Apply the latest planned transaction updates to Monarch."""
    plan_path = review_latest_dir() / "review-plan.json"
    if not plan_path.exists():
        console.print("[red]No review plan found.[/] Run `monarch review plan` first.")
        raise typer.Exit(1)

    plan = read_json(plan_path)
    updates = list(plan.get("updates") or [])
    if limit is not None:
        updates = updates[:limit]

    if not updates:
        console.print("[yellow]No updates to apply.[/]")
        raise typer.Exit(0)

    if dry_run:
        print_dry_run_table(
            f"Dry run - {len(updates)} updates",
            updates,
            _REVIEW_COLUMNS,
            lambda u: (
                u["merchantName"],
                _format_amount(u.get("amount")),
                u["currentCategory"],
                u["suggestedCategory"],
                f"{float(u.get('confidence', 0)):.0%}",
            ),
        )
        return

    if not yes:
        confirmed = typer.confirm(
            "This will update Monarch transactions through the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_review_plan(updates))
    console.print(f"[green]Applied review updates:[/] {result['requestedCount']}")


@review_app.command("clear-plan")
def plan_clear_reviews_command(
    categories: Annotated[
        str,
        typer.Option(
            "--categories", help="Comma-separated category names trusted for clearing Needs Review."
        ),
    ] = ",".join(DEFAULT_CLEAR_REVIEW_CATEGORIES),
) -> None:
    """Write a reviewable plan for clearing Needs Review on trusted categories."""
    trusted = [c.strip() for c in categories.split(",") if c.strip()]
    try:
        plan = build_clear_review_plan(trusted)
    except FileNotFoundError as error:
        exit_with_file_error(error)
    summary = plan["summary"]
    console.print(
        "[green]Clear-review plan written:[/] data/review/latest/clear-review-plan.json "
        f"({summary['plannedUpdateCount']} planned, {summary['deferredCount']} deferred)"
    )


@review_app.command("clear-apply")
def apply_clear_reviews_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply the latest clear-review plan without a prompt."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many planned clears."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be applied without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Apply the latest reviewed clear-review plan to Monarch."""
    plan_path = review_latest_dir() / "clear-review-plan.json"
    if not plan_path.exists():
        console.print("[red]No clear-review plan found.[/] Run `monarch review clear-plan` first.")
        raise typer.Exit(1)

    plan = read_json(plan_path)
    updates = list(plan.get("updates") or [])
    if limit is not None:
        updates = updates[:limit]

    if not updates:
        console.print("[yellow]No updates to apply.[/]")
        raise typer.Exit(0)

    if dry_run:
        print_dry_run_table(
            f"Dry run - {len(updates)} clears",
            updates,
            [("Merchant", None), ("Amount", "right"), ("Category", None), ("Account", None)],
            lambda u: (
                u["merchantName"],
                _format_amount(u.get("amount")),
                u["currentCategory"],
                u.get("accountName", ""),
            ),
        )
        return

    if not yes:
        confirmed = typer.confirm(
            "This will clear Needs Review through the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_clear_review_plan(updates))
    console.print(f"[green]Cleared review flag on:[/] {result['requestedCount']} transactions")


@review_app.command("llm-plan")
def llm_review_command(
    focus: Annotated[
        str | None,
        typer.Option(
            "--focus",
            help=(
                "Comma-separated category names to focus on "
                "(default: Uncategorized,Misc Travel Expenses,Paychecks)."
            ),
        ),
    ] = None,
    backend: Annotated[
        str,
        typer.Option(
            "--backend",
            help="LLM backend: 'cli' (claude -p) or 'api' (ANTHROPIC_API_KEY).",
        ),
    ] = "cli",
    model: Annotated[
        str | None,
        typer.Option("--model", help="Model override, e.g. claude-haiku-4-5-20251001."),
    ] = None,
    skip_p2p: Annotated[
        bool,
        typer.Option(
            "--skip-p2p/--no-skip-p2p",
            help="Skip P2P accounts (Venmo, Personal Profile, etc.). Default: True.",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show scope without calling the LLM.", envvar="MONARCH_DRY_RUN"
        ),
    ] = False,
) -> None:
    """Run an LLM-assisted categorization pass on ambiguous needs-review transactions."""
    from ..llm_review import FOCUS_CATEGORIES, build_llm_review_plan

    focus_categories = (
        {c.strip() for c in focus.split(",") if c.strip()} if focus else FOCUS_CATEGORIES
    )
    try:
        plan = build_llm_review_plan(
            focus_categories=focus_categories,
            dry_run=dry_run,
            backend=backend,
            model=model,
            skip_p2p=skip_p2p,
        )
    except FileNotFoundError as error:
        exit_with_file_error(error)
    if dry_run:
        console.print(
            f"[cyan]Dry run:[/] {plan['transactionCount']} transactions, "
            f"{plan['merchantCount']} unique merchants, "
            f"{plan['batchCount']} LLM batches."
        )
        return
    s = plan["summary"]
    console.print(
        f"[green]LLM review plan written:[/] data/review/latest/llm-review-plan.{{json,csv,md}} "
        f"({s['updateCount']} updates proposed: "
        f"{s['highConfidenceCount']} high-confidence, {s['lowConfidenceCount']} low)"
    )


@review_app.command("llm", hidden=True, deprecated=True)
def llm_review_command_deprecated(
    focus: Annotated[str | None, typer.Option("--focus")] = None,
    backend: Annotated[str, typer.Option("--backend")] = "cli",
    model: Annotated[str | None, typer.Option("--model")] = None,
    skip_p2p: Annotated[bool, typer.Option("--skip-p2p/--no-skip-p2p")] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", envvar="MONARCH_DRY_RUN")] = False,
) -> None:
    """Deprecated: use `monarch review llm-plan` instead."""
    console.print(
        "[yellow]Warning:[/] `monarch review llm` is deprecated. "
        "Use `monarch review llm-plan` instead."
    )
    llm_review_command(
        focus=focus, backend=backend, model=model, skip_p2p=skip_p2p, dry_run=dry_run
    )


@review_app.command("llm-apply")
def apply_llm_review_command(
    yes: Annotated[
        bool, typer.Option("--yes", help="Apply without an interactive prompt.")
    ] = False,
    min_confidence: Annotated[
        float,
        typer.Option("--min-confidence", min=0.0, max=1.0, help="Minimum confidence to apply."),
    ] = 0.85,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many updates."),
    ] = None,
    category: Annotated[
        list[str] | None,
        typer.Option(
            "--category",
            help="Only apply updates for this suggested category (repeatable).",
        ),
    ] = None,
    exclude_merchant: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude-merchant",
            help="Skip updates for this merchant name (repeatable).",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be applied without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Apply the latest LLM review plan to Monarch."""
    plan_path = review_latest_dir() / "llm-review-plan.json"
    if not plan_path.exists():
        console.print("[red]No LLM review plan found.[/] Run `monarch review llm` first.")
        raise typer.Exit(1)

    plan = read_json(plan_path)
    updates = [
        u for u in (plan.get("updates") or []) if float(u.get("confidence", 0)) >= min_confidence
    ]
    if category:
        updates = [u for u in updates if u.get("suggestedCategory") in category]
    if exclude_merchant:
        updates = [u for u in updates if u.get("merchantName") not in exclude_merchant]
    if limit is not None:
        updates = updates[:limit]

    if not updates:
        console.print(f"[yellow]No updates meet min-confidence {min_confidence}.[/]")
        raise typer.Exit(0)

    if dry_run:
        print_dry_run_table(
            f"Dry run - {len(updates)} updates",
            updates,
            _REVIEW_COLUMNS,
            lambda u: (
                u["merchantName"],
                _format_amount(u.get("amount")),
                u["currentCategory"],
                u["suggestedCategory"],
                f"{float(u.get('confidence', 0)):.0%}",
            ),
        )
        return

    if not yes:
        confirmed = typer.confirm(f"Apply {len(updates)} LLM review updates to Monarch? Continue?")
        if not confirmed:
            raise typer.Abort()

    from ..llm_review import apply_llm_review_plan

    result = run_async(apply_llm_review_plan(updates))
    console.print(f"[green]Applied LLM review updates:[/] {result['appliedCount']}")


@review_app.command("bulk-clear")
def bulk_clear_reviews_command(
    categories: Annotated[
        str,
        typer.Option(
            "--categories", help="Comma-separated category names to trust and clear review flag."
        ),
    ] = "Transfer,Credit Card Payment,Buy Investment,Sell Investment,Interest",
    yes: Annotated[
        bool, typer.Option("--yes", help="Apply without an interactive prompt.")
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many clears."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be applied without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Build and optionally apply a clear-review plan for trusted categories."""
    trust_categories = {c.strip() for c in categories.split(",") if c.strip()}
    plan = build_clear_review_plan(sorted(trust_categories))
    updates = list(plan.get("updates") or [])
    if limit is not None:
        updates = updates[:limit]
    planned_count = int(plan["summary"]["plannedUpdateCount"])
    if not updates:
        console.print("[yellow]No transactions to clear.[/]")
        raise typer.Exit(0)

    console.print(
        f"Clear-review plan written with [bold]{planned_count}[/] transactions "
        f"in: {', '.join(sorted(trust_categories))}"
    )
    if dry_run:
        print_dry_run_table(
            f"Dry run - {len(updates)} clears",
            updates,
            [("Merchant", None), ("Amount", "right"), ("Category", None), ("Account", None)],
            lambda u: (
                u["merchantName"],
                _format_amount(u.get("amount")),
                u["currentCategory"],
                u.get("accountName", ""),
            ),
        )
        return

    if not yes:
        confirmed = typer.confirm(f"Apply {len(updates)} planned review clears now?")
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_clear_review_plan(updates))
    console.print(f"[green]Cleared review flag on:[/] {result['requestedCount']} transactions")


_REVERT_COLUMNS = [
    ("Merchant", None),
    ("Current Category", None),
    ("Restoring Category", None),
    ("Review", None),
]


@review_app.command("revert")
def revert_reviews_command(
    receipt: Annotated[
        str | None,
        typer.Option("--receipt", help="Path to a specific revert receipt file."),
    ] = None,
    yes: Annotated[
        bool, typer.Option("--yes", help="Revert without an interactive prompt.")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be reverted without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Revert the latest review apply using its revert receipt."""
    from pathlib import Path

    receipt_path = Path(receipt) if receipt else find_latest_receipt(review_revert_dir())
    if not receipt_path:
        console.print("[red]No revert receipt found.[/] Run `monarch review apply` first.")
        raise typer.Exit(1)

    receipt_data = read_json(receipt_path)
    ops = [
        op
        for op in (receipt_data.get("operations") or [])
        if op.get("type") == "update_transaction"
    ]

    if not ops:
        console.print("[yellow]No revertable operations in this receipt.[/]")
        raise typer.Exit(0)

    console.print(f"Using receipt: [dim]{receipt_path}[/] ({len(ops)} operations)")
    print_dry_run_table(
        f"{'Dry run - ' if dry_run else ''}Revert {len(ops)} operations",
        ops,
        _REVERT_COLUMNS,
        lambda op: (
            op.get("merchantName", ""),
            (op.get("after") or {}).get("categoryName", ""),
            (op.get("before") or {}).get("categoryName", ""),
            str((op.get("before") or {}).get("needsReview", "")),
        ),
    )

    if dry_run:
        return

    if not yes:
        confirmed = typer.confirm(f"Revert {len(ops)} operations in Monarch? Continue?")
        if not confirmed:
            raise typer.Abort()

    result = run_async(execute_revert(receipt_path))
    console.print(f"[green]Reverted:[/] {result['revertedCount']} operations")
    if result.get("skippedCount"):
        console.print(f"[yellow]Skipped:[/] {result['skippedCount']} operations (unknown type)")
