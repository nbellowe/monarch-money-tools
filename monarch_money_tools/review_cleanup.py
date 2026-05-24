"""Interactive accept/reject/skip loop for taxonomy cleanup candidates."""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel

from .paths import cleanup_latest_dir
from .storage import read_json
from .taxonomy_cleanup import load_decisions, save_decision

JsonObject = dict[str, Any]
console = Console()

VALID_KEYS = {"a", "r", "s", "q"}


def _read_char() -> str:
    import termios
    import tty

    file_descriptor = sys.stdin.fileno()
    old_settings = termios.tcgetattr(file_descriptor)
    try:
        tty.setraw(file_descriptor)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_settings)


def run_review_cleanup() -> None:
    plan_path = cleanup_latest_dir() / "cleanup-plan.json"
    if not plan_path.exists():
        console.print("[red]No cleanup plan found.[/] Run `monarch cleanup-plan` first.")
        return

    plan = read_json(plan_path)
    candidates = [
        candidate
        for candidate in (plan.get("candidates") or [])
        if not candidate.get("requiresNewCategory")
    ]
    if not candidates:
        console.print("[yellow]No reviewable candidates.[/]")
        return

    decisions = load_decisions()
    pending = [candidate for candidate in candidates if candidate["transactionId"] not in decisions]

    if not pending:
        console.print(
            f"[green]All {len(candidates)} candidates already reviewed.[/] "
            "Run `monarch apply-cleanup` to apply accepted ones."
        )
        return

    total = len(candidates)
    reviewed_before = sum(1 for candidate in candidates if candidate["transactionId"] in decisions)

    for index, candidate in enumerate(pending, start=reviewed_before + 1):
        transaction_id = candidate["transactionId"]
        merchant = candidate["merchantName"]
        current = candidate["currentCategory"]
        suggested = candidate["suggestedCategory"]
        source = candidate.get("source", "")
        date = candidate.get("date", "?")
        amount = float(candidate.get("amount", 0))

        panel_content = (
            f"[bold]{merchant}[/] -> [green]{suggested}[/]\n"
            f"  Current:   [yellow]{current}[/]\n"
            f"  Sample:    {date}  ${abs(amount):,.2f}\n"
            f"  Source:    {source}\n\n"
            f"  [bold](a)[/]ccept  [bold](r)[/]eject  "
            f"[bold](s)[/]kip  [bold](q)[/]uit"
        )
        console.print(Panel(panel_content, title=f"[{index}/{total}]"))

        while True:
            key = _read_char()
            if key in VALID_KEYS:
                break

        console.print()
        if key == "q":
            console.print("[dim]Saved progress. Resume with `monarch review-cleanup`.[/]")
            return
        if key == "a":
            save_decision(transaction_id, "accepted")
            console.print(f"[green]Accepted:[/] {merchant} -> {suggested}")
        elif key == "r":
            save_decision(transaction_id, "rejected")
            console.print(f"[red]Rejected:[/] {merchant}")
        elif key == "s":
            save_decision(transaction_id, "skipped")
            console.print(f"[dim]Skipped:[/] {merchant}")

    accepted = sum(1 for decision in load_decisions().values() if decision == "accepted")
    console.print(
        f"\n[green]Review complete.[/] {accepted} accepted. Run `monarch apply-cleanup` to apply."
    )
