# Refactor: Complexity & Duplication Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate duplicated utilities, merge the analyzer thin-wrapper, split cli.py (1303 lines) into focused command modules, and extract business logic from command handlers.

**Architecture:** Four sequential sections: (1) consolidate shared utilities into storage.py, (2) merge analyzer.py into analysis.py, (3) split cli.py into cmd/ sub-modules, (4) extract filtering/payload logic into domain modules. Each section leaves all tests green before the next begins.

**Tech Stack:** Python 3.11+, Typer, Rich, uv/pytest

---

## File Map

| File | Action |
|---|---|
| `monarch_money_tools/storage.py` | Add `now_iso`, `round2`, `load_bundle` |
| `monarch_money_tools/analysis.py` | Receive `run_analyze`; remove `now_iso`, `round2` |
| `monarch_money_tools/analyzer.py` | **Delete** |
| `monarch_money_tools/review.py` | Remove `now_iso`, `round2`; fix apply signatures |
| `monarch_money_tools/rules.py` | Remove inline `now_iso`; add `build_push_rule_payload` |
| `monarch_money_tools/taxonomy_cleanup.py` | Remove `_now_iso`; add `filter_cleanup_candidates` |
| `monarch_money_tools/llm_review.py` | Remove `_now_iso` |
| `monarch_money_tools/reporter.py` | Remove `JsonObject` local def |
| `monarch_money_tools/exporter.py` | Remove `iso_datetime`; use `now_iso` |
| `monarch_money_tools/cli.py` | Slim to ~50 lines: app skeleton + flat shortcuts |
| `monarch_money_tools/cmd/__init__.py` | **New** (empty) |
| `monarch_money_tools/cmd/_utils.py` | **New**: console, run_async, exit_with_file_error, _format_amount, print_dry_run_table |
| `monarch_money_tools/cmd/data.py` | **New**: data_app + all data commands + resolve_run_bundle |
| `monarch_money_tools/cmd/review.py` | **New**: review_app + all review commands |
| `monarch_money_tools/cmd/cleanup.py` | **New**: cleanup_app + cleanup commands |
| `monarch_money_tools/cmd/rules.py` | **New**: rules_app + rules commands |
| `monarch_money_tools/cmd/misc.py` | **New**: init-profile, portfolio commands |
| `tests/test_storage.py` | Add tests for new storage utilities |
| `tests/test_cmd_utils.py` | **New**: tests for print_dry_run_table |

---

## Task 1: Add shared utilities to storage.py

**Files:**
- Modify: `monarch_money_tools/storage.py`
- Modify: `tests/test_storage.py` (add to existing file, or create if absent)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_storage.py` (or append if it exists):

```python
import pytest
from monarch_money_tools.storage import JsonObject, load_bundle, now_iso, round2, write_json


def test_json_object_importable() -> None:
    obj: JsonObject = {"key": "value"}
    assert obj["key"] == "value"


def test_now_iso_format() -> None:
    result = now_iso()
    assert result.endswith("Z")
    assert "T" in result
    assert "+" not in result


def test_round2_rounds_to_two_places() -> None:
    assert round2(0.956) == 0.96
    assert round2(0.554) == 0.55
    assert round2(1.0) == 1.0


def test_load_bundle_raises_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="monarch pull"):
        load_bundle()


def test_load_bundle_returns_parsed_data(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    bundle = {"transactions": [{"id": "t1"}], "categories": []}
    write_json(tmp_path / "data/normalized/latest/bundle.json", bundle)
    result = load_bundle()
    assert result["transactions"][0]["id"] == "t1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_storage.py -v 2>&1 | tail -20
```

Expected: `FAILED` — `now_iso`, `round2`, `load_bundle` not yet in storage.

- [ ] **Step 3: Add utilities to storage.py**

Add these after the existing imports in `monarch_money_tools/storage.py` (note: `JsonObject` is already defined there at line 10 — do not duplicate it):

```python
from .paths import normalized_latest_dir


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def round2(value: float) -> float:
    return round(value * 100) / 100


def load_bundle() -> Any:
    path = normalized_latest_dir() / "bundle.json"
    if not path.exists():
        raise FileNotFoundError(
            "No normalized bundle found. Run `monarch pull` or `monarch import <csv>` first."
        )
    return read_json(path)
```

Also add `UTC` to the existing datetime import at the top of storage.py:
```python
from datetime import UTC, datetime
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_storage.py -v 2>&1 | tail -20
```

Expected: all new tests PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all 71+ tests pass.

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/storage.py tests/test_storage.py
git commit -m "refactor: add now_iso, round2, load_bundle to storage"
```

---

## Task 2: Remove duplicate utility definitions from all modules

**Files:** Modify analysis.py, review.py, rules.py, taxonomy_cleanup.py, llm_review.py, exporter.py, reporter.py

For each file: remove the local definition and add/update the import from storage.

- [ ] **Step 1: Update analysis.py**

Remove these from `analysis.py` (they appear near the bottom):
```python
def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

def round2(value: float) -> float:
    return round(value * 100) / 100
```

Change the import block at the top to add storage imports:
```python
from .storage import JsonObject, now_iso, round2
```

Remove `UTC` and `datetime` from the import if no longer used (keep `datetime` for `is_recent`; keep `UTC` for `is_recent`).

- [ ] **Step 2: Update review.py**

Remove from `review.py`:
```python
def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

def round2(value: float) -> float:
    return round(value * 100) / 100
```

Add to imports:
```python
from .storage import JsonObject, now_iso, read_json, reset_dir, round2, write_csv, write_json, write_text
```

Remove `JsonObject = dict[str, Any]` local definition and remove `from typing import Any` if unused.

- [ ] **Step 3: Update rules.py**

`rules.py` doesn't define `now_iso()` as a function — it inlines the pattern twice. Replace both occurrences:

In `build_rule_suggestions` replace:
```python
generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
```
with:
```python
generated_at = now_iso()
```

In `build_apply_plan` replace:
```python
"generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
```
with:
```python
"generatedAt": now_iso(),
```

Remove `JsonObject = dict[str, Any]` local definition. Update imports:
```python
from .storage import JsonObject, now_iso, read_json, reset_dir, write_csv, write_json, write_text
```

Remove `from datetime import UTC, datetime` if no longer used after removing inline patterns.

- [ ] **Step 4: Update taxonomy_cleanup.py**

Remove:
```python
def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
```

Replace all calls `_now_iso()` → `now_iso()`.

Remove `JsonObject = dict[str, Any]` local definition.

Update imports:
```python
from .storage import JsonObject, now_iso, read_json, reset_dir, write_csv, write_json, write_text
```

Remove `from datetime import UTC, datetime` if no longer used.

- [ ] **Step 5: Update llm_review.py**

Remove:
```python
def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
```

Replace call `_now_iso()` → `now_iso()`.

Remove `JsonObject = dict[str, Any]` local definition.

Update imports to include:
```python
from .storage import JsonObject, now_iso, read_json, write_csv, write_json, write_text
```

Remove `from datetime import UTC, datetime` if no longer used.

- [ ] **Step 6: Update exporter.py**

Remove:
```python
def iso_datetime() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
```

Replace its single call site (where `exported_at = iso_datetime()` appears) with:
```python
exported_at = now_iso()
```

Add to imports:
```python
from .storage import iso_date, latest_csv_path, now_iso, reset_dir, timestamp_slug, write_csv, write_json
```

- [ ] **Step 7: Update reporter.py**

Remove `JsonObject = dict[str, Any]` local definition and `from typing import Any`.

Add to imports:
```python
from .storage import JsonObject
```

- [ ] **Step 8: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add monarch_money_tools/analysis.py monarch_money_tools/review.py monarch_money_tools/rules.py \
  monarch_money_tools/taxonomy_cleanup.py monarch_money_tools/llm_review.py \
  monarch_money_tools/exporter.py monarch_money_tools/reporter.py
git commit -m "refactor: import now_iso, round2, JsonObject from storage everywhere"
```

---

## Task 3: Replace manual bundle loading with load_bundle()

**Files:** Modify analyzer.py, review.py, rules.py, taxonomy_cleanup.py, llm_review.py

Each location currently does:
```python
bundle_path = normalized_latest_dir() / "bundle.json"
if not bundle_path.exists():
    raise FileNotFoundError("No normalized bundle found. ...")
bundle = read_json(bundle_path)
```

Replace with `bundle = load_bundle()` and remove the path/existence check. Remove unused `normalized_latest_dir` imports where they're no longer needed after the replacement (but keep them if used elsewhere in the same file).

- [ ] **Step 1: Update analyzer.py**

In `run_analyze`, replace:
```python
bundle_path = normalized_latest_dir() / "bundle.json"
if not bundle_path.exists():
    raise FileNotFoundError(
        "No normalized bundle found. Run `monarch pull` or `monarch import <csv>` first."
    )
prepared = prepare_analysis(read_json(bundle_path))
```
with:
```python
prepared = prepare_analysis(load_bundle())
```

Add `load_bundle` to imports from storage. Remove `normalized_latest_dir` from paths import if no longer used.

- [ ] **Step 2: Update review.py — build_clear_review_plan**

Replace:
```python
bundle_path = normalized_latest_dir() / "bundle.json"
if not bundle_path.exists():
    raise FileNotFoundError(
        "No normalized bundle found. Run `monarch pull` or `monarch import <csv>` first."
    )
bundle = read_json(bundle_path)
```
with:
```python
bundle = load_bundle()
```

- [ ] **Step 3: Update review.py — build_review_plan**

Same replacement as Step 2 (there's a second identical block in `build_review_plan`).

Remove `normalized_latest_dir` from `review.py`'s paths import if no longer used elsewhere in the file.

Add `load_bundle` to the storage import line.

- [ ] **Step 4: Update rules.py — build_rule_suggestions and build_apply_plan**

`build_rule_suggestions` has:
```python
bundle_path = normalized_latest_dir() / "bundle.json"
if not bundle_path.exists():
    raise FileNotFoundError(
        "No normalized bundle found. Run `monarch pull` or `monarch import` first."
    )
bundle = read_json(bundle_path)
```
Replace with `bundle = load_bundle()`.

`build_apply_plan` has the same pattern. Replace with `bundle = load_bundle()`.

Add `load_bundle` to storage import. Remove `normalized_latest_dir` from paths import (it's no longer used in rules.py after this).

- [ ] **Step 5: Update taxonomy_cleanup.py**

Replace the bundle-load block in `build_taxonomy_cleanup_plan`:
```python
bundle_path = normalized_latest_dir() / "bundle.json"
if not bundle_path.exists():
    raise FileNotFoundError(
        "No normalized bundle. Run `monarch pull` or `monarch import` first."
    )
bundle = read_json(bundle_path)
```
with:
```python
bundle = load_bundle()
```

Add `load_bundle` to storage import. Remove `normalized_latest_dir` from paths import if no longer used.

- [ ] **Step 6: Update llm_review.py**

`build_llm_review_plan` currently reads the bundle directly:
```python
bundle = read_json(normalized_latest_dir() / "bundle.json")
```
Replace with `bundle = load_bundle()`. Add `load_bundle` to storage import. Remove `normalized_latest_dir` from paths import if no longer used.

- [ ] **Step 7: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add monarch_money_tools/analyzer.py monarch_money_tools/review.py monarch_money_tools/rules.py \
  monarch_money_tools/taxonomy_cleanup.py monarch_money_tools/llm_review.py
git commit -m "refactor: replace manual bundle loading with load_bundle()"
```

---

## Task 4: Merge analyzer.py into analysis.py

**Files:**
- Modify: `monarch_money_tools/analysis.py`
- Delete: `monarch_money_tools/analyzer.py`
- Modify: `monarch_money_tools/cli.py` (one import line)

- [ ] **Step 1: Move run_analyze to analysis.py**

Append to the bottom of `monarch_money_tools/analysis.py`:

```python
def run_analyze() -> dict[str, Any]:
    prepared = prepare_analysis(load_bundle())
    rule_opportunities = prepared["heuristicRuleOpportunities"]
    analysis = {
        "generatedAt": prepared["generatedAt"],
        "summary": {
            **prepared["summary"],
            "ruleOpportunityCount": len(rule_opportunities),
        },
        "ruleGeneration": {
            "mode": "heuristic",
            "candidateCount": len(prepared["ruleCandidates"]),
            "batchCount": 0,
            "warning": "AI rule generation has not been ported to the Python CLI yet.",
        },
        "miscategorizations": prepared["miscategorizations"],
        "ownerReviews": prepared["ownerReviews"],
        "ruleOpportunities": rule_opportunities,
    }

    reset_dir(analysis_latest_dir())
    write_json(analysis_latest_dir() / "analysis.json", analysis)
    write_json(analysis_latest_dir() / "summary.json", analysis["summary"])
    write_json(analysis_latest_dir() / "rule-candidates.json", prepared["ruleCandidates"])
    return analysis
```

Add to `analysis.py` imports:
```python
from .storage import load_bundle, now_iso, read_json, reset_dir, round2, write_json
```
(Adjust the existing storage import line — don't duplicate.)

Also add `analysis_latest_dir` to the paths import if not already there:
```python
from .paths import analysis_latest_dir
```

- [ ] **Step 2: Update cli.py import**

In `monarch_money_tools/cli.py`, change:
```python
from .analyzer import run_analyze
```
to:
```python
from .analysis import run_analyze
```

- [ ] **Step 3: Delete analyzer.py**

```bash
rm monarch_money_tools/analyzer.py
```

- [ ] **Step 4: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add monarch_money_tools/analysis.py monarch_money_tools/cli.py
git rm monarch_money_tools/analyzer.py
git commit -m "refactor: merge analyzer.py into analysis.py"
```

---

## Task 5: Create cmd package with shared utilities

**Files:**
- Create: `monarch_money_tools/cmd/__init__.py`
- Create: `monarch_money_tools/cmd/_utils.py`
- Create: `tests/test_cmd_utils.py`

- [ ] **Step 1: Write failing test for print_dry_run_table**

Create `tests/test_cmd_utils.py`:

```python
from __future__ import annotations

from io import StringIO

from rich.console import Console

from monarch_money_tools.cmd._utils import print_dry_run_table


def _capture(fn) -> str:
    buf = StringIO()
    console = Console(file=buf, width=200)
    fn(console)
    return buf.getvalue()


def test_print_dry_run_table_shows_all_rows() -> None:
    rows = [
        {"merchant": "Coffee", "amount": "-$5.00", "cat": "Dining"},
        {"merchant": "Gas", "amount": "-$40.00", "cat": "Auto"},
    ]
    columns = [("Merchant", None), ("Amount", "right"), ("Category", None)]

    output = _capture(
        lambda c: print_dry_run_table(
            "Test Title",
            rows,
            columns,
            lambda r: (r["merchant"], r["amount"], r["cat"]),
            console=c,
        )
    )

    assert "Coffee" in output
    assert "Gas" in output
    assert "Test Title" in output


def test_print_dry_run_table_truncates_at_limit() -> None:
    rows = [{"merchant": f"Merchant{i}", "amount": f"-${i}.00"} for i in range(10)]
    columns = [("Merchant", None), ("Amount", "right")]

    output = _capture(
        lambda c: print_dry_run_table(
            "Truncation Test",
            rows,
            columns,
            lambda r: (r["merchant"], r["amount"]),
            console=c,
            limit=3,
        )
    )

    assert "Merchant0" in output
    assert "Merchant2" in output
    assert "Merchant3" not in output
    assert "7 more" in output
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_cmd_utils.py -v 2>&1 | tail -10
```

Expected: ImportError — `cmd._utils` doesn't exist yet.

- [ ] **Step 3: Create cmd/__init__.py**

```bash
mkdir -p monarch_money_tools/cmd
touch monarch_money_tools/cmd/__init__.py
```

- [ ] **Step 4: Create cmd/_utils.py**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_cmd_utils.py uv run pytest --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/cmd/ tests/test_cmd_utils.py
git commit -m "refactor: add cmd package with shared CLI utilities"
```

---

## Task 6: Create cmd/data.py

**Files:**
- Create: `monarch_money_tools/cmd/data.py`

- [ ] **Step 1: Create cmd/data.py**

```python
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
from ._utils import _format_amount, console, exit_with_file_error, run_async

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
```

- [ ] **Step 2: Run full suite (cmd/data.py is not yet wired into cli.py)**

```bash
uv run pytest --tb=short -q
```

Expected: all existing tests still pass (data.py is not yet imported anywhere).

- [ ] **Step 3: Commit**

```bash
git add monarch_money_tools/cmd/data.py
git commit -m "refactor: add cmd/data.py with data sub-commands"
```

---

## Task 7: Fix apply function signatures in review.py

**Files:** Modify `monarch_money_tools/review.py`

The current `apply_review_plan(limit)` and `apply_clear_review_plan(limit)` each read the plan file from disk. After this task they accept pre-filtered updates directly — the CLI will do the filtering before calling.

- [ ] **Step 1: Write failing test**

Add to `tests/test_review.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from monarch_money_tools.review import apply_clear_review_plan, apply_review_plan


def test_apply_review_plan_accepts_updates_directly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    updates = [{"transactionId": "t1", "merchantName": "Coffee", "categoryId": "c1"}]
    with (
        patch("monarch_money_tools.review.apply_transaction_updates", new_callable=AsyncMock) as mock_apply,
        patch("monarch_money_tools.review.write_json"),
    ):
        mock_apply.return_value = [{"id": "t1"}]
        result = asyncio.run(apply_review_plan(updates))
    mock_apply.assert_called_once_with(updates)
    assert result["requestedCount"] == 1


def test_apply_clear_review_plan_accepts_updates_directly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    updates = [{"transactionId": "t2", "merchantName": "Gas", "categoryId": ""}]
    with (
        patch("monarch_money_tools.review.apply_transaction_updates", new_callable=AsyncMock) as mock_apply,
        patch("monarch_money_tools.review.write_json"),
    ):
        mock_apply.return_value = [{"id": "t2"}]
        result = asyncio.run(apply_clear_review_plan(updates))
    mock_apply.assert_called_once_with(updates)
    assert result["requestedCount"] == 1
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_review.py -k "apply" -v 2>&1 | tail -15
```

Expected: FAIL — current signatures don't accept `updates` positionally.

- [ ] **Step 3: Update apply_review_plan in review.py**

Replace:
```python
async def apply_review_plan(limit: int | None = None) -> JsonObject:
    plan_path = review_latest_dir() / "review-plan.json"
    if not plan_path.exists():
        raise FileNotFoundError("No review plan found. Run `monarch review plan` first.")

    plan = read_json(plan_path)
    updates = list(plan.get("updates") or [])
    if limit is not None:
        updates = updates[:limit]
    results = await apply_transaction_updates(updates)
    applied = {
        "appliedAt": now_iso(),
        "requestedCount": len(updates),
        "results": results,
    }
    write_json(review_latest_dir() / "apply-results.json", applied)
    return applied
```

with:
```python
async def apply_review_plan(updates: list[JsonObject]) -> JsonObject:
    results = await apply_transaction_updates(updates)
    applied = {
        "appliedAt": now_iso(),
        "requestedCount": len(updates),
        "results": results,
    }
    write_json(review_latest_dir() / "apply-results.json", applied)
    return applied
```

- [ ] **Step 4: Update apply_clear_review_plan in review.py**

Replace:
```python
async def apply_clear_review_plan(limit: int | None = None) -> JsonObject:
    plan_path = review_latest_dir() / "clear-review-plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(
            "No clear-review plan found. Run `monarch review clear-plan` first."
        )

    plan = read_json(plan_path)
    updates = list(plan.get("updates") or [])
    if limit is not None:
        updates = updates[:limit]
    results = await apply_transaction_updates(updates)
    applied = {
        "appliedAt": now_iso(),
        "requestedCount": len(updates),
        "results": results,
    }
    write_json(review_latest_dir() / "clear-review-apply-results.json", applied)
    return applied
```

with:
```python
async def apply_clear_review_plan(updates: list[JsonObject]) -> JsonObject:
    results = await apply_transaction_updates(updates)
    applied = {
        "appliedAt": now_iso(),
        "requestedCount": len(updates),
        "results": results,
    }
    write_json(review_latest_dir() / "clear-review-apply-results.json", applied)
    return applied
```

- [ ] **Step 5: Update the two callers in cli.py**

`apply_reviews_command` — change:
```python
result = run_async(apply_review_plan(limit=limit))
```
to (after the existing `updates = updates[:limit]` filtering block):
```python
result = run_async(apply_review_plan(updates))
```

`apply_clear_reviews_command` — change:
```python
result = run_async(apply_clear_review_plan(limit=limit))
```
to:
```python
result = run_async(apply_clear_review_plan(updates))
```

`bulk_clear_reviews_command` currently calls `apply_clear_review_plan(limit=limit)`. Change to:
```python
plan = build_clear_review_plan(sorted(trust_categories))
updates = list(plan.get("updates") or [])
if limit is not None:
    updates = updates[:limit]
...
result = run_async(apply_clear_review_plan(updates))
```

- [ ] **Step 6: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add monarch_money_tools/review.py monarch_money_tools/cli.py
git commit -m "refactor: apply_review_plan and apply_clear_review_plan accept updates directly"
```

---

## Task 8: Create cmd/review.py

**Files:** Create `monarch_money_tools/cmd/review.py`

- [ ] **Step 1: Create cmd/review.py**

```python
from __future__ import annotations

from typing import Annotated

import typer

from ..monarch_api import apply_transaction_updates
from ..paths import review_latest_dir
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
        typer.Option("--min-confidence", min=0.0, max=1.0,
                     help="Minimum confidence required before planning an update."),
    ] = 0.78,
    include_pending: Annotated[
        bool,
        typer.Option("--include-pending", help="Include pending transactions in the plan."),
    ] = False,
    skip_already_correct: Annotated[
        bool,
        typer.Option("--skip-already-correct",
                     help="Do not clear review status when the category already matches history."),
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
    yes: Annotated[bool, typer.Option("--yes", help="Apply without an interactive prompt.")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Apply at most this many planned updates.")] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API.",
                     envvar="MONARCH_DRY_RUN"),
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
        typer.Option("--categories",
                     help="Comma-separated category names trusted for clearing Needs Review."),
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
    yes: Annotated[bool, typer.Option("--yes", help="Apply the latest clear-review plan without a prompt.")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Apply at most this many planned clears.")] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API.",
                     envvar="MONARCH_DRY_RUN"),
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


@review_app.command("llm")
def llm_review_command(
    focus: Annotated[
        str | None,
        typer.Option("--focus",
                     help="Comma-separated category names to focus on (default: Uncategorized,Misc Travel Expenses,Paychecks)."),
    ] = None,
    backend: Annotated[
        str,
        typer.Option("--backend", help="LLM backend: 'cli' (claude -p) or 'api' (ANTHROPIC_API_KEY)."),
    ] = "cli",
    model: Annotated[
        str | None,
        typer.Option("--model", help="Model override, e.g. claude-haiku-4-5-20251001."),
    ] = None,
    skip_p2p: Annotated[
        bool,
        typer.Option("--skip-p2p/--no-skip-p2p",
                     help="Skip P2P accounts (Venmo, Personal Profile, etc.). Default: True."),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show scope without calling the LLM.", envvar="MONARCH_DRY_RUN"),
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


@review_app.command("llm-apply")
def apply_llm_review_command(
    yes: Annotated[bool, typer.Option("--yes", help="Apply without an interactive prompt.")] = False,
    min_confidence: Annotated[
        float,
        typer.Option("--min-confidence", min=0.0, max=1.0, help="Minimum confidence to apply."),
    ] = 0.85,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Apply at most this many updates.")] = None,
    category: Annotated[
        list[str] | None,
        typer.Option("--category", help="Only apply updates for this suggested category (repeatable)."),
    ] = None,
    exclude_merchant: Annotated[
        list[str] | None,
        typer.Option("--exclude-merchant", help="Skip updates for this merchant name (repeatable)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API.",
                     envvar="MONARCH_DRY_RUN"),
    ] = False,
) -> None:
    """Apply the latest LLM review plan to Monarch."""
    plan_path = review_latest_dir() / "llm-review-plan.json"
    if not plan_path.exists():
        console.print("[red]No LLM review plan found.[/] Run `monarch review llm` first.")
        raise typer.Exit(1)

    plan = read_json(plan_path)
    updates = [u for u in (plan.get("updates") or []) if float(u.get("confidence", 0)) >= min_confidence]
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


@review_app.command("bulk-clear")
def bulk_clear_reviews_command(
    categories: Annotated[
        str,
        typer.Option("--categories",
                     help="Comma-separated category names to trust and clear review flag."),
    ] = "Transfer,Credit Card Payment,Buy Investment,Sell Investment,Interest",
    yes: Annotated[bool, typer.Option("--yes", help="Apply without an interactive prompt.")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Apply at most this many clears.")] = None,
) -> None:
    """Build and optionally apply a clear-review plan for trusted categories."""
    trust_categories = {c.strip() for c in categories.split(",") if c.strip()}
    plan = build_clear_review_plan(sorted(trust_categories))
    updates = list(plan.get("updates") or [])
    if limit is not None:
        updates = updates[:limit]
    if not updates:
        console.print("[yellow]No transactions to clear.[/]")
        raise typer.Exit(0)

    console.print(
        f"Clear-review plan written with [bold]{len(updates)}[/] transactions "
        f"in: {', '.join(sorted(trust_categories))}"
    )
    if not yes:
        confirmed = typer.confirm(f"Apply {len(updates)} planned review clears now?")
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_clear_review_plan(updates))
    console.print(f"[green]Cleared review flag on:[/] {result['requestedCount']} transactions")
```

- [ ] **Step 2: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass (cmd/review.py not yet wired into cli.py).

- [ ] **Step 3: Commit**

```bash
git add monarch_money_tools/cmd/review.py
git commit -m "refactor: add cmd/review.py with review sub-commands"
```

---

## Task 9: Create cmd/cleanup.py with filter_cleanup_candidates

**Files:**
- Modify: `monarch_money_tools/taxonomy_cleanup.py` (add `filter_cleanup_candidates`)
- Create: `monarch_money_tools/cmd/cleanup.py`

- [ ] **Step 1: Write failing test for filter_cleanup_candidates**

Add to `tests/test_taxonomy_cleanup.py`:

```python
from monarch_money_tools.taxonomy_cleanup import filter_cleanup_candidates


def test_filter_cleanup_candidates_skips_blocked_by_default() -> None:
    plan = {
        "candidates": [
            {"transactionId": "t1", "requiresNewCategory": False, "source": "taxonomy_migration"},
            {"transactionId": "t2", "requiresNewCategory": True, "source": "taxonomy_migration"},
        ]
    }
    result = filter_cleanup_candidates(plan, decisions={}, skip_blocked=True, source=None, limit=None)
    assert len(result) == 1
    assert result[0]["transactionId"] == "t1"


def test_filter_cleanup_candidates_applies_decisions() -> None:
    plan = {
        "candidates": [
            {"transactionId": "t1", "requiresNewCategory": False, "source": "taxonomy_migration"},
            {"transactionId": "t2", "requiresNewCategory": False, "source": "taxonomy_migration"},
        ]
    }
    decisions = {"t1": "accepted", "t2": "rejected"}
    result = filter_cleanup_candidates(plan, decisions=decisions, skip_blocked=False, source=None, limit=None)
    assert len(result) == 1
    assert result[0]["transactionId"] == "t1"


def test_filter_cleanup_candidates_filters_by_source() -> None:
    plan = {
        "candidates": [
            {"transactionId": "t1", "requiresNewCategory": False, "source": "taxonomy_migration"},
            {"transactionId": "t2", "requiresNewCategory": False, "source": "merchant_history"},
        ]
    }
    result = filter_cleanup_candidates(plan, decisions={}, skip_blocked=False,
                                       source="taxonomy_migration", limit=None)
    assert len(result) == 1
    assert result[0]["transactionId"] == "t1"


def test_filter_cleanup_candidates_respects_limit() -> None:
    plan = {
        "candidates": [
            {"transactionId": f"t{i}", "requiresNewCategory": False, "source": "taxonomy_migration"}
            for i in range(5)
        ]
    }
    result = filter_cleanup_candidates(plan, decisions={}, skip_blocked=False, source=None, limit=2)
    assert len(result) == 2
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_taxonomy_cleanup.py -k "filter" -v 2>&1 | tail -10
```

Expected: FAIL — `filter_cleanup_candidates` not defined.

- [ ] **Step 3: Add filter_cleanup_candidates to taxonomy_cleanup.py**

Add after the `save_decision` function:

```python
def filter_cleanup_candidates(
    plan: JsonObject,
    decisions: dict[str, str],
    skip_blocked: bool,
    source: str | None,
    limit: int | None,
) -> list[JsonObject]:
    candidates = list(plan.get("candidates") or [])
    if decisions:
        candidates = [
            c for c in candidates if decisions.get(c["transactionId"]) == "accepted"
        ]
    if skip_blocked:
        candidates = [c for c in candidates if not c.get("requiresNewCategory")]
    if source:
        candidates = [c for c in candidates if c.get("source") == source]
    if limit is not None:
        candidates = candidates[:limit]
    return candidates
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_taxonomy_cleanup.py -v 2>&1 | tail -10
```

- [ ] **Step 5: Create cmd/cleanup.py**

```python
from __future__ import annotations

from typing import Annotated

import typer

from ..monarch_api import apply_transaction_updates
from ..paths import cleanup_latest_dir
from ..review_cleanup import run_review_cleanup
from ..storage import read_json
from ..taxonomy_cleanup import build_taxonomy_cleanup_plan, filter_cleanup_candidates, load_decisions
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
    yes: Annotated[bool, typer.Option("--yes", help="Apply the cleanup plan without an interactive prompt.")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Apply at most this many updates.")] = None,
    source: Annotated[
        str | None,
        typer.Option("--source", help="Filter to a specific source: taxonomy_migration or merchant_history."),
    ] = None,
    skip_blocked: Annotated[
        bool,
        typer.Option("--skip-blocked", help="Skip candidates that require a new category (default: True)."),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API.",
                     envvar="MONARCH_DRY_RUN"),
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
```

- [ ] **Step 6: Run full suite**

```bash
uv run pytest --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add monarch_money_tools/taxonomy_cleanup.py monarch_money_tools/cmd/cleanup.py \
  tests/test_taxonomy_cleanup.py
git commit -m "refactor: add filter_cleanup_candidates and cmd/cleanup.py"
```

---

## Task 10: Create cmd/rules.py with build_push_rule_payload

**Files:**
- Modify: `monarch_money_tools/rules.py` (add `build_push_rule_payload`)
- Create: `monarch_money_tools/cmd/rules.py`

- [ ] **Step 1: Write failing test for build_push_rule_payload**

Add to `tests/test_rules.py`:

```python
from monarch_money_tools.rules import build_push_rule_payload


def test_build_push_rule_payload_with_merchant_names() -> None:
    rule = {
        "match": {"merchantNames": ["Coffee Shop", "Cafe"], "needsReview": True},
        "action": {"setCategory": "Dining", "clearNeedsReview": True},
    }
    payload = build_push_rule_payload(rule, category_id="cat-123")
    assert payload["setCategoryAction"] == "cat-123"
    assert payload["reviewStatusAction"] == "reviewed"
    assert len(payload["merchantNameCriteria"]) == 2
    assert payload["merchantNameCriteria"][0]["operator"] == "eq"
    assert payload["merchantNameCriteria"][0]["value"] == "coffee shop"


def test_build_push_rule_payload_with_merchant_pattern() -> None:
    rule = {
        "match": {"merchantPattern": "AMZN", "needsReview": True},
        "action": {"setCategory": "Shopping", "clearNeedsReview": False},
    }
    payload = build_push_rule_payload(rule, category_id="cat-shop")
    assert payload["merchantNameCriteria"][0]["operator"] == "contains"
    assert payload["merchantNameCriteria"][0]["value"] == "amzn"
    assert "reviewStatusAction" not in payload


def test_build_push_rule_payload_no_category() -> None:
    rule = {
        "match": {"merchantNames": ["Venmo"]},
        "action": {"clearNeedsReview": True},
    }
    payload = build_push_rule_payload(rule, category_id=None)
    assert "setCategoryAction" not in payload
    assert payload["reviewStatusAction"] == "reviewed"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_rules.py -k "push_rule_payload" -v 2>&1 | tail -10
```

- [ ] **Step 3: Add build_push_rule_payload to rules.py**

Add after `_rule_matches_filter`:

```python
def build_push_rule_payload(
    rule: JsonObject, category_id: str | None
) -> dict[str, object]:
    match_spec = rule.get("match") or {}
    action = rule.get("action") or {}
    merchant_names: list[str] = match_spec.get("merchantNames") or []
    merchant_pattern: str = match_spec.get("merchantPattern") or ""

    payload: dict[str, object] = {"applyToExistingTransactions": False}

    if category_id:
        payload["setCategoryAction"] = category_id

    if action.get("clearNeedsReview"):
        payload["reviewStatusAction"] = "reviewed"

    if merchant_names:
        payload["merchantNameCriteria"] = [
            {"operator": "eq", "value": name.lower()} for name in merchant_names
        ]
    elif merchant_pattern:
        payload["merchantNameCriteria"] = [
            {"operator": "contains", "value": merchant_pattern.lower()}
        ]

    return payload
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_rules.py -v 2>&1 | tail -15
```

- [ ] **Step 5: Create cmd/rules.py**

```python
from __future__ import annotations

from typing import Annotated, cast, Any

import typer
from rich.table import Table

from ..monarch_api import delete_monarch_rule, fetch_transaction_rules
from ..rules import build_apply_plan, build_push_rule_payload, build_rule_suggestions, load_rule_suggestions
from ._utils import _format_amount, console, exit_with_file_error, print_dry_run_table, run_async

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
    yes: Annotated[bool, typer.Option("--yes", help="Apply without an interactive prompt.")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Apply at most this many updates.")] = None,
    rules_path: Annotated[
        str | None,
        typer.Option("--rules-path", help="Path to a rule-suggestions.json file (default: data/rules/latest)."),
    ] = None,
    rule: Annotated[
        list[str] | None,
        typer.Option("--rule", help="Only apply this rule id or exact rule name (repeatable)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API.",
                     envvar="MONARCH_DRY_RUN"),
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
    rule_id: Annotated[str, typer.Argument(help="Local rule ID from rule-suggestions.json to push to Monarch.")],
    rules_path: Annotated[
        str | None,
        typer.Option("--rules-path", help="Path to rule-suggestions.json (default: data/rules/latest)."),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Create without confirmation prompt.")] = False,
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


@rules_app.command("delete")
def delete_monarch_rule_command(
    rule_id: Annotated[str, typer.Argument(help="Monarch rule ID to delete (from `monarch rules list`).")],
    yes: Annotated[bool, typer.Option("--yes", help="Delete without confirmation prompt.")] = False,
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
```

- [ ] **Step 6: Run full suite**

```bash
uv run pytest --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add monarch_money_tools/rules.py monarch_money_tools/cmd/rules.py tests/test_rules.py
git commit -m "refactor: add build_push_rule_payload and cmd/rules.py"
```

---

## Task 11: Create cmd/misc.py and slim cli.py

**Files:**
- Create: `monarch_money_tools/cmd/misc.py`
- Modify: `monarch_money_tools/cli.py` (replace with slim version)

- [ ] **Step 1: Create cmd/misc.py**

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ._utils import console, run_async

def init_command(
    yes: Annotated[bool, typer.Option("--yes", help="Non-interactive: use existing env values, skip prompts.")] = False,
) -> None:
    """Interactive setup wizard: credentials, connection test, taxonomy check, profile, doctor."""
    from ..init_wizard import run_init_wizard

    run_init_wizard(yes=yes)


def init_profile_command(
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing profile.yaml without prompting.")] = False,
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
        "[cyan]Edit it with your details, then run `monarch retire` to generate your simulation.[/]"
    )


def retire_command(
    profile_path: Annotated[
        Path | None,
        typer.Option("--profile", help="Path to profile.yaml (default: search cwd)."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Output HTML path (default: reports/retirement/simulation.html)."),
    ] = None,
    open_browser: Annotated[
        bool,
        typer.Option("--open", help="Open the generated HTML in your default browser."),
    ] = False,
) -> None:
    """Generate a personalized retirement simulation HTML from profile.yaml."""
    import webbrowser

    from ..paths import retirement_dir
    from ..profile import ProfileNotFoundError, load_profile
    from ..retire import generate_retirement_html

    try:
        profile = load_profile(profile_path)
    except ProfileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None

    out_path = output or (retirement_dir() / "simulation.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = generate_retirement_html(profile)
    out_path.write_text(html)
    console.print(f"[green]Retirement simulation written:[/] {out_path}")

    if open_browser:
        webbrowser.open(f"file://{out_path.absolute()}")


def portfolio_command(
    top: Annotated[int, typer.Option("--top", help="Number of top holdings to display.")] = 20,
    save: Annotated[bool, typer.Option("--save", help="Write holdings JSON to data/latest/portfolio-holdings.json.")] = False,
) -> None:
    """Fetch portfolio holdings from Monarch and display allocation summary."""
    import json
    from typing import cast, Any

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
```

- [ ] **Step 2: Replace cli.py with the slim version**

Replace the entire contents of `monarch_money_tools/cli.py` with:

```python
from __future__ import annotations

import typer

from .cmd._utils import console, exit_with_file_error, run_async  # noqa: F401 – re-exported
from .cmd.cleanup import cleanup_app
from .cmd.data import data_app, doctor_command, import_command, pull_command, run_command
from .cmd.misc import init_command, init_profile_command, portfolio_command, retire_command
from .cmd.review import review_app
from .cmd.rules import rules_app

app = typer.Typer(
    help="Local-first Monarch Money export analysis and planning CLI.",
    no_args_is_help=True,
)

app.add_typer(data_app, name="data")
app.add_typer(review_app, name="review")
app.add_typer(cleanup_app, name="cleanup")
app.add_typer(rules_app, name="rules")

# Primary flat shortcuts (visible at top level)
app.command("doctor")(doctor_command)
app.command("import")(import_command)
app.command("run")(run_command)
app.command("pull")(pull_command)
app.command("init")(init_command)
app.command("retire")(retire_command)
app.command("init-profile")(init_profile_command)
app.command("portfolio")(portfolio_command)
```

- [ ] **Step 3: Run full suite**

```bash
uv run pytest --tb=short -q
```

Expected: all 71+ tests pass. If any test fails, check that the command name or output string still matches — the command logic is identical, only the file location changed.

- [ ] **Step 4: Smoke-test the CLI**

```bash
uv run monarch --help
uv run monarch data --help
uv run monarch review --help
uv run monarch cleanup --help
uv run monarch rules --help
```

Expected: all sub-groups appear; primary flat commands (doctor, import, run, pull, init, retire) appear at top level.

- [ ] **Step 5: Commit**

```bash
git add monarch_money_tools/cmd/misc.py monarch_money_tools/cli.py
git commit -m "refactor: split cli.py into cmd/ sub-modules, slim cli.py to ~30 lines"
```

---

## Final verification

- [ ] **Run full suite one last time**

```bash
uv run pytest --tb=short -q
uv run ruff check .
uv run ruff format --check .
```

Expected: all tests pass, no lint errors.

- [ ] **Verify line counts**

```bash
wc -l monarch_money_tools/cli.py monarch_money_tools/cmd/*.py monarch_money_tools/storage.py
```

`cli.py` should be ≤ 35 lines.

- [ ] **Final commit (if any formatting fixes needed)**

```bash
git add -u
git commit -m "refactor: fix lint/format issues"
```
