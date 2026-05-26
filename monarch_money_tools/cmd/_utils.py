from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, NoReturn, TypeVar

import typer
from rich.console import Console
from rich.table import Table

T = TypeVar("T")

console = Console()


def _format_amount(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return str(value or "")
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def print_dry_run_table(
    title: str,
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str | None]],
    row_values: Callable[[dict[str, Any]], tuple[str, ...]],
    *,
    limit: int = 50,
    width: int | None = None,
    console: Console = console,
) -> None:
    kwargs: dict[str, Any] = {"title": title}
    if width is not None:
        kwargs["width"] = width
    table = Table(**kwargs)
    for col_name, justify in columns:
        table.add_column(col_name, justify=justify)
    for row in rows[:limit]:
        table.add_row(*row_values(row))
    console.print(table)
    if len(rows) > limit:
        console.print(f"[dim]... and {len(rows) - limit} more[/]")


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


def exit_with_file_error(error: FileNotFoundError) -> NoReturn:
    console.print(f"[red]Missing input:[/] {error}")
    raise typer.Exit(1) from None
