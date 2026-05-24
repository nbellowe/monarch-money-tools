from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Annotated, Any, TypeVar, cast

import typer
from rich.console import Console
from rich.table import Table

from .analyzer import run_analyze
from .backup import create_pre_cleanup_backup, verify_pre_cleanup_backup
from .doctor import collect_checks, has_python_project
from .exporter import run_export
from .llm_review import FOCUS_CATEGORIES, build_llm_review_plan
from .monarch_api import (
    apply_transaction_updates,
    delete_monarch_rule,
    fetch_portfolio_allocation,
    fetch_transaction_rules,
    pull_from_monarch_api,
    tag_transactions,
)
from .recurring import run_recurring
from .reporter import run_report
from .review import (
    DEFAULT_CLEAR_REVIEW_CATEGORIES,
    apply_clear_review_plan,
    apply_review_plan,
    build_clear_review_plan,
    build_review_plan,
)
from .rules import apply_rules_plan, build_rule_suggestions
from .taxonomy_cleanup import build_taxonomy_cleanup_plan

app = typer.Typer(
    help="Local-first Monarch Money export analysis and planning CLI.",
    no_args_is_help=True,
)
console = Console()
T = TypeVar("T")


@app.command("doctor")
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


@app.command("import")
def import_command(
    csv_path: Annotated[
        Path | None,
        typer.Argument(help="Path to a Monarch transaction CSV export."),
    ] = None,
) -> None:
    """Import and normalize a Monarch transaction CSV export."""
    bundle_path = run_export(csv_path)
    console.print(f"[green]Wrote normalized bundle:[/] {bundle_path}")


@app.command("analyze")
def analyze_command() -> None:
    """Analyze normalized transactions for review and rule opportunities."""
    analysis = run_analyze()
    summary = analysis["summary"]
    console.print(
        "[green]Analysis complete:[/] "
        f"{summary['miscategorizationCount']} category candidates, "
        f"{summary['ownerReviewCount']} owner candidates, "
        f"{summary['ruleOpportunityCount']} rule opportunities."
    )


@app.command("report")
def report_command() -> None:
    """Render Markdown and CSV reports from the latest analysis."""
    run_report()
    console.print("[green]Reports written:[/] reports/latest")


@app.command("recurring")
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


@app.command("run")
def run_command(
    csv_path: Annotated[
        Path | None,
        typer.Argument(help="Path to a Monarch transaction CSV export."),
    ] = None,
) -> None:
    """Import, analyze, and report in one safe read-only pass."""
    bundle_path = run_export(csv_path)
    analysis = run_analyze()
    run_report()
    summary = analysis["summary"]
    console.print(f"[green]Imported:[/] {bundle_path}")
    console.print(
        "[green]Reports written:[/] reports/latest "
        f"({summary['miscategorizationCount']} category, "
        f"{summary['ownerReviewCount']} owner, "
        f"{summary['ruleOpportunityCount']} rule findings)"
    )


@app.command("backup")
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


@app.command("cleanup-plan")
def cleanup_plan_command() -> None:
    """Generate deterministic taxonomy cleanup candidates (migrations + merchant history)."""
    plan = build_taxonomy_cleanup_plan()
    s = plan["summary"]
    cats = plan.get("categoriesToCreate") or []
    console.print(
        "[green]Cleanup plan written:[/] data/cleanup/latest "
        f"({s['taxonomyMigrationCount']} taxonomy migrations, "
        f"{s['merchantConsistencyCount']} merchant consistency, "
        f"{s['readyCount']} ready, {s['blockedCount']} blocked)"
    )
    if cats:
        console.print(
            f"[yellow]Create these {len(cats)} categories in Monarch first "
            f"before applying blocked candidates:[/] "
            + ", ".join(f"{c['group']}/{c['name']}" for c in cats)
        )


@app.command("apply-cleanup")
def apply_cleanup_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply the cleanup plan without an interactive prompt."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many updates."),
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
) -> None:
    """Apply the latest taxonomy cleanup plan to Monarch."""
    from .paths import cleanup_latest_dir
    from .storage import read_json

    plan_path = cleanup_latest_dir() / "cleanup-plan.json"
    if not plan_path.exists():
        console.print("[red]No cleanup plan found.[/] Run `monarch cleanup-plan` first.")
        raise typer.Exit(1)

    plan = read_json(plan_path)
    candidates = list(plan.get("candidates") or [])

    if skip_blocked:
        candidates = [c for c in candidates if not c.get("requiresNewCategory")]
    if source:
        candidates = [c for c in candidates if c.get("source") == source]
    if limit is not None:
        candidates = candidates[:limit]

    blocked_count = sum(1 for c in plan.get("candidates", []) if c.get("requiresNewCategory"))
    if not candidates:
        console.print("[yellow]No applicable candidates to apply.[/]")
        if blocked_count:
            console.print(
                f"[yellow]{blocked_count} candidates are blocked pending new category creation.[/] "
                "See `data/cleanup/latest/cleanup-blocked.csv`."
            )
        raise typer.Exit(0)

    if not yes:
        confirmed = typer.confirm(
            f"Apply {len(candidates)} cleanup updates to Monarch via the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    updates = [
        {
            "transactionId": c["transactionId"],
            "merchantName": c["merchantName"],
            "suggestedCategory": c["suggestedCategory"],
            "categoryId": c["categoryId"],
            "setNeedsReview": c.get("setNeedsReview", False),
        }
        for c in candidates
        if c.get("categoryId")
    ]
    result = run_async(apply_transaction_updates(updates))
    console.print(f"[green]Applied cleanup updates:[/] {len(result)}")


@app.command("pull")
def pull_command() -> None:
    """Pull Monarch data through the optional unofficial API adapter."""
    bundle_path = run_async(pull_from_monarch_api())
    console.print(f"[green]Pulled Monarch data:[/] {bundle_path}")


@app.command("plan-reviews")
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
    plan = build_review_plan(
        min_confidence=min_confidence,
        include_pending=include_pending,
        review_correct_categories=not skip_already_correct,
    )
    summary = plan["summary"]
    console.print(
        "[green]Review plan written:[/] data/review/latest/review-plan.json "
        f"({summary['plannedUpdateCount']} planned, {summary['deferredCount']} deferred)"
    )


@app.command("plan-clear-reviews")
def plan_clear_reviews_command(
    categories: Annotated[
        str,
        typer.Option(
            "--categories",
            help="Comma-separated category names trusted for clearing Needs Review.",
        ),
    ] = ",".join(DEFAULT_CLEAR_REVIEW_CATEGORIES),
) -> None:
    """Write a reviewable plan for clearing Needs Review on trusted categories."""
    trusted = [category.strip() for category in categories.split(",") if category.strip()]
    plan = build_clear_review_plan(trusted)
    summary = plan["summary"]
    console.print(
        "[green]Clear-review plan written:[/] data/review/latest/clear-review-plan.json "
        f"({summary['plannedUpdateCount']} planned, {summary['deferredCount']} deferred)"
    )


@app.command("apply-clear-reviews")
def apply_clear_reviews_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply the latest clear-review plan without a prompt."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many planned clears."),
    ] = None,
) -> None:
    """Apply the latest reviewed clear-review plan to Monarch."""
    if not yes:
        confirmed = typer.confirm(
            "This will clear Needs Review through the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_clear_review_plan(limit=limit))
    console.print(f"[green]Cleared review flag on:[/] {result['requestedCount']} transactions")


@app.command("apply-reviews")
def apply_reviews_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply the latest review plan without an interactive prompt."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many planned updates."),
    ] = None,
) -> None:
    """Apply the latest planned transaction updates to Monarch."""
    if not yes:
        confirmed = typer.confirm(
            "This will update Monarch transactions through the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_review_plan(limit=limit))
    console.print(f"[green]Applied review updates:[/] {result['requestedCount']}")


@app.command("llm-review")
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
            help="LLM backend: 'cli' (claude -p, no key needed) or 'api' (ANTHROPIC_API_KEY).",
        ),
    ] = "cli",
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Model override, e.g. claude-haiku-4-5-20251001, claude-sonnet-4-6.",
        ),
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
        typer.Option("--dry-run", help="Show scope without calling the LLM."),
    ] = False,
) -> None:
    """Run an LLM-assisted categorization pass on ambiguous needs-review transactions."""
    focus_categories = (
        {c.strip() for c in focus.split(",") if c.strip()} if focus else FOCUS_CATEGORIES
    )
    plan = build_llm_review_plan(
        focus_categories=focus_categories,
        dry_run=dry_run,
        backend=backend,
        model=model,
        skip_p2p=skip_p2p,
    )
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


@app.command("apply-llm-review")
def apply_llm_review_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply without an interactive prompt."),
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
) -> None:
    """Apply the latest LLM review plan to Monarch."""
    from .paths import review_latest_dir
    from .storage import read_json

    plan_path = review_latest_dir() / "llm-review-plan.json"
    if not plan_path.exists():
        console.print("[red]No LLM review plan found.[/] Run `monarch llm-review` first.")
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

    if not yes:
        confirmed = typer.confirm(f"Apply {len(updates)} LLM review updates to Monarch? Continue?")
        if not confirmed:
            raise typer.Abort()

    api_updates = [
        {
            "transactionId": u["transactionId"],
            "merchantName": u["merchantName"],
            "suggestedCategory": u["suggestedCategory"],
            "categoryId": u["categoryId"],
            "setNeedsReview": False,
        }
        for u in updates
        if u.get("categoryId")
    ]
    results = run_async(apply_transaction_updates(api_updates))
    console.print(f"[green]Applied LLM review updates:[/] {len(results)}")


@app.command("bulk-clear-reviews")
def bulk_clear_reviews_command(
    categories: Annotated[
        str,
        typer.Option(
            "--categories",
            help="Comma-separated category names to trust and clear review flag.",
        ),
    ] = "Transfer,Credit Card Payment,Buy Investment,Sell Investment,Interest",
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply without an interactive prompt."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many clears."),
    ] = None,
) -> None:
    """Build and optionally apply a clear-review plan for trusted categories."""
    trust_categories = {c.strip() for c in categories.split(",") if c.strip()}
    plan = build_clear_review_plan(sorted(trust_categories))
    planned_count = int(plan["summary"]["plannedUpdateCount"])
    apply_count = min(planned_count, limit) if limit is not None else planned_count
    if not apply_count:
        console.print("[yellow]No transactions to clear.[/]")
        raise typer.Exit(0)

    console.print(
        f"Clear-review plan written with [bold]{planned_count}[/] transactions "
        f"in: {', '.join(sorted(trust_categories))}"
    )
    if not yes:
        confirmed = typer.confirm(f"Apply {apply_count} planned review clears now?")
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_clear_review_plan(limit=limit))
    console.print(f"[green]Cleared review flag on:[/] {result['requestedCount']} transactions")


@app.command("tag-reimbursements")
def tag_reimbursements_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply without an interactive prompt."),
    ] = False,
    tag: Annotated[
        str,
        typer.Option("--tag", help="Tag name to apply."),
    ] = "expense-reimbursement",
) -> None:
    """Reclassify Expensify/Navan reimbursements to Other Income and tag them."""
    from .monarch_api import apply_transaction_updates
    from .paths import normalized_latest_dir
    from .storage import read_json

    bundle = read_json(normalized_latest_dir() / "bundle.json")
    txns = bundle.get("transactions") or []
    cats = bundle.get("categories") or []

    other_income_id = next((str(c["id"]) for c in cats if c.get("name") == "Other Income"), None)
    if not other_income_id:
        console.print("[red]Other Income category not found in bundle.[/]")
        raise typer.Exit(1)

    def is_reimbursement(t: dict) -> bool:
        name = (t.get("merchantName") or "").lower()
        amount = float(t.get("signedAmount") or 0)
        return ("expensify" in name or "navan" in name) and amount > 0

    reimbursements = [t for t in txns if is_reimbursement(t)]
    to_reclassify = [t for t in reimbursements if t.get("categoryName") != "Other Income"]
    to_tag = reimbursements

    console.print(
        f"Found [bold]{len(reimbursements)}[/] Expensify/Navan reimbursement transactions."
    )
    if to_reclassify:
        console.print(
            f"  [yellow]{len(to_reclassify)} need reclassification[/] (Paychecks → Other Income)"
        )
    console.print(f"  [cyan]{len(to_tag)} will be tagged[/] as [bold]{tag}[/]")

    if not yes:
        confirmed = typer.confirm("Apply reclassification and tagging via the unofficial API?")
        if not confirmed:
            raise typer.Abort()

    if to_reclassify:
        updates = [
            {
                "transactionId": t["id"],
                "merchantName": t["merchantName"],
                "suggestedCategory": "Other Income",
                "categoryId": other_income_id,
                "setNeedsReview": False,
            }
            for t in to_reclassify
        ]
        run_async(apply_transaction_updates(updates))
        console.print(f"[green]Reclassified {len(to_reclassify)} transactions → Other Income[/]")

    tag_ids = [str(t["id"]) for t in to_tag]
    run_async(tag_transactions(tag_ids, tag))
    console.print(f"[green]Tagged {len(to_tag)} transactions:[/] {tag}")


@app.command("portfolio")
def portfolio_command(
    top: Annotated[
        int,
        typer.Option("--top", help="Number of top holdings to display."),
    ] = 20,
    save: Annotated[
        bool,
        typer.Option("--save", help="Write holdings JSON to data/latest/portfolio-holdings.json."),
    ] = False,
) -> None:
    """Fetch portfolio holdings from Monarch and display allocation summary."""
    import json

    from .paths import normalized_latest_dir

    alloc = cast(dict[str, Any], run_async(fetch_portfolio_allocation()))
    total = float(alloc["totalValue"])
    by_type = cast(dict[str, float], alloc["byType"])
    holdings = cast(list[dict[str, Any]], alloc["holdings"])

    console.print(f"\n[bold]Portfolio: {alloc['count']} holdings, total ${total:,.0f}[/]\n")

    type_table = Table(title="By Asset Type")
    type_table.add_column("Type")
    type_table.add_column("Value", justify="right")
    type_table.add_column("%", justify="right")
    type_table.add_column("Count", justify="right")
    for t, val in sorted(by_type.items(), key=lambda x: -x[1]):
        count = sum(1 for h in holdings if (h.get("security") or {}).get("typeDisplay") == t)
        type_table.add_row(t, f"${val:>12,.0f}", f"{val / total * 100:.1f}%", str(count))
    console.print(type_table)

    top_table = Table(title=f"Top {top} Holdings")
    top_table.add_column("#", justify="right")
    top_table.add_column("Ticker")
    top_table.add_column("Name")
    top_table.add_column("Type")
    top_table.add_column("Value", justify="right")
    top_table.add_column("%", justify="right")
    for i, h in enumerate(holdings[:top], 1):
        sec = h.get("security") or {}
        val = float(h.get("totalValue") or 0)
        top_table.add_row(
            str(i),
            sec.get("ticker", "?"),
            (sec.get("name") or "?")[:40],
            sec.get("typeDisplay", "?"),
            f"${val:>12,.0f}",
            f"{val / total * 100:.2f}%",
        )
    console.print(top_table)

    if save:
        out = normalized_latest_dir() / "portfolio-holdings.json"
        out.write_text(json.dumps(alloc["holdings"], indent=2))
        console.print(f"[green]Saved:[/] {out}")


@app.command("suggest-rules")
def suggest_rules_command() -> None:
    """Analyze transaction history and suggest automation rules."""
    output = build_rule_suggestions()
    s = output["summary"]
    console.print(
        "[green]Rule suggestions written:[/] data/rules/latest/rule-suggestions.{json,csv,md} "
        f"({s['totalRules']} rules covering {s['totalMerchants']} merchants, "
        f"{s['pendingTotal']} needs-review transactions)"
    )
    console.print(
        "[cyan]Next:[/] review data/rules/latest/rule-suggestions.md, "
        "then run `monarch apply-rules`."
    )


@app.command("apply-rules")
def apply_rules_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Apply without an interactive prompt."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Apply at most this many updates."),
    ] = None,
    rules_path: Annotated[
        str | None,
        typer.Option(
            "--rules-path",
            help="Path to a rule-suggestions.json file (default: data/rules/latest).",
        ),
    ] = None,
    rule: Annotated[
        list[str] | None,
        typer.Option("--rule", help="Only apply this rule id or exact rule name (repeatable)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API."),
    ] = False,
) -> None:
    """Apply enabled rules from the latest rule suggestions to Monarch."""
    from .rules import build_apply_plan

    plan = build_apply_plan(rules_path, rule)
    updates = plan["updates"]
    if limit is not None:
        updates = updates[:limit]

    if not updates:
        console.print(
            "[yellow]No updates to apply.[/] "
            "Check that rules are enabled and have matching transactions."
        )
        raise typer.Exit(0)

    if dry_run:
        table = Table(title=f"Dry run — {len(updates)} updates")
        table.add_column("Merchant")
        table.add_column("Current Category")
        table.add_column("New Category")
        table.add_column("Clear Review")
        table.add_column("Rule")
        for u in updates[:50]:
            table.add_row(
                u["merchantName"],
                u["currentCategory"],
                u["suggestedCategory"] or "(unchanged)",
                str(u["clearNeedsReview"]),
                u["ruleName"],
            )
        console.print(table)
        if len(updates) > 50:
            console.print(f"[dim]… and {len(updates) - 50} more[/]")
        return

    if not yes:
        confirmed = typer.confirm(
            f"Apply {len(updates)} rule-based updates to Monarch via the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_rules_plan(rules_path=rules_path, limit=limit, rules_filter=rule))
    console.print(f"[green]Applied rule updates:[/] {result['appliedCount']} transactions")


@app.command("list-monarch-rules")
def list_monarch_rules_command() -> None:
    """List all transaction rules currently stored in Monarch."""
    rules = run_async(fetch_transaction_rules())
    if not rules:
        console.print("[yellow]No rules found in Monarch.[/]")
        return

    table = Table(title=f"Monarch Rules ({len(rules)} total)", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("ID", style="dim")
    table.add_column("Criteria")
    table.add_column("Set Category")
    table.add_column("Review")
    table.add_column("Last Applied")

    for rule in rules:
        criteria_parts: list[str] = []
        for field, label in [
            ("merchantCriteria", "merchant"),
            ("merchantNameCriteria", "merchantName"),
            ("originalStatementCriteria", "statement"),
        ]:
            for c in rule.get(field) or []:
                criteria_parts.append(f'{label} {c["operator"]} "{c["value"]}"')
        if rule.get("amountCriteria"):
            ac = rule["amountCriteria"]
            criteria_parts.append(f"amount {ac['operator']} {ac.get('value')}")
        for acct in rule.get("accounts") or []:
            criteria_parts.append(f"account={acct['displayName']}")

        cat = rule.get("setCategoryAction")
        cat_name = cat["name"] if cat else ""
        review = rule.get("reviewStatusAction") or ""
        last = (rule.get("lastAppliedAt") or "never")[:10]
        n_applied = rule.get("recentApplicationCount") or 0
        last_display = f"{last} (×{n_applied})" if last != "never" else "never"

        table.add_row(
            str(rule["order"]),
            rule["id"],
            "\n".join(criteria_parts) or "(no criteria)",
            cat_name,
            review,
            last_display,
        )

    console.print(table)


@app.command("push-rule")
def push_rule_command(
    rule_id: Annotated[
        str,
        typer.Argument(help="Local rule ID from rule-suggestions.json to push to Monarch."),
    ],
    rules_path: Annotated[
        str | None,
        typer.Option(
            "--rules-path",
            help="Path to rule-suggestions.json (default: data/rules/latest).",
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Create without confirmation prompt."),
    ] = False,
) -> None:
    """Push a single local rule suggestion into Monarch as a live transaction rule."""
    from .rules import load_rule_suggestions

    rules = load_rule_suggestions(rules_path)
    match = next((r for r in rules if r["id"] == rule_id or r["name"] == rule_id), None)
    if not match:
        console.print(f"[red]Rule not found:[/] {rule_id}")
        raise typer.Exit(1)

    if not match.get("enabled", True):
        console.print(f"[yellow]Rule is disabled:[/] {match['name']}")
        raise typer.Exit(1)

    action = match.get("action", {})
    match_spec = match.get("match", {})
    merchant_names = match_spec.get("merchantNames") or []
    merchant_pattern = match_spec.get("merchantPattern")

    console.print(f"Rule: [bold]{match['name']}[/]")
    console.print(f"  Category: {action.get('setCategory')}")
    console.print(f"  Review action: {'reviewed' if action.get('clearNeedsReview') else '(none)'}")
    if merchant_names:
        console.print(f"  Merchants ({len(merchant_names)}): {', '.join(merchant_names[:5])}")
        if len(merchant_names) > 5:
            console.print(f"    … and {len(merchant_names) - 5} more")
    if merchant_pattern:
        console.print(f"  Pattern (contains): {merchant_pattern}")

    if not yes:
        confirmed = typer.confirm("Push this rule to Monarch?")
        if not confirmed:
            raise typer.Abort()

    async def _push() -> dict[str, object]:
        from .monarch_api import create_monarch_client

        client = await create_monarch_client()

        # Resolve category name → Monarch numeric ID via live API lookup
        category_id: str | None = None
        category_name = action.get("setCategory")
        if category_name:
            cats_result = await client.get_transaction_categories()
            cats = cats_result.get("categories") or []
            cat = next((c for c in cats if c.get("name") == category_name), None)
            if not cat:
                raise RuntimeError(
                    f"Category '{category_name}' not found in Monarch. "
                    "Check the name matches exactly."
                )
            category_id = str(cat["id"])

        monarch_input: dict[str, object] = {"applyToExistingTransactions": False}

        if category_id:
            monarch_input["setCategoryAction"] = category_id

        if action.get("clearNeedsReview"):
            monarch_input["reviewStatusAction"] = "reviewed"

        if merchant_names:
            monarch_input["merchantNameCriteria"] = [
                {"operator": "eq", "value": name.lower()} for name in merchant_names
            ]
        elif merchant_pattern:
            monarch_input["merchantNameCriteria"] = [
                {"operator": "contains", "value": merchant_pattern.lower()}
            ]

        return await client.create_transaction_rule(monarch_input)

    result = run_async(_push())
    errors = result.get("errors")
    if errors:
        console.print(f"[red]API error:[/] {errors}")
        raise typer.Exit(1)

    new_rule = result.get("transactionRule", {})
    console.print(
        f"[green]Created Monarch rule:[/] {new_rule.get('id')} (order {new_rule.get('order')})"
    )


@app.command("delete-monarch-rule")
def delete_monarch_rule_command(
    rule_id: Annotated[
        str,
        typer.Argument(help="Monarch rule ID to delete (from list-monarch-rules)."),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Delete without confirmation prompt."),
    ] = False,
) -> None:
    """Delete a transaction rule from Monarch by its ID."""
    if not yes:
        confirmed = typer.confirm(f"Delete Monarch rule {rule_id}?")
        if not confirmed:
            raise typer.Abort()

    result = run_async(delete_monarch_rule(rule_id))
    errors = result.get("errors")
    if errors:
        console.print(f"[red]API error:[/] {errors}")
        raise typer.Exit(1)

    console.print(f"[green]Deleted rule:[/] {rule_id}")


def run_async(coro: Coroutine[object, object, T]) -> T:
    try:
        return asyncio.run(coro)
    except Exception as error:
        message = str(error)
        if "429" in message or "Too Many Requests" in message:
            console.print(
                "[red]Monarch login is rate-limited.[/] Wait before retrying, or set "
                "`MONARCH_SESSION_TOKEN` / `MONARCH_SESSION_FILE` so the CLI can reuse a session."
            )
            raise typer.Exit(1) from error
        console.print(f"[red]Command failed:[/] {message}")
        raise typer.Exit(1) from error
