# Codebase Refactor Design

**Date:** 2026-05-26  
**Scope:** Comprehensive — shared utilities, module merge, CLI split, business logic extraction

---

## Goals

1. Eliminate duplicated utility definitions (`JsonObject`, `now_iso`, `round2`, bundle-loading pattern) that are copy-pasted across 6+ modules.
2. Remove `analyzer.py` as an unnecessary thin wrapper over `analysis.py`.
3. Split `cli.py` (1303 lines) into focused command modules organized by sub-command group.
4. Move substantial business logic out of command handlers back into their domain modules.

---

## Section 1: Shared Utilities in `storage.py`

### Problem

Six modules each define `JsonObject = dict[str, Any]`.  
Two modules define an identical `round2()`.  
Five modules define a private `now_iso()` / `_now_iso()` / `iso_datetime()` — all return the same string.  
Seven places repeat the same 4-line "check bundle path exists → raise FileNotFoundError → read JSON" pattern.

### Solution

Add to `storage.py`:

```python
JsonObject = dict[str, Any]               # remove from all other modules

def now_iso() -> str:                     # canonical; replaces all variants
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

def round2(value: float) -> float:        # remove from analysis.py, review.py
    return round(value * 100) / 100

def load_bundle() -> JsonObject:          # raises FileNotFoundError if missing
    path = normalized_latest_dir() / "bundle.json"
    if not path.exists():
        raise FileNotFoundError(
            "No normalized bundle found. Run `monarch pull` or `monarch import <csv>` first."
        )
    return read_json(path)
```

All modules remove their local definitions and import from `storage`.  
`exporter.py`'s private `iso_datetime()` is replaced by `now_iso()`.

**Behavior change:** None.

---

## Section 2: Merge `analyzer.py` into `analysis.py`

### Problem

`analyzer.py` (40 lines) contains only `run_analyze()`, which calls `prepare_analysis()` from `analysis.py`, writes three JSON output files, and returns. There is no logic that justifies a separate file.

### Solution

- Move `run_analyze()` to the bottom of `analysis.py`.
- Delete `analyzer.py`.
- Update the one import site in `cli.py`: `from .analysis import run_analyze`.

**Behavior change:** None.

---

## Section 3: Split `cli.py` by Command Group

### Problem

`cli.py` at 1303 lines handles 30+ commands across 5 command groups, plus shared helpers. The dry-run table is built inline 4 times with near-identical column sets.

### Solution

**New layout:**

```
monarch_money_tools/
  cli.py             — app + sub-app definitions; run_async; exit_with_file_error;
                       console; _format_amount; registers 6 primary flat shortcuts
  cmd/
    __init__.py
    _utils.py        — print_dry_run_table (shared by all apply commands)
    data.py          — data_app: import, analyze, report, run, pull, backup,
                       recurring, income-overlay, doctor
    review.py        — review_app: plan, apply, clear-plan, clear-apply,
                       llm, llm-apply, bulk-clear-reviews
    cleanup.py       — cleanup_app: plan, review, apply
    rules.py         — rules_app: suggest, apply, push, list, delete
    misc.py          — top-level app: init, init-profile, retire, portfolio
```

**Dual-registration simplification:**  
Each `cmd/*.py` creates its own `typer.Typer()` sub-app and registers commands directly on it. `cli.py` calls `app.add_typer(...)` for each. For the 6 primary flat shortcuts (`doctor`, `import`, `run`, `pull`, `init`, `retire`), `cli.py` imports the command function from the relevant cmd module and registers it on the top-level `app`.  
`_register_grouped_aliases()` and `_hide_secondary_flat_commands()` are deleted.

**Dry-run table consolidation:**  
`cmd/_utils.py` provides:

```python
def print_dry_run_table(
    console: Console,
    updates: list[dict],
    columns: list[tuple[str, str | None]],  # (header, justify)
    rows_fn: Callable[[dict], tuple],
    title: str,
    limit: int = 50,
) -> None: ...
```

The 4 near-identical table blocks in the apply commands are replaced by calls to this helper.

---

## Section 4: Business Logic Out of Command Handlers

### Problem A — `apply_cleanup_command` (73 lines of filtering logic)

The command handler filters candidates by decisions, `skip_blocked`, `source`, and `limit`. This filtering belongs in the domain module.

**Solution:** Add to `taxonomy_cleanup.py`:

```python
def filter_cleanup_candidates(
    plan: JsonObject,
    decisions: dict[str, str],
    skip_blocked: bool,
    source: str | None,
    limit: int | None,
) -> list[JsonObject]: ...
```

The command handler calls `filter_cleanup_candidates(...)`, then either dry-runs or applies.

### Problem B — `push_rule_command` inline async function

A 30-line `async def _push()` lives inside the command function. It looks up a category ID via the live API and builds the Monarch rule payload.

**Solution:** Extract to `rules.py`:

```python
def build_push_rule_payload(rule: JsonObject, category_id: str | None) -> dict: ...
```

The async category-ID lookup (one `client.get_transaction_categories()` call) remains inside the command handler in `cmd/rules.py` — it's a live-API concern that belongs at the CLI layer. The command calls `build_push_rule_payload` with the resolved ID and passes the result to `client.create_transaction_rule`.

### Problem C — Double plan-read in apply commands

`apply_clear_reviews_command` reads the plan, filters updates, then calls `apply_clear_review_plan(limit=limit)` which reads the plan *again* from disk. Same pattern in `apply_reviews_command`.

**Solution:** Change `apply_clear_review_plan` and `apply_review_plan` in `review.py` to accept pre-filtered updates directly:

```python
async def apply_clear_review_plan(updates: list[JsonObject]) -> JsonObject: ...
async def apply_review_plan(updates: list[JsonObject]) -> JsonObject: ...
```

The command handler filters once, passes the result, no second disk read.

---

## File Changes Summary

| File | Action |
|---|---|
| `storage.py` | Add `JsonObject`, `now_iso`, `round2`, `load_bundle` |
| `analysis.py` | Receive `run_analyze`; remove local `JsonObject`, `now_iso`, `round2` |
| `analyzer.py` | **Delete** |
| `review.py` | Remove local `JsonObject`, `now_iso`, `round2`; change apply signatures |
| `rules.py` | Remove local `JsonObject`; add `build_push_rule_payload` |
| `taxonomy_cleanup.py` | Remove local `JsonObject`, `_now_iso`; add `filter_cleanup_candidates` |
| `llm_review.py` | Remove local `JsonObject`, `_now_iso` |
| `reporter.py` | Remove local `JsonObject` |
| `exporter.py` | Remove `iso_datetime`, use `now_iso` from storage |
| `cli.py` | Slim to app skeleton + 6 flat shortcuts |
| `cmd/__init__.py` | **New** (empty) |
| `cmd/_utils.py` | **New** — `print_dry_run_table` |
| `cmd/data.py` | **New** — data_app commands |
| `cmd/review.py` | **New** — review_app commands |
| `cmd/cleanup.py` | **New** — cleanup_app commands |
| `cmd/rules.py` | **New** — rules_app commands |
| `cmd/misc.py` | **New** — misc top-level commands |

---

## Testing Strategy

- All 15 existing tests must pass before and after each section.
- Sections are independent enough to implement and verify one at a time.
- Order: Section 1 → Section 2 → Section 3 → Section 4.
