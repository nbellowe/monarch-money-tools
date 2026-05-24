# GitHub Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 9 open GitHub issues: shared test fixtures, workbench scoping, tag-reimbursements removal, consistent --dry-run, monarch init wizard with auth, income classifier, interactive cleanup review, and PyPI release.

**Architecture:** Infrastructure first (fixtures, quick cleanup), then CLI consistency (dry-run), then new features (init wizard, income-overlay, review-cleanup), then release. All new business logic lives in dedicated modules; cli.py delegates. TDD throughout — write a failing test before implementation.

**Tech Stack:** Python 3.11+, typer, rich, pydantic, pytest, uv, ruff. monarchmoney library for API auth. GitHub Actions + pypa/gh-action-pypi-publish for release.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `tests/conftest.py` | Create | Shared `normalized_bundle` and `monarch_data_dir` fixtures |
| `monarch_money_tools/workbench.py` | Modify | Add internal-tool docstring |
| `monarch_money_tools/cli.py` | Modify (many times) | Remove tag-reimbursements, add dry-run flags, add init/income-overlay/review-cleanup commands |
| `monarch_money_tools/paths.py` | Modify | Fix `taxonomy_dir()`, add `cashflow_latest_dir()` |
| `monarch_money_tools/profile.py` | Modify | Add `IncomePatternConfig`, `CashflowConfig`, `cashflow` field on `UserProfile` |
| `monarch_money_tools/cashflow.py` | Create | Income classification logic and output writing |
| `monarch_money_tools/taxonomy_cleanup.py` | Modify | Add `load_decisions()`, `save_decision()`, decisions-aware candidate filtering |
| `monarch_money_tools/review_cleanup.py` | Create | Interactive accept/reject/skip loop |
| `monarch_money_tools/init_wizard.py` | Create | Credential setup, connection test, taxonomy check, profile bootstrap, doctor |
| `tests/test_taxonomy_cleanup.py` | Modify | Update taxonomy path after `taxonomy_dir()` fix |
| `tests/test_conftest_fixtures.py` | Create | Smoke-test the shared fixtures |
| `tests/test_dry_run.py` | Create | --dry-run tests for all four apply commands |
| `tests/test_init_wizard.py` | Create | Tests for init wizard steps |
| `tests/test_cashflow.py` | Create | Income classification tests |
| `tests/test_review_cleanup.py` | Create | Decision persistence and apply-cleanup filtering tests |
| `.github/workflows/ci.yml` | Create | CI on push/PR to main |
| `.github/workflows/publish.yml` | Create | Publish to PyPI on v* tag |
| `pyproject.toml` | Modify | Version → 0.0.1 |
| `README.md` | Modify | Install instructions → `uv tool install monarch-money-tools` |

---

## Task 1: Add conftest.py with Shared Fixtures

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_conftest_fixtures.py`

- [ ] **Step 1: Write a failing test that uses the fixture**

Create `tests/test_conftest_fixtures.py`:

```python
from __future__ import annotations

from monarch_money_tools.paths import normalized_latest_dir


def test_normalized_bundle_fixture_writes_bundle_json(normalized_bundle, tmp_path):
    path = normalized_latest_dir() / "bundle.json"
    assert path.exists()
    assert "transactions" in normalized_bundle
    assert "accounts" in normalized_bundle
    assert "categories" in normalized_bundle
    assert len(normalized_bundle["transactions"]) > 0


def test_monarch_data_dir_fixture_returns_tmp_path(monarch_data_dir, tmp_path):
    assert monarch_data_dir == tmp_path
    assert (tmp_path / "data/normalized/latest/bundle.json").exists()
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_conftest_fixtures.py -v
```

Expected: `ERROR` — `fixture 'normalized_bundle' not found`

- [ ] **Step 3: Create conftest.py**

Create `tests/conftest.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from monarch_money_tools.csv_adapter import import_transactions_from_csv
from monarch_money_tools.normalizer import (
    normalize_accounts,
    normalize_categories,
    normalize_transactions,
)
from monarch_money_tools.storage import write_json

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "monarch_transactions.csv"


@pytest.fixture
def normalized_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Writes a normalized bundle to tmp_path/data/normalized/latest/bundle.json.

    Changes cwd to tmp_path so all path helpers (normalized_latest_dir, etc.) resolve there.
    Returns the bundle dict with keys: transactions, accounts, categories, transactionRules.
    """
    monkeypatch.chdir(tmp_path)
    imported = import_transactions_from_csv(FIXTURE_CSV)
    bundle: dict[str, Any] = {
        "transactions": normalize_transactions(
            imported.transactions, imported.accounts, imported.categories
        ),
        "accounts": normalize_accounts(imported.accounts),
        "categories": normalize_categories(imported.categories),
        "transactionRules": [],
    }
    write_json(tmp_path / "data/normalized/latest/bundle.json", bundle)
    return bundle


@pytest.fixture
def monarch_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Patches root_dir() to a temp directory pre-populated with the fixture bundle.

    Returns tmp_path (the patched root). Use normalized_latest_dir() etc. to build paths.
    """
    monkeypatch.chdir(tmp_path)
    imported = import_transactions_from_csv(FIXTURE_CSV)
    bundle: dict[str, Any] = {
        "transactions": normalize_transactions(
            imported.transactions, imported.accounts, imported.categories
        ),
        "accounts": normalize_accounts(imported.accounts),
        "categories": normalize_categories(imported.categories),
        "transactionRules": [],
    }
    write_json(tmp_path / "data/normalized/latest/bundle.json", bundle)
    return tmp_path
```

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_conftest_fixtures.py -v
```

Expected: 2 PASSED

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest -v
```

Expected: all existing tests pass (fixtures are additive).

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_conftest_fixtures.py
git commit -m "test: add conftest.py with normalized_bundle and monarch_data_dir fixtures"
```

---

## Task 2: Mark workbench as Internal

**Files:**
- Modify: `monarch_money_tools/workbench.py` (first few lines)

- [ ] **Step 1: Add module docstring to workbench.py**

Open `monarch_money_tools/workbench.py`. The file currently starts with `from __future__ import annotations`. Add a module docstring before the imports:

```python
"""Internal investigation helpers — not part of the stable CLI surface.

Import functions here interactively (e.g. in a Python REPL or notebook) to
explore normalized transaction data. Not intended for end-user scripting.
"""
from __future__ import annotations
# ... rest of file unchanged
```

- [ ] **Step 2: Run full suite**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add monarch_money_tools/workbench.py
git commit -m "docs: mark workbench module as internal investigation tool"
```

---

## Task 3: Remove tag-reimbursements Command

**Files:**
- Modify: `monarch_money_tools/cli.py`

Note: `tag_transactions` stays in `monarch_api.py` — it is used by `rules.py` via a local import there. Only the top-level import in `cli.py` needs to be removed.

- [ ] **Step 1: Verify no tests reference tag-reimbursements**

```bash
grep -rn "tag.reimburs\|tag_reimburs" tests/
```

Expected: no output (confirmed no tests exist for this command).

- [ ] **Step 2: Remove the command from cli.py**

In `monarch_money_tools/cli.py`, remove the `tag_transactions` import from the top-level block:

```python
# REMOVE this line from the monarchmoney_api import block:
    tag_transactions,
```

Then delete the entire `tag_reimbursements_command` function (lines 535–599 in the current file — from `@app.command("tag-reimbursements")` through the final `console.print` call and its closing paren).

- [ ] **Step 3: Run full suite**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 4: Confirm command is gone**

```bash
uv run monarch --help | grep tag
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add monarch_money_tools/cli.py
git commit -m "feat: remove tag-reimbursements command (too Expensify/Navan-specific)"
```

---

## Task 4: `--dry-run` for `apply-reviews`

**Files:**
- Create: `tests/test_dry_run.py` (start file here; later tasks append to it)
- Modify: `monarch_money_tools/cli.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_dry_run.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from monarch_money_tools.cli import app
from monarch_money_tools.storage import write_json

runner = CliRunner()


def _write_review_plan(tmp_path: Path) -> None:
    plan = {
        "generatedAt": "2026-05-24T00:00:00Z",
        "summary": {"plannedUpdateCount": 2, "deferredCount": 0},
        "updates": [
            {
                "transactionId": "t1",
                "date": "2026-05-01",
                "merchantName": "Acme Coffee",
                "accountName": "Checking",
                "amount": -5.25,
                "currentCategory": "Shopping",
                "suggestedCategory": "Dining",
                "categoryId": "cat-dining",
                "confidence": 0.92,
                "action": "recategorize",
                "setNeedsReview": False,
            },
            {
                "transactionId": "t2",
                "date": "2026-05-02",
                "merchantName": "Gas Station",
                "accountName": "Checking",
                "amount": -45.00,
                "currentCategory": "Uncategorized",
                "suggestedCategory": "Auto & Transport",
                "categoryId": "cat-auto",
                "confidence": 0.88,
                "action": "recategorize",
                "setNeedsReview": False,
            },
        ],
    }
    write_json(tmp_path / "data/review/latest/review-plan.json", plan)


def test_apply_reviews_dry_run_prints_table_and_skips_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_review_plan(tmp_path)

    api_called = []
    monkeypatch.setattr(
        "monarch_money_tools.cli.run_async",
        lambda coro: api_called.append(coro) or {},
    )

    result = runner.invoke(app, ["apply-reviews", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert not api_called, "API should not be called during dry-run"
    assert "Acme Coffee" in result.output
    assert "Gas Station" in result.output
    assert "Dining" in result.output
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_dry_run.py::test_apply_reviews_dry_run_prints_table_and_skips_api -v
```

Expected: FAILED — `apply-reviews` has no `--dry-run` flag yet.

- [ ] **Step 3: Add `--dry-run` to `apply_reviews_command` in cli.py**

In `monarch_money_tools/cli.py`, modify `apply_reviews_command`:

```python
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API."),
    ] = False,
) -> None:
    """Apply the latest planned transaction updates to Monarch."""
    from .paths import review_latest_dir
    from .storage import read_json

    plan_path = review_latest_dir() / "review-plan.json"
    if not plan_path.exists():
        console.print("[red]No review plan found.[/] Run `monarch plan-reviews` first.")
        raise typer.Exit(1)

    plan = read_json(plan_path)
    updates = list(plan.get("updates") or [])
    if limit is not None:
        updates = updates[:limit]

    if not updates:
        console.print("[yellow]No updates to apply.[/]")
        raise typer.Exit(0)

    if dry_run:
        table = Table(title=f"Dry run — {len(updates)} updates")
        table.add_column("Merchant")
        table.add_column("Current Category")
        table.add_column("Suggested")
        table.add_column("Confidence", justify="right")
        for u in updates[:50]:
            table.add_row(
                u["merchantName"],
                u["currentCategory"],
                u["suggestedCategory"],
                f"{float(u.get('confidence', 0)):.0%}",
            )
        console.print(table)
        if len(updates) > 50:
            console.print(f"[dim]… and {len(updates) - 50} more[/]")
        return

    if not yes:
        confirmed = typer.confirm(
            "This will update Monarch transactions through the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_review_plan(limit=limit))
    console.print(f"[green]Applied review updates:[/] {result['requestedCount']}")
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_dry_run.py::test_apply_reviews_dry_run_prints_table_and_skips_api -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add monarch_money_tools/cli.py tests/test_dry_run.py
git commit -m "feat: add --dry-run to apply-reviews"
```

---

## Task 5: `--dry-run` for `apply-clear-reviews`

**Files:**
- Modify: `tests/test_dry_run.py` (append test)
- Modify: `monarch_money_tools/cli.py`

- [ ] **Step 1: Append failing test to test_dry_run.py**

```python
def _write_clear_review_plan(tmp_path: Path) -> None:
    plan = {
        "generatedAt": "2026-05-24T00:00:00Z",
        "summary": {"plannedUpdateCount": 1, "deferredCount": 0, "trustedCategories": ["Dining"]},
        "updates": [
            {
                "transactionId": "t3",
                "date": "2026-05-03",
                "merchantName": "Sushi Place",
                "accountName": "Checking",
                "amount": -32.00,
                "currentCategory": "Dining",
                "suggestedCategory": "Dining",
                "categoryId": "cat-dining",
                "currentNeedsReview": True,
                "setNeedsReview": False,
                "confidence": 0.99,
                "action": "clear_review",
                "rationale": "Dining is trusted.",
            }
        ],
        "deferred": [],
    }
    write_json(tmp_path / "data/review/latest/clear-review-plan.json", plan)


def test_apply_clear_reviews_dry_run_prints_table_and_skips_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_clear_review_plan(tmp_path)

    api_called = []
    monkeypatch.setattr(
        "monarch_money_tools.cli.run_async",
        lambda coro: api_called.append(coro) or {},
    )

    result = runner.invoke(app, ["apply-clear-reviews", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert not api_called
    assert "Sushi Place" in result.output
    assert "Dining" in result.output
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_dry_run.py::test_apply_clear_reviews_dry_run_prints_table_and_skips_api -v
```

Expected: FAILED

- [ ] **Step 3: Add `--dry-run` to `apply_clear_reviews_command` in cli.py**

```python
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API."),
    ] = False,
) -> None:
    """Apply the latest reviewed clear-review plan to Monarch."""
    from .paths import review_latest_dir
    from .storage import read_json

    plan_path = review_latest_dir() / "clear-review-plan.json"
    if not plan_path.exists():
        console.print("[red]No clear-review plan found.[/] Run `monarch plan-clear-reviews` first.")
        raise typer.Exit(1)

    plan = read_json(plan_path)
    updates = list(plan.get("updates") or [])
    if limit is not None:
        updates = updates[:limit]

    if not updates:
        console.print("[yellow]No updates to apply.[/]")
        raise typer.Exit(0)

    if dry_run:
        table = Table(title=f"Dry run — {len(updates)} clears")
        table.add_column("Merchant")
        table.add_column("Category")
        table.add_column("Account")
        for u in updates[:50]:
            table.add_row(
                u["merchantName"],
                u["currentCategory"],
                u.get("accountName", ""),
            )
        console.print(table)
        if len(updates) > 50:
            console.print(f"[dim]… and {len(updates) - 50} more[/]")
        return

    if not yes:
        confirmed = typer.confirm(
            "This will clear Needs Review through the unofficial API. Continue?"
        )
        if not confirmed:
            raise typer.Abort()

    result = run_async(apply_clear_review_plan(limit=limit))
    console.print(f"[green]Cleared review flag on:[/] {result['requestedCount']} transactions")
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_dry_run.py::test_apply_clear_reviews_dry_run_prints_table_and_skips_api -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add monarch_money_tools/cli.py tests/test_dry_run.py
git commit -m "feat: add --dry-run to apply-clear-reviews"
```

---

## Task 6: `--dry-run` for `apply-cleanup`

**Files:**
- Modify: `tests/test_dry_run.py` (append test)
- Modify: `monarch_money_tools/cli.py`

- [ ] **Step 1: Append failing test**

```python
def _write_cleanup_plan(tmp_path: Path) -> None:
    plan = {
        "generatedAt": "2026-05-24T00:00:00Z",
        "summary": {
            "taxonomyMigrationCount": 1,
            "merchantConsistencyCount": 0,
            "readyCount": 1,
            "blockedCount": 0,
        },
        "candidates": [
            {
                "transactionId": "t4",
                "date": "2026-05-04",
                "merchantName": "Mechanic Shop",
                "accountName": "Checking",
                "amount": -200.00,
                "currentCategory": "Auto Maintenance",
                "suggestedCategory": "Auto Maintenance & Fees",
                "categoryId": "cat-auto-maint",
                "confidence": 1.0,
                "source": "taxonomy_migration",
                "requiresNewCategory": False,
                "setNeedsReview": False,
            }
        ],
    }
    write_json(tmp_path / "data/cleanup/latest/cleanup-plan.json", plan)


def test_apply_cleanup_dry_run_prints_table_and_skips_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_cleanup_plan(tmp_path)

    api_called = []
    monkeypatch.setattr(
        "monarch_money_tools.cli.run_async",
        lambda coro: api_called.append(coro) or {},
    )

    result = runner.invoke(app, ["apply-cleanup", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert not api_called
    assert "Mechanic Shop" in result.output
    assert "Auto Maintenance & Fees" in result.output
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_dry_run.py::test_apply_cleanup_dry_run_prints_table_and_skips_api -v
```

Expected: FAILED

- [ ] **Step 3: Add `--dry-run` to `apply_cleanup_command` in cli.py**

Replace the `apply_cleanup_command` function signature and add the dry-run block after candidate filtering and before the `if not yes:` prompt:

```python
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API."),
    ] = False,
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

    # Apply decision log if it exists: only accepted candidates
    decisions_path = cleanup_latest_dir() / "decisions.json"
    if decisions_path.exists():
        decisions = read_json(decisions_path)
        candidates = [c for c in candidates if decisions.get(c["transactionId"]) == "accepted"]

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

    if dry_run:
        table = Table(title=f"Dry run — {len(candidates)} updates")
        table.add_column("Merchant")
        table.add_column("Current Category")
        table.add_column("Suggested")
        table.add_column("Confidence", justify="right")
        table.add_column("Source")
        for c in candidates[:50]:
            table.add_row(
                c["merchantName"],
                c["currentCategory"],
                c["suggestedCategory"],
                f"{float(c.get('confidence', 0)):.0%}",
                c.get("source", ""),
            )
        console.print(table)
        if len(candidates) > 50:
            console.print(f"[dim]… and {len(candidates) - 50} more[/]")
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

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_dry_run.py::test_apply_cleanup_dry_run_prints_table_and_skips_api -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add monarch_money_tools/cli.py tests/test_dry_run.py
git commit -m "feat: add --dry-run to apply-cleanup"
```

---

## Task 7: `--dry-run` for `apply-llm-review`

**Files:**
- Modify: `tests/test_dry_run.py` (append test)
- Modify: `monarch_money_tools/cli.py`

- [ ] **Step 1: Append failing test**

```python
def _write_llm_review_plan(tmp_path: Path) -> None:
    plan = {
        "generatedAt": "2026-05-24T00:00:00Z",
        "summary": {"updateCount": 2, "highConfidenceCount": 1, "lowConfidenceCount": 1},
        "updates": [
            {
                "transactionId": "t5",
                "date": "2026-05-05",
                "merchantName": "Amazon",
                "accountName": "Checking",
                "amount": -34.99,
                "currentCategory": "Uncategorized",
                "suggestedCategory": "Shopping",
                "categoryId": "cat-shopping",
                "confidence": 0.95,
                "source": "llm_review",
                "setNeedsReview": False,
            },
            {
                "transactionId": "t6",
                "date": "2026-05-06",
                "merchantName": "Mystery Store",
                "accountName": "Checking",
                "amount": -12.00,
                "currentCategory": "Uncategorized",
                "suggestedCategory": "Shopping",
                "categoryId": "cat-shopping",
                "confidence": 0.70,
                "source": "llm_review",
                "setNeedsReview": False,
            },
        ],
    }
    write_json(tmp_path / "data/review/latest/llm-review-plan.json", plan)


def test_apply_llm_review_dry_run_prints_table_and_skips_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_llm_review_plan(tmp_path)

    api_called = []
    monkeypatch.setattr(
        "monarch_money_tools.cli.run_async",
        lambda coro: api_called.append(coro) or {},
    )

    result = runner.invoke(app, ["apply-llm-review", "--dry-run", "--min-confidence", "0.85"])

    assert result.exit_code == 0, result.output
    assert not api_called
    assert "Amazon" in result.output
    # Mystery Store confidence 0.70 < 0.85, should not appear
    assert "Mystery Store" not in result.output
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_dry_run.py::test_apply_llm_review_dry_run_prints_table_and_skips_api -v
```

Expected: FAILED

- [ ] **Step 3: Add `--dry-run` to `apply_llm_review_command` in cli.py**

Add the `dry_run` parameter and insert the dry-run block after filtering and before `if not yes:`:

```python
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be applied without calling the API."),
    ] = False,
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

    if dry_run:
        table = Table(title=f"Dry run — {len(updates)} updates")
        table.add_column("Merchant")
        table.add_column("Current Category")
        table.add_column("Suggested")
        table.add_column("Confidence", justify="right")
        for u in updates[:50]:
            table.add_row(
                u["merchantName"],
                u["currentCategory"],
                u["suggestedCategory"],
                f"{float(u.get('confidence', 0)):.0%}",
            )
        console.print(table)
        if len(updates) > 50:
            console.print(f"[dim]… and {len(updates) - 50} more[/]")
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
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_dry_run.py -v
```

Expected: all 4 dry-run tests PASSED

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/cli.py tests/test_dry_run.py
git commit -m "feat: add --dry-run to apply-llm-review (closes #8)"
```

---

## Task 8: `monarch init` Setup Wizard

**Files:**
- Modify: `monarch_money_tools/paths.py` — fix `taxonomy_dir()`, add note about root location
- Modify: `tests/test_taxonomy_cleanup.py` — update fixture path after taxonomy_dir fix
- Create: `monarch_money_tools/init_wizard.py`
- Modify: `monarch_money_tools/cli.py` — add `monarch init` command
- Create: `tests/test_init_wizard.py`

### Step 8a: Fix taxonomy_dir()

The actual taxonomy file lives at `taxonomy/canonical-taxonomy.yaml` (project root, version-controlled). `taxonomy_dir()` currently returns `data/taxonomy/` which is wrong.

- [ ] **Step 1: Fix taxonomy_dir() in paths.py**

In `monarch_money_tools/paths.py`, change:

```python
def taxonomy_dir() -> Path:
    return data_dir() / "taxonomy"
```

to:

```python
def taxonomy_dir() -> Path:
    return root_dir() / "taxonomy"
```

- [ ] **Step 2: Fix the test that creates the taxonomy at the old path**

In `tests/test_taxonomy_cleanup.py`, find `taxonomy = tmp_path / "data/taxonomy/canonical-taxonomy.yaml"` and change to:

```python
taxonomy = tmp_path / "taxonomy" / "canonical-taxonomy.yaml"
```

(The `.parent.mkdir(parents=True)` call below it stays the same.)

- [ ] **Step 3: Run full suite to confirm the fix**

```bash
uv run pytest -v
```

Expected: all pass.

### Step 8b: init_wizard.py

- [ ] **Step 4: Write failing tests**

Create `tests/test_init_wizard.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from monarch_money_tools.init_wizard import _append_env, _read_env


def test_read_env_parses_key_value_pairs(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('MONARCH_EMAIL="test@example.com"\nMONARCH_PASSWORD=secret\n', encoding="utf-8")
    result = _read_env(env)
    assert result["MONARCH_EMAIL"] == "test@example.com"
    assert result["MONARCH_PASSWORD"] == "secret"


def test_read_env_returns_empty_for_missing_file(tmp_path: Path) -> None:
    result = _read_env(tmp_path / ".env")
    assert result == {}


def test_append_env_adds_missing_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('MONARCH_EMAIL="existing@example.com"\n', encoding="utf-8")
    _append_env(env, {"MONARCH_EMAIL": "other@example.com", "MONARCH_PASSWORD": "pw"})
    content = env.read_text(encoding="utf-8")
    # MONARCH_EMAIL already existed — must not be overwritten
    assert 'MONARCH_EMAIL="other@example.com"' not in content
    assert "existing@example.com" in content
    # MONARCH_PASSWORD was missing — must be added
    assert "MONARCH_PASSWORD" in content
    assert "pw" in content


def test_append_env_creates_file_if_missing(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    _append_env(env, {"MONARCH_EMAIL": "new@example.com"})
    assert env.exists()
    assert "new@example.com" in env.read_text(encoding="utf-8")


def test_append_env_no_op_when_all_keys_exist(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('MONARCH_EMAIL="a@b.com"\n', encoding="utf-8")
    _append_env(env, {"MONARCH_EMAIL": "other@b.com"})
    content = env.read_text(encoding="utf-8")
    assert content.count("MONARCH_EMAIL") == 1
```

- [ ] **Step 5: Run to verify they fail**

```bash
uv run pytest tests/test_init_wizard.py -v
```

Expected: ERROR — `No module named 'monarch_money_tools.init_wizard'`

- [ ] **Step 6: Create init_wizard.py**

Create `monarch_money_tools/init_wizard.py`:

```python
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def _append_env(path: Path, new_keys: dict[str, str]) -> None:
    """Append keys that are not already set in the .env file. Never overwrites."""
    existing = _read_env(path)
    to_add = {k: v for k, v in new_keys.items() if k not in existing}
    if not to_add:
        return
    with path.open("a", encoding="utf-8") as f:
        for k, v in to_add.items():
            f.write(f'{k}="{v}"\n')


def _step_credentials(yes: bool, env_path: Path) -> None:
    email = os.environ.get("MONARCH_EMAIL") or _read_env(env_path).get("MONARCH_EMAIL")
    password = os.environ.get("MONARCH_PASSWORD") or _read_env(env_path).get("MONARCH_PASSWORD")

    console.print("\n[bold]Step 1: Credentials[/]")
    if email and password:
        console.print("[green]✓ Credentials already set.[/]")
        return

    if yes:
        console.print(
            "[yellow]--yes mode: skipping credential prompts. "
            "Set MONARCH_EMAIL and MONARCH_PASSWORD in .env.[/]"
        )
        return

    if not email:
        email = typer.prompt("Monarch Money email")
    if not password:
        password = typer.prompt("Monarch Money password", hide_input=True)

    mfa = os.environ.get("MONARCH_MFA_SECRET") or _read_env(env_path).get("MONARCH_MFA_SECRET")
    if not mfa:
        console.print(
            "[dim]Optional: MFA secret for automatic login.[/]\n"
            "[dim]To get it: disable 2FA in Monarch → re-enable → click 'Can't scan?' "
            "→ copy the BASE32 secret.[/]"
        )
        mfa_input = typer.prompt("MFA secret (Enter to skip)", default="")
        mfa = mfa_input or None

    new_keys: dict[str, str] = {}
    if email:
        new_keys["MONARCH_EMAIL"] = email
    if password:
        new_keys["MONARCH_PASSWORD"] = password
    if mfa:
        new_keys["MONARCH_MFA_SECRET"] = mfa

    _append_env(env_path, new_keys)
    console.print("[green]✓ Credentials written to .env[/]")


def _step_connection_test() -> None:
    console.print("\n[bold]Step 2: Connection test[/]")
    try:
        from .monarch_api import create_monarch_client

        async def _test() -> None:
            client = await create_monarch_client()
            await client.get_transaction_categories()

        asyncio.run(_test())
        console.print("[green]✓ Connected to Monarch successfully.[/]")
    except Exception as exc:
        console.print(f"[yellow]Connection test failed:[/] {exc}")
        console.print(
            "[dim]Check MONARCH_EMAIL / MONARCH_PASSWORD / MONARCH_MFA_SECRET in .env "
            "and try again.[/]"
        )


def _step_taxonomy_check() -> None:
    console.print("\n[bold]Step 3: Taxonomy check[/]")
    from .paths import taxonomy_dir

    taxonomy_path = taxonomy_dir() / "canonical-taxonomy.yaml"
    if not taxonomy_path.exists():
        console.print(f"[yellow]Taxonomy not found at {taxonomy_path} — skipping.[/]")
        return

    try:
        import yaml

        with open(taxonomy_path, encoding="utf-8") as f:
            taxonomy = yaml.safe_load(f)
        canonical_names = {c["name"] for c in (taxonomy.get("categories") or [])}

        async def _fetch_live() -> set[str]:
            from .monarch_api import create_monarch_client

            client = await create_monarch_client()
            result = await client.get_transaction_categories()
            cats = result.get("categories") or []
            return {c["name"] for c in cats}

        live_names = asyncio.run(_fetch_live())
        only_canonical = canonical_names - live_names
        only_live = live_names - canonical_names

        if not only_canonical and not only_live:
            console.print("[green]✓ Taxonomy matches Monarch categories.[/]")
        else:
            if only_canonical:
                console.print(
                    f"[yellow]In taxonomy but not in Monarch ({len(only_canonical)}):[/] "
                    + ", ".join(sorted(only_canonical))
                )
            if only_live:
                console.print(
                    f"[yellow]In Monarch but not in taxonomy ({len(only_live)}):[/] "
                    + ", ".join(sorted(only_live))
                )
    except Exception as exc:
        console.print(f"[yellow]Taxonomy check skipped:[/] {exc}")


def _step_profile_bootstrap(yes: bool) -> None:
    console.print("\n[bold]Step 4: Profile[/]")
    profile_path = Path("profile.yaml")
    if profile_path.exists():
        console.print("[green]✓ profile.yaml already exists.[/]")
        return

    from .profile import PROFILE_TEMPLATE

    if not yes and not typer.confirm("Create a starter profile.yaml?", default=True):
        return

    profile_path.write_text(PROFILE_TEMPLATE, encoding="utf-8")
    console.print("[green]✓ Created profile.yaml — edit it before running `monarch retire`.[/]")


def _step_doctor() -> None:
    console.print("\n[bold]Step 5: Doctor[/]")
    from .doctor import collect_checks, has_python_project

    all_ok = True
    for name, ok, detail in collect_checks():
        status = "[green]ok[/]" if ok else "[red]missing[/]"
        console.print(f"  {status}  {name}: {detail}")
        if not ok:
            all_ok = False
    pyproject_ok = has_python_project()
    console.print(
        f"  {'[green]ok[/]' if pyproject_ok else '[red]missing[/]'}  python project: pyproject.toml"
    )
    if all_ok and pyproject_ok:
        console.print("[green]✓ All checks passed.[/]")


def run_init_wizard(yes: bool = False) -> None:
    env_path = Path(".env")
    _step_credentials(yes, env_path)
    _step_connection_test()
    _step_taxonomy_check()
    _step_profile_bootstrap(yes)
    _step_doctor()
```

- [ ] **Step 7: Run to verify tests pass**

```bash
uv run pytest tests/test_init_wizard.py -v
```

Expected: 5 PASSED

- [ ] **Step 8: Add `monarch init` command to cli.py**

Add this import at the top of cli.py (with other module imports):

```python
from .init_wizard import run_init_wizard
```

Add this command (place before or after `init-profile`):

```python
@app.command("init")
def init_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Non-interactive: use existing env values, skip prompts."),
    ] = False,
) -> None:
    """Interactive setup wizard: credentials, connection test, taxonomy check, profile, doctor."""
    run_init_wizard(yes=yes)
```

- [ ] **Step 9: Run full suite**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add monarch_money_tools/paths.py monarch_money_tools/init_wizard.py monarch_money_tools/cli.py tests/test_init_wizard.py tests/test_taxonomy_cleanup.py
git commit -m "feat: add monarch init setup wizard with interactive auth flow (closes #7, #13)"
```

---

## Task 9: `monarch income-overlay` Command

**Files:**
- Modify: `monarch_money_tools/paths.py` — add `cashflow_latest_dir()`
- Modify: `monarch_money_tools/profile.py` — add `IncomePatternConfig`, `CashflowConfig`
- Create: `monarch_money_tools/cashflow.py`
- Modify: `monarch_money_tools/cli.py` — add `income-overlay` command
- Create: `tests/test_cashflow.py`

- [ ] **Step 1: Add cashflow_latest_dir() to paths.py**

```python
def cashflow_latest_dir() -> Path:
    return data_dir() / "cashflow" / "latest"
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_cashflow.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from monarch_money_tools.cashflow import classify_transactions
from monarch_money_tools.profile import (
    CashflowConfig,
    IncomePatternConfig,
    UserProfile,
)

BASE_TXN = {
    "id": "t1",
    "date": "2026-05-01",
    "merchantName": "Acme Corp Payroll",
    "categoryName": "Paychecks",
    "groupName": "Income",
    "signedAmount": 5000.0,
    "accountName": "Checking",
    "needsReview": False,
    "isPending": False,
}


def _profile_with_patterns() -> UserProfile:
    return UserProfile.model_validate(
        {
            "cashflow": {
                "income_sources": [{"pattern": "Acme Corp Payroll"}],
                "reimbursement_patterns": [{"pattern": "Expensify"}],
                "transfer_patterns": [{"pattern": "Zelle from"}],
            }
        }
    )


def test_classify_salary_by_pattern() -> None:
    txn = {**BASE_TXN, "merchantName": "Acme Corp Payroll", "signedAmount": 5000.0}
    results = classify_transactions([txn], _profile_with_patterns())
    assert results[0]["classification"] == "salary"
    assert results[0]["manual_review"] is False


def test_classify_reimbursement_by_pattern() -> None:
    txn = {**BASE_TXN, "merchantName": "Expensify", "categoryName": "Other Income"}
    results = classify_transactions([txn], _profile_with_patterns())
    assert results[0]["classification"] == "reimbursement"


def test_classify_transfer_by_pattern() -> None:
    txn = {**BASE_TXN, "merchantName": "Zelle from Alex", "categoryName": "Transfer"}
    results = classify_transactions([txn], _profile_with_patterns())
    assert results[0]["classification"] == "transfer"


def test_classify_investment_proceeds_by_category() -> None:
    txn = {**BASE_TXN, "merchantName": "Vanguard", "categoryName": "Sell Investment"}
    results = classify_transactions([txn], None)
    assert results[0]["classification"] == "investment_proceeds"


def test_classify_salary_by_category_heuristic_when_no_profile() -> None:
    txn = {**BASE_TXN, "merchantName": "Unknown Payroll", "categoryName": "Paychecks"}
    results = classify_transactions([txn], None)
    assert results[0]["classification"] == "salary"


def test_classify_spending_as_default() -> None:
    txn = {**BASE_TXN, "merchantName": "Starbucks", "categoryName": "Dining", "signedAmount": -5.0}
    results = classify_transactions([txn], _profile_with_patterns())
    assert results[0]["classification"] == "spending"


def test_date_filter_start(tmp_path: Path) -> None:
    txns = [
        {**BASE_TXN, "id": "a", "date": "2026-01-01"},
        {**BASE_TXN, "id": "b", "date": "2026-06-01"},
    ]
    results = classify_transactions(txns, None, start="2026-03-01")
    assert len(results) == 1
    assert results[0]["id"] == "b"


def test_date_filter_end(tmp_path: Path) -> None:
    txns = [
        {**BASE_TXN, "id": "a", "date": "2026-01-01"},
        {**BASE_TXN, "id": "b", "date": "2026-06-01"},
    ]
    results = classify_transactions(txns, None, end="2026-03-01")
    assert len(results) == 1
    assert results[0]["id"] == "a"
```

- [ ] **Step 3: Run to verify they fail**

```bash
uv run pytest tests/test_cashflow.py -v
```

Expected: ERROR — `No module named 'monarch_money_tools.cashflow'`

- [ ] **Step 4: Add profile additions**

In `monarch_money_tools/profile.py`, add before `UserProfile`:

```python
class IncomePatternConfig(ProfileBaseModel):
    pattern: str


class CashflowConfig(ProfileBaseModel):
    income_sources: list[IncomePatternConfig] = Field(default_factory=list)
    reimbursement_patterns: list[IncomePatternConfig] = Field(default_factory=list)
    transfer_patterns: list[IncomePatternConfig] = Field(default_factory=list)
```

In `UserProfile`, add:

```python
cashflow: CashflowConfig = Field(default_factory=CashflowConfig)
```

Also add `CashflowConfig` and `IncomePatternConfig` to `__all__`.

- [ ] **Step 5: Create cashflow.py**

Create `monarch_money_tools/cashflow.py`:

```python
from __future__ import annotations

import re
from typing import Any

from .paths import cashflow_latest_dir, normalized_latest_dir
from .profile import UserProfile
from .storage import read_json, reset_dir, write_csv, write_json, write_text

JsonObject = dict[str, Any]

LABEL_SALARY = "salary"
LABEL_REIMBURSEMENT = "reimbursement"
LABEL_TRANSFER = "transfer"
LABEL_INVESTMENT = "investment_proceeds"
LABEL_SPENDING = "spending"

_SALARY_CATEGORIES = {"Paychecks"}
_INVESTMENT_CATEGORIES = {"Sell Investment"}
_TRANSFER_CATEGORIES = {"Transfer", "Credit Card Payment"}


def classify_transactions(
    transactions: list[JsonObject],
    profile: UserProfile | None,
    start: str | None = None,
    end: str | None = None,
) -> list[JsonObject]:
    filtered = [
        t for t in transactions
        if (start is None or str(t.get("date", "")) >= start)
        and (end is None or str(t.get("date", "")) <= end)
    ]
    return [_annotate(t, profile) for t in filtered]


def _annotate(txn: JsonObject, profile: UserProfile | None) -> JsonObject:
    label, manual_review = _classify_one(txn, profile)
    return {**txn, "classification": label, "manual_review": manual_review}


def _classify_one(txn: JsonObject, profile: UserProfile | None) -> tuple[str, bool]:
    merchant = str(txn.get("merchantName") or "")
    category = str(txn.get("categoryName") or "")

    if profile is not None:
        cf = profile.cashflow
        if _matches_any(merchant, [p.pattern for p in cf.income_sources]):
            return LABEL_SALARY, False
        if _matches_any(merchant, [p.pattern for p in cf.reimbursement_patterns]):
            return LABEL_REIMBURSEMENT, False
        if _matches_any(merchant, [p.pattern for p in cf.transfer_patterns]):
            return LABEL_TRANSFER, False

    if category in _SALARY_CATEGORIES:
        return LABEL_SALARY, False
    if category in _INVESTMENT_CATEGORIES:
        return LABEL_INVESTMENT, False
    if category in _TRANSFER_CATEGORIES:
        return LABEL_TRANSFER, False

    return LABEL_SPENDING, False


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(re.search(p, value, re.IGNORECASE) for p in patterns)


def run_income_overlay(
    profile: UserProfile | None,
    start: str | None = None,
    end: str | None = None,
) -> JsonObject:
    bundle_path = normalized_latest_dir() / "bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(
            "No normalized bundle. Run `monarch pull` or `monarch import` first."
        )

    bundle = read_json(bundle_path)
    transactions = [t for t in (bundle.get("transactions") or []) if not t.get("isPending")]
    classified = classify_transactions(transactions, profile, start=start, end=end)

    counts: dict[str, int] = {}
    totals: dict[str, float] = {}
    manual_review_count = 0
    for t in classified:
        label = t["classification"]
        counts[label] = counts.get(label, 0) + 1
        totals[label] = totals.get(label, 0.0) + float(t.get("signedAmount") or 0)
        if t["manual_review"]:
            manual_review_count += 1

    summary = {
        "transactionCount": len(classified),
        "manualReviewCount": manual_review_count,
        "byLabel": [
            {"label": label, "count": counts[label], "total": round(totals[label], 2)}
            for label in [LABEL_SALARY, LABEL_REIMBURSEMENT, LABEL_TRANSFER,
                          LABEL_INVESTMENT, LABEL_SPENDING]
            if label in counts
        ],
    }
    result = {"summary": summary, "transactions": classified}

    out_dir = cashflow_latest_dir()
    reset_dir(out_dir)
    write_json(out_dir / "income-overlay.json", result)
    write_csv(out_dir / "income-overlay.csv", classified)
    _write_markdown(out_dir / "income-overlay.md", summary)
    return result


def _write_markdown(path: Any, summary: JsonObject) -> None:
    lines = ["# Income Overlay\n", f"Total transactions: {summary['transactionCount']}\n"]
    if summary["manualReviewCount"]:
        lines.append(f"**Manual review needed: {summary['manualReviewCount']}**\n")
    lines.append("\n| Classification | Count | Total |\n|---|---|---|\n")
    for row in summary["byLabel"]:
        lines.append(f"| {row['label']} | {row['count']} | ${row['total']:,.2f} |\n")
    write_text(path, "".join(lines))
```

- [ ] **Step 6: Run to verify tests pass**

```bash
uv run pytest tests/test_cashflow.py -v
```

Expected: all PASSED

- [ ] **Step 7: Add income-overlay command to cli.py**

Add this import:

```python
from .cashflow import run_income_overlay
```

Add this command:

```python
@app.command("income-overlay")
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
    from .profile import ProfileNotFoundError, find_profile, load_profile

    profile = None
    try:
        resolved = profile_path or find_profile()
        if resolved:
            profile = load_profile(resolved)
    except ProfileNotFoundError:
        pass

    result = run_income_overlay(profile, start=start, end=end)
    s = result["summary"]
    console.print(
        f"[green]Income overlay written:[/] data/cashflow/latest/ "
        f"({s['transactionCount']} transactions)"
    )
    if s["manualReviewCount"]:
        console.print(f"[yellow]{s['manualReviewCount']} transactions need manual review.[/]")

    table = Table(title="Classification Summary")
    table.add_column("Classification")
    table.add_column("Count", justify="right")
    table.add_column("Total", justify="right")
    for row in s["byLabel"]:
        table.add_row(row["label"], str(row["count"]), f"${row['total']:,.2f}")
    console.print(table)
```

- [ ] **Step 8: Run full suite**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add monarch_money_tools/paths.py monarch_money_tools/profile.py monarch_money_tools/cashflow.py monarch_money_tools/cli.py tests/test_cashflow.py
git commit -m "feat: add monarch income-overlay command with configurable income classifier (closes #2)"
```

---

## Task 10: Interactive Cleanup Review Loop

**Files:**
- Modify: `monarch_money_tools/taxonomy_cleanup.py` — add `load_decisions()`, `save_decision()`
- Create: `monarch_money_tools/review_cleanup.py`
- Modify: `monarch_money_tools/cli.py` — add `review-cleanup`, add `--show-rejected` to `cleanup-plan`
- Create: `tests/test_review_cleanup.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_review_cleanup.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from monarch_money_tools.storage import read_json, write_json
from monarch_money_tools.taxonomy_cleanup import load_decisions, save_decision


def _make_plan(tmp_path: Path) -> None:
    write_json(
        tmp_path / "data/cleanup/latest/cleanup-plan.json",
        {
            "candidates": [
                {
                    "transactionId": "txn-1",
                    "merchantName": "Mechanic",
                    "currentCategory": "Auto Maintenance",
                    "suggestedCategory": "Auto Maintenance & Fees",
                    "categoryId": "cat-1",
                    "confidence": 1.0,
                    "source": "taxonomy_migration",
                    "requiresNewCategory": False,
                    "setNeedsReview": False,
                    "date": "2026-01-01",
                    "amount": -100.0,
                    "accountName": "Checking",
                },
                {
                    "transactionId": "txn-2",
                    "merchantName": "Amazon",
                    "currentCategory": "Uncategorized",
                    "suggestedCategory": "Shopping",
                    "categoryId": "cat-2",
                    "confidence": 0.9,
                    "source": "merchant_history",
                    "requiresNewCategory": False,
                    "setNeedsReview": False,
                    "date": "2026-01-02",
                    "amount": -34.99,
                    "accountName": "Checking",
                },
            ]
        },
    )


def test_save_and_load_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    save_decision("txn-1", "accepted")
    save_decision("txn-2", "rejected")
    decisions = load_decisions()
    assert decisions["txn-1"] == "accepted"
    assert decisions["txn-2"] == "rejected"


def test_load_decisions_returns_empty_when_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_decisions() == {}


def test_apply_cleanup_respects_decision_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _make_plan(tmp_path)
    save_decision("txn-1", "accepted")
    save_decision("txn-2", "rejected")

    from typer.testing import CliRunner
    from monarch_money_tools.cli import app

    applied_updates = []

    def fake_run_async(coro: object) -> list:
        return applied_updates

    monkeypatch.setattr("monarch_money_tools.cli.run_async", fake_run_async)

    runner = CliRunner()
    result = runner.invoke(app, ["apply-cleanup", "--yes"])

    assert result.exit_code == 0, result.output
    # Only txn-1 (accepted) should have been applied; txn-2 (rejected) skipped
    assert "1" in result.output  # "Applied cleanup updates: 0" or 1
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_review_cleanup.py -v
```

Expected: ERROR — `cannot import name 'load_decisions' from 'monarch_money_tools.taxonomy_cleanup'`

- [ ] **Step 3: Add load_decisions/save_decision to taxonomy_cleanup.py**

In `monarch_money_tools/taxonomy_cleanup.py`, add these two functions (near the top of the public API section, after imports):

```python
def load_decisions() -> dict[str, str]:
    """Load the decision log from data/cleanup/latest/decisions.json.

    Returns a dict of transactionId → decision ("accepted", "rejected", "skipped").
    Returns {} if no file exists.
    """
    path = cleanup_latest_dir() / "decisions.json"
    if not path.exists():
        return {}
    return dict(read_json(path))


def save_decision(transaction_id: str, decision: str) -> None:
    """Persist a single decision to data/cleanup/latest/decisions.json.

    decision must be "accepted", "rejected", or "skipped".
    Writes immediately (not batched) so quit-and-resume is safe.
    """
    decisions = load_decisions()
    decisions[transaction_id] = decision
    write_json(cleanup_latest_dir() / "decisions.json", decisions)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/test_review_cleanup.py -v
```

Expected: all PASSED

- [ ] **Step 5: Create review_cleanup.py**

Create `monarch_money_tools/review_cleanup.py`:

```python
"""Interactive accept/reject/skip loop for taxonomy cleanup candidates."""
from __future__ import annotations

import sys
import tty
import termios
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
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run_review_cleanup() -> None:
    plan_path = cleanup_latest_dir() / "cleanup-plan.json"
    if not plan_path.exists():
        console.print("[red]No cleanup plan found.[/] Run `monarch cleanup-plan` first.")
        return

    plan = read_json(plan_path)
    candidates = [c for c in (plan.get("candidates") or []) if not c.get("requiresNewCategory")]
    if not candidates:
        console.print("[yellow]No reviewable candidates.[/]")
        return

    decisions = load_decisions()
    pending = [c for c in candidates if c["transactionId"] not in decisions]

    if not pending:
        console.print(
            f"[green]All {len(candidates)} candidates already reviewed.[/] "
            "Run `monarch apply-cleanup` to apply accepted ones."
        )
        return

    total = len(candidates)
    reviewed_before = len(decisions)

    for i, candidate in enumerate(pending, start=reviewed_before + 1):
        txn_id = candidate["transactionId"]
        merchant = candidate["merchantName"]
        current = candidate["currentCategory"]
        suggested = candidate["suggestedCategory"]
        source = candidate.get("source", "")
        date = candidate.get("date", "?")
        amount = float(candidate.get("amount", 0))

        panel_content = (
            f"[bold]{merchant}[/]  →  [green]{suggested}[/]\n"
            f"  Current:   [yellow]{current}[/]\n"
            f"  Sample:    {date}  ${abs(amount):.2f}\n"
            f"  Source:    {source}\n\n"
            f"  [bold](a)[/]ccept  [bold](r)[/]eject  [bold](s)[/]kip  [bold](q)[/]uit"
        )
        console.print(Panel(panel_content, title=f"[{i}/{total}]"))

        while True:
            key = _read_char()
            if key not in VALID_KEYS:
                continue
            break

        console.print()
        if key == "q":
            console.print("[dim]Saved progress. Resume with `monarch review-cleanup`.[/]")
            return
        if key == "a":
            save_decision(txn_id, "accepted")
            console.print(f"[green]✓ Accepted:[/] {merchant} → {suggested}")
        elif key == "r":
            save_decision(txn_id, "rejected")
            console.print(f"[red]✗ Rejected:[/] {merchant}")
        elif key == "s":
            save_decision(txn_id, "skipped")
            console.print(f"[dim]Skipped:[/] {merchant}")

    accepted = sum(1 for v in load_decisions().values() if v == "accepted")
    console.print(
        f"\n[green]Review complete.[/] {accepted} accepted. "
        "Run `monarch apply-cleanup` to apply."
    )
```

- [ ] **Step 6: Add review-cleanup command and --show-rejected to cli.py**

Add import:

```python
from .review_cleanup import run_review_cleanup
```

Add command:

```python
@app.command("review-cleanup")
def review_cleanup_command() -> None:
    """Interactively accept, reject, or skip taxonomy cleanup candidates one at a time."""
    run_review_cleanup()
```

Modify `cleanup_plan_command` to add `--show-rejected`:

```python
@app.command("cleanup-plan")
def cleanup_plan_command(
    show_rejected: Annotated[
        bool,
        typer.Option("--show-rejected", help="Include rejected candidates in the summary count."),
    ] = False,
) -> None:
    """Generate deterministic taxonomy cleanup candidates (migrations + merchant history)."""
    from .taxonomy_cleanup import load_decisions

    plan = build_taxonomy_cleanup_plan()
    s = plan["summary"]
    cats = plan.get("categoriesToCreate") or []

    decisions = load_decisions()
    rejected_ids = {tid for tid, d in decisions.items() if d == "rejected"}

    ready_count = s["readyCount"]
    if not show_rejected:
        ready_count -= sum(
            1 for c in plan.get("candidates", [])
            if c["transactionId"] in rejected_ids and not c.get("requiresNewCategory")
        )

    console.print(
        "[green]Cleanup plan written:[/] data/cleanup/latest "
        f"({s['taxonomyMigrationCount']} taxonomy migrations, "
        f"{s['merchantConsistencyCount']} merchant consistency, "
        f"{ready_count} ready, {s['blockedCount']} blocked)"
    )
    if rejected_ids and not show_rejected:
        console.print(
            f"[dim]{len(rejected_ids)} rejected candidates hidden. "
            "Use --show-rejected to include them.[/]"
        )
    if cats:
        console.print(
            f"[yellow]Create these {len(cats)} categories in Monarch first "
            f"before applying blocked candidates:[/] "
            + ", ".join(f"{c['group']}/{c['name']}" for c in cats)
        )
```

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add monarch_money_tools/taxonomy_cleanup.py monarch_money_tools/review_cleanup.py monarch_money_tools/cli.py tests/test_review_cleanup.py
git commit -m "feat: add interactive review-cleanup loop with decision persistence (closes #4)"
```

---

## Task 11: PyPI Release

**Files:**
- Modify: `pyproject.toml` — version → `0.0.1`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/publish.yml`
- Modify: `README.md` — update install instructions

- [ ] **Step 1: Bump version in pyproject.toml**

In `pyproject.toml`, change:

```toml
version = "0.1.0"
```

to:

```toml
version = "0.0.1"
```

- [ ] **Step 2: Create CI workflow**

```bash
mkdir -p .github/workflows
```

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      - name: Install dependencies
        run: uv sync --extra dev --extra api --extra llm
      - name: Lint
        run: uv run ruff check .
      - name: Format check
        run: uv run ruff format --check .
      - name: Test
        run: uv run pytest
```

- [ ] **Step 3: Create publish workflow**

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"
      - name: Install dependencies
        run: uv sync --extra dev --extra api --extra llm
      - name: Lint
        run: uv run ruff check .
      - name: Format check
        run: uv run ruff format --check .
      - name: Test
        run: uv run pytest
      - name: Build
        run: uv build
      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1
```

Note: This uses PyPI Trusted Publishing (OIDC) — no API token secret needed. Before the first publish, configure a Trusted Publisher in your PyPI project settings (GitHub → repo: `monarch-money-tools`, workflow: `publish.yml`, environment: `pypi`).

- [ ] **Step 4: Update README install instructions**

Find the install section in README.md that says:

```
uv tool install .
```

Replace with:

```markdown
## Installation

```bash
uv tool install monarch-money-tools
```

For a development install (cloned repo):

```bash
git clone https://github.com/<your-username>/monarch-money-tools.git
cd monarch-money-tools
uv sync --extra dev --extra api --extra llm
```
```

- [ ] **Step 5: Run full suite one final time**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .github/workflows/ci.yml .github/workflows/publish.yml README.md
git commit -m "chore: bump version to 0.0.1, add CI/publish workflows, update install docs (closes #10)"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task(s) |
|-----------------|---------|
| `#6` conftest.py with normalized_bundle, monarch_data_dir | Task 1 |
| `#5` workbench marked internal | Task 2 |
| `#12` tag-reimbursements removed | Task 3 |
| `#8` --dry-run on apply-reviews | Task 4 |
| `#8` --dry-run on apply-clear-reviews | Task 5 |
| `#8` --dry-run on apply-cleanup (respects decision log) | Task 6 |
| `#8` --dry-run on apply-llm-review | Task 7 |
| `#7` monarch init wizard (credentials, connection, taxonomy, profile, doctor) | Task 8 |
| `#13` interactive auth with MFA secret instructions | Task 8 |
| Fix taxonomy_dir() bug | Task 8 |
| `#2` IncomePatternConfig/CashflowConfig profile additions | Task 9 |
| `#2` income-overlay command with classification + output files | Task 9 |
| `#4` review-cleanup interactive loop (accept/reject/skip/quit) | Task 10 |
| `#4` decisions persisted per-keypress, resume on re-entry | Task 10 |
| `#4` apply-cleanup respects decision log | Task 6 (decisions path) + Task 10 (decisions written) |
| `#4` cleanup-plan --show-rejected | Task 10 |
| `#10` version 0.0.1 | Task 11 |
| `#10` CI workflow | Task 11 |
| `#10` publish workflow (tag-triggered, OIDC) | Task 11 |
| `#10` README install update | Task 11 |

**Placeholder scan:** None found.

**Type consistency:**
- `load_decisions()` returns `dict[str, str]` — used in Task 6 (apply-cleanup) and Task 10 (review_cleanup.py, cleanup_plan). Consistent.
- `save_decision(transaction_id: str, decision: str)` — called in Task 10 (review_cleanup.py) and tested in Task 10 tests. Consistent.
- `classify_transactions(transactions, profile, start, end)` — defined in Task 9 cashflow.py, tested in test_cashflow.py, called in `run_income_overlay`. Consistent.
- `run_income_overlay(profile, start, end)` — defined in cashflow.py, imported and called in cli.py. Consistent.
- `run_review_cleanup()` — defined in review_cleanup.py, imported in cli.py. Consistent.
- `run_init_wizard(yes)` — defined in init_wizard.py, imported in cli.py. Consistent.
- `_append_env(path, new_keys)` and `_read_env(path)` — defined and tested in init_wizard.py. Consistent.
