from __future__ import annotations

from typing import Annotated, Any, cast

import typer
from rich.table import Table

from ..monarch_api import delete_monarch_rule, fetch_transaction_rules
from ..paths import rules_revert_dir
from ..revert import build_revert_receipt, execute_revert, find_latest_receipt, write_revert_receipt
from ..rules import (
    build_apply_plan,
    build_push_rule_payload,
    build_rule_suggestions,
    load_rule_suggestions,
)
from ..storage import read_json
from ._utils import _format_amount, console, print_dry_run_table, run_async

rules_app = typer.Typer(help="Rule suggestion and Monarch rule commands.", no_args_is_help=True)


@rules_app.command("suggest")
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
        "then run `monarch rules apply`."
    )


@rules_app.command("apply")
def apply_rules_command(
    yes: Annotated[
        bool, typer.Option("--yes", help="Apply without an interactive prompt.")
    ] = False,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help="Apply at most this many updates.")
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
        typer.Option(
            "--dry-run",
            help="Show what would be applied without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Apply rule suggestions to existing Monarch transactions."""
    from ..rules import apply_rules_plan

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
        print_dry_run_table(
            f"Dry run — {len(updates)} updates",
            updates,
            [
                ("Merchant", None),
                ("Amount", "right"),
                ("Current Category", None),
                ("New Category", None),
                ("Clear Review", None),
                ("Rule", None),
            ],
            lambda u: (
                u["merchantName"],
                _format_amount(u.get("amount")),
                u["currentCategory"],
                u["suggestedCategory"] or "(unchanged)",
                str(u["clearNeedsReview"]),
                u["ruleName"],
            ),
        )
        return

    if not yes:
        confirmed = typer.confirm(
            f"Apply {len(updates)} rule-based updates to Monarch via the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_rules_plan(rules_path=rules_path, limit=limit, rules_filter=rule))
    console.print(f"[green]Applied rule updates:[/] {result['appliedCount']} transactions")


@rules_app.command("list")
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


@rules_app.command("push")
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
    yes: Annotated[bool, typer.Option("--yes", help="Create without confirmation prompt.")] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show the Monarch rule that would be created without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Push a single local rule suggestion into Monarch as a live transaction rule."""
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

    if dry_run:
        console.print("[cyan]Dry run:[/] no Monarch rule was created.")
        return

    if not yes:
        confirmed = typer.confirm("Push this rule to Monarch?")
        if not confirmed:
            raise typer.Abort()

    async def _push() -> dict[str, object]:
        from ..monarch_api import create_monarch_client

        client = await create_monarch_client()
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

        payload = build_push_rule_payload(match, category_id)
        return await client.create_transaction_rule(payload)

    result = run_async(_push())
    errors = result.get("errors")
    if errors:
        console.print(f"[red]API error:[/] {errors}")
        raise typer.Exit(1)

    new_rule = cast(dict[str, Any], result.get("transactionRule") or {})
    console.print(
        f"[green]Created Monarch rule:[/] {new_rule.get('id')} (order {new_rule.get('order')})"
    )
    receipt_op: dict[str, object] = {
        "type": "create_rule",
        "entityId": str(new_rule.get("id", "")),
        "ruleName": match["name"],
        "before": None,
        "after": {"monarchRuleId": str(new_rule.get("id", ""))},
    }
    receipt = build_revert_receipt("monarch rules push", [receipt_op])
    write_revert_receipt(rules_revert_dir(), receipt)


@rules_app.command("delete")
def delete_monarch_rule_command(
    rule_id: Annotated[
        str,
        typer.Argument(help="Monarch rule ID to delete (from `monarch rules list`)."),
    ],
    yes: Annotated[bool, typer.Option("--yes", help="Delete without confirmation prompt.")] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show which Monarch rule would be deleted without calling the API.",
            envvar="MONARCH_DRY_RUN",
        ),
    ] = False,
) -> None:
    """Delete a transaction rule from Monarch by its ID."""
    if dry_run:
        console.print(f"[cyan]Dry run:[/] would delete Monarch rule {rule_id}.")
        return

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


@rules_app.command("revert")
def revert_rules_command(
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
    """Revert the latest rules apply or push using its revert receipt."""
    from pathlib import Path

    receipt_path = Path(receipt) if receipt else find_latest_receipt(rules_revert_dir())
    if not receipt_path:
        console.print(
            "[red]No revert receipt found.[/] "
            "Run `monarch rules apply` or `monarch rules push` first."
        )
        raise typer.Exit(1)

    receipt_data = read_json(receipt_path)
    ops = list(receipt_data.get("operations") or [])

    if not ops:
        console.print("[yellow]No revertable operations in this receipt.[/]")
        raise typer.Exit(0)

    txn_ops = [op for op in ops if op.get("type") == "update_transaction"]
    rule_ops = [op for op in ops if op.get("type") == "create_rule"]

    console.print(f"Using receipt: [dim]{receipt_path}[/] ({len(ops)} operations)")

    if txn_ops:
        print_dry_run_table(
            f"{'Dry run - ' if dry_run else ''}Revert {len(txn_ops)} transaction updates",
            txn_ops,
            [
                ("Merchant", None),
                ("Current Category", None),
                ("Restoring Category", None),
                ("Review", None),
            ],
            lambda op: (
                op.get("merchantName", ""),
                (op.get("after") or {}).get("categoryName", ""),
                (op.get("before") or {}).get("categoryName", ""),
                str((op.get("before") or {}).get("needsReview", "")),
            ),
        )

    if rule_ops:
        print_dry_run_table(
            f"{'Dry run - ' if dry_run else ''}Delete {len(rule_ops)} Monarch rules",
            rule_ops,
            [("Rule Name", None), ("Monarch Rule ID", None)],
            lambda op: (op.get("ruleName", ""), op.get("entityId", "")),
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
