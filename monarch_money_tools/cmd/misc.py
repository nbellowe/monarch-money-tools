from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ._utils import console, run_async


def init_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Non-interactive: use existing env values, skip prompts."),
    ] = False,
) -> None:
    """Interactive setup wizard: credentials, connection test, taxonomy check, profile, doctor."""
    from ..init_wizard import run_init_wizard

    run_init_wizard(yes=yes)


def init_profile_command(
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing profile.yaml without prompting."),
    ] = False,
) -> None:
    """Generate a commented starter profile.yaml for retirement simulation."""
    from ..profile import PROFILE_TEMPLATE

    dest = Path("profile.yaml")
    if dest.exists() and not force:
        confirmed = typer.confirm("profile.yaml already exists. Overwrite?")
        if not confirmed:
            raise typer.Abort()

    dest.write_text(PROFILE_TEMPLATE)
    console.print(f"[green]Created:[/] {dest}")
    console.print(
        "[cyan]Edit it with your details, then visit "
        "https://nbellowe.github.io/retirement-simulator "
        "and drag in your profile.[/]"
    )


def portfolio_command(
    top: Annotated[
        int,
        typer.Option("--top", help="Number of top holdings to display."),
    ] = 20,
    save: Annotated[
        bool,
        typer.Option(
            "--save",
            help="Write holdings JSON to data/normalized/latest/portfolio-holdings.json.",
        ),
    ] = False,
) -> None:
    """Fetch portfolio holdings from Monarch and display allocation summary."""
    import json
    from typing import Any, cast

    from rich.table import Table

    from ..monarch_api import fetch_portfolio_allocation
    from ..paths import normalized_latest_dir

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
