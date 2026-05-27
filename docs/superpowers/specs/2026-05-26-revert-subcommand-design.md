# Revert Subcommand Design

**Date:** 2026-05-26  
**Status:** Approved  
**Scope:** Add `revert` subcommands to all command groups that have `plan` + `apply`

---

## Overview

Monarch Money Tools follows a three-step lifecycle for all mutations:

```
plan  →  apply  →  revert
```

- **plan** generates a human-readable plan file and shows a dry-run table. No API calls.
- **apply** reads the plan, calls the Monarch API, and writes a **revert receipt** capturing exactly what changed.
- **revert** reads the latest receipt and sends the before-state back to the API, undoing the apply.

This document specifies the receipt format, the new `revert.py` module, the changes to existing apply functions, and the new `revert` subcommands.

See also: [`docs/patterns/plan-apply-revert.md`](../../patterns/plan-apply-revert.md) for the canonical pattern reference.

---

## Receipt Format & Storage Layout

### Directory structure

Each command group gets its own `revert/` directory alongside `latest/`:

```
data/
  review/
    latest/          ← existing plan files
    revert/
      revert-20260526-143200.json
      revert-20260526-151700.json
  cleanup/
    latest/
    revert/
      revert-20260526-160000.json
  rules/
    latest/
    revert/
      revert-20260526-170000.json
```

Receipts are never deleted automatically. A receipt marked `reverted: true` is skipped by `find_latest_receipt`; running `revert` again picks the next-oldest.

### Receipt schema

```json
{
  "createdAt": "2026-05-26T14:32:00Z",
  "command": "monarch review apply",
  "reverted": false,
  "operations": [
    {
      "type": "update_transaction",
      "entityId": "txn-abc123",
      "merchantName": "Starbucks",
      "before": {
        "categoryId": "cat-111",
        "categoryName": "Uncategorized",
        "needsReview": true
      },
      "after": {
        "categoryId": "cat-222",
        "categoryName": "Coffee Shops",
        "needsReview": false
      }
    }
  ]
}
```

For `rules push`, the operation type differs — no `before` (the rule didn't exist):

```json
{
  "type": "create_rule",
  "entityId": "monarch-rule-xyz",
  "ruleName": "Starbucks → Coffee Shops",
  "before": null,
  "after": { "monarchRuleId": "monarch-rule-xyz" }
}
```

### Operation types

| `type` | Inverted by |
|---|---|
| `update_transaction` | Re-send `before` fields via `update_transaction` API |
| `create_rule` | Call `delete_monarch_rule(entityId)` |

New operation types are registered by adding an inversion handler in `revert.py`. Nothing else needs to change.

---

## New `paths.py` helpers

Three new path helpers, parallel to existing `review_latest_dir()`, `cleanup_latest_dir()`, `rules_latest_dir()`:

```python
def review_revert_dir() -> Path:
    return data_dir() / "review" / "revert"

def cleanup_revert_dir() -> Path:
    return data_dir() / "cleanup" / "revert"

def rules_revert_dir() -> Path:
    return data_dir() / "rules" / "revert"
```

---

## New `revert.py` module

```
monarch_money_tools/
  revert.py   ← NEW
```

### Public API

```python
def snapshot_transaction_before(txn_id: str, bundle: dict) -> dict:
    """
    Look up txn_id in bundle["transactions"] and return its current field values
    as a before-dict: {categoryId, categoryName, needsReview}.

    The categoryId is resolved from bundle["categories"] by matching categoryName.
    Returns {} if the transaction is not found in the bundle (apply will still
    proceed; revert will skip that operation with a warning).
    """

def build_revert_receipt(command: str, operations: list[dict]) -> dict:
    """
    Construct the receipt envelope:
      { createdAt, command, reverted: False, operations }
    """

def write_revert_receipt(revert_dir: Path, receipt: dict) -> Path:
    """
    Write receipt to revert_dir/revert-<ts>.json.
    Creates the directory if it does not exist.
    Returns the path written.
    """

def find_latest_receipt(revert_dir: Path) -> Path | None:
    """
    Return the path of the most recent receipt in revert_dir where reverted == False.
    Returns None if no eligible receipt exists.
    """

async def execute_revert(receipt_path: Path) -> dict:
    """
    Load the receipt at receipt_path, dispatch each operation to its inversion
    handler, mark receipt reverted=True, overwrite the file.
    Returns { revertedAt, revertedCount, skippedCount }.
    """
```

### Inversion dispatch (private)

```python
async def _invert_operation(op: dict) -> bool:
    match op["type"]:
        case "update_transaction":
            # re-send op["before"] fields to the API
            ...
            return True
        case "create_rule":
            # delete the rule that was created
            await delete_monarch_rule(op["entityId"])
            return True
        case _:
            console.print(f"[yellow]Unknown operation type '{op['type']}', skipping.[/]")
            return False
```

### Extending for new field types

`snapshot_transaction_before` currently captures `{categoryId, categoryName, needsReview}`. To add a new field (e.g. `notes`):

1. Add `"notes": txn.get("notes")` to the snapshot dict in `revert.py`
2. Add `"notes": update.get("notes")` to the `after` dict in the relevant apply function
3. Add `"notes": before.get("notes")` to the API call in `_invert_operation`

No receipt format changes, no new operation types needed.

---

## Apply-side changes

Each apply function is modified to:
1. Load the bundle before sending API calls
2. Build `before` + `after` dicts per operation
3. Call `write_revert_receipt` after all API calls succeed

**Pattern (shown for `apply_review_plan`):**

```python
async def apply_review_plan(updates: list[JsonObject]) -> JsonObject:
    bundle = load_bundle()
    client = await create_monarch_client()
    operations = []
    results = []

    for update in updates:
        before = snapshot_transaction_before(update["transactionId"], bundle)
        after = {
            "categoryId": update.get("categoryId"),
            "categoryName": update.get("suggestedCategory"),
            "needsReview": update.get("setNeedsReview"),
        }
        response = await client.update_transaction(
            transaction_id=str(update["transactionId"]),
            category_id=string_or_none(update.get("categoryId")),
            needs_review=update.get("setNeedsReview"),
        )
        results.append(response)
        operations.append({
            "type": "update_transaction",
            "entityId": update["transactionId"],
            "merchantName": update.get("merchantName", ""),
            "before": before,
            "after": after,
        })

    receipt = build_revert_receipt("monarch review apply", operations)
    write_revert_receipt(review_revert_dir(), receipt)
    return {"appliedAt": now_iso(), "requestedCount": len(updates), "results": results}
```

**Apply functions to modify:**

| Function | Module | Receipt dir |
|---|---|---|
| `apply_review_plan` | `review.py` | `review_revert_dir()` |
| `apply_clear_review_plan` | `review.py` | `review_revert_dir()` |
| `apply_llm_review` (via `apply_transaction_updates`) | `llm_review.py` | `review_revert_dir()` |
| `apply_cleanup_plan` | `taxonomy_cleanup.py` | `cleanup_revert_dir()` |
| `apply_rules_plan` | `rules.py` | `rules_revert_dir()` |
| `rules push` handler | `cmd/rules.py` | `rules_revert_dir()` (type: `create_rule`) |

Note: `apply_transaction_updates` in `monarch_api.py` is a low-level helper shared by multiple callers. Receipt writing happens at the domain-module level (one level up), not in this shared helper, so each command gets its own correctly-labeled receipt.

---

## New `revert` subcommands

Three new subcommands with identical shape:

```
monarch review  revert [--receipt <path>] [--yes] [--dry-run]
monarch cleanup revert [--receipt <path>] [--yes] [--dry-run]
monarch rules   revert [--receipt <path>] [--yes] [--dry-run]
```

**Behavior:**

1. No `--receipt` → find the latest non-reverted receipt via `find_latest_receipt()`; exit with a clear message if none found
2. Show a dry-run table of what will be restored (same style as apply tables, columns: Merchant, From Category, To Category, Needs Review)
3. Prompt for confirmation (skipped with `--yes`); `--dry-run` exits after showing the table
4. Call `execute_revert(receipt_path)` — handles API calls and marks receipt `reverted: true`
5. Print summary: `Reverted N operations` (or detail on any skipped)

**Example output:**
```
$ monarch review revert
Using receipt: data/review/revert/revert-20260526-143200.json (42 operations)

  Merchant          From Category    To Category    Needs Review
  ──────────────────────────────────────────────────────────────
  Starbucks         Coffee Shops  →  Uncategorized  ✓
  Amazon Prime      Subscriptions →  Uncategorized  ✓
  ...

Revert 42 operations to Monarch? [y/N]: y
Reverted: 42 operations
```

---

## Consistency audit & fixes

Current command naming against the plan→apply→revert pattern:

| Group | Plan step | Apply step | Issue |
|---|---|---|---|
| `cleanup` | `cleanup plan` | `cleanup apply` | ✅ consistent |
| `review` | `review plan` | `review apply` | ✅ consistent |
| `review` | `review clear-plan` | `review clear-apply` | ✅ consistent |
| `review` | `review llm` | `review llm-apply` | ⚠️ plan step should be `review llm-plan` |
| `rules` | `rules suggest` | `rules apply` | ⚠️ plan step named `suggest`, not `plan` |
| `rules` | *(none)* | `rules push` | ℹ️ intentionally atomic; emits receipt only |
| `review` | *(combined)* | `review bulk-clear` | ℹ️ combined; emits receipt via `apply_clear_review_plan` |

**Renames included in this implementation:**
- `review llm` → `review llm-plan` (keep `llm` as a deprecated alias for one release, print a deprecation warning)

**Left as-is with rationale:**
- `rules suggest` — "suggest" is domain-appropriate and there is no global `rules plan` concept; `rules apply` applies the suggestions file, which is close enough
- `rules push` — intentionally atomic (no plan file makes sense for a single rule push); will emit a receipt so `rules revert` can undo it
- `review bulk-clear` — intentionally combines steps for a common quick-clear workflow; emits a receipt via the shared `apply_clear_review_plan` call

---

## Documentation artifacts

**`docs/patterns/plan-apply-revert.md`** — canonical pattern reference:
- Lifecycle diagram and description
- Receipt format reference
- Full command inventory (which step each command represents)
- "Adding a new operation type" guide
- "Extending for new fields" guide

**`CLAUDE.md` update** — add to the Key Invariants section:
> **Plan / Apply / Revert.** Every mutation follows plan → apply → revert. `plan` writes a human-readable plan file. `apply` reads the plan, calls the API, and writes a timestamped revert receipt at `data/<group>/revert/`. `revert` reads the latest receipt and restores the before-state. See `docs/patterns/plan-apply-revert.md`.

---

## Testing

- Unit tests for `revert.py`: `snapshot_transaction_before`, `build_revert_receipt`, `write_revert_receipt`, `find_latest_receipt` — all using fixtures, no live API
- Integration-style test for `execute_revert` using a mock API client
- Existing apply tests remain valid; they gain an assertion that a receipt file was written to the expected path
