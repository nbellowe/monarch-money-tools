# Revert Subcommand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `revert` subcommand to every command group that has `plan` + `apply`, backed by timestamped revert receipts emitted by each `apply` call.

**Architecture:** A new `revert.py` module provides pure helper functions (`snapshot_transaction_before`, `build_revert_receipt`, `write_revert_receipt`, `find_latest_receipt`) and an async dispatcher (`execute_revert`). Each `apply` function is modified to snapshot the before-state from the normalized bundle and write a timestamped receipt to `data/<group>/revert/`. Three new `revert` subcommands read those receipts and invert the operations via the Monarch API.

**Tech Stack:** Python 3.12, Typer (CLI), Pydantic-free plain dicts, `unittest.mock.AsyncMock` for async API tests, `pytest` + `tmp_path` for file-system tests.

**Spec:** `docs/superpowers/specs/2026-05-26-revert-subcommand-design.md`  
**Pattern reference:** `docs/patterns/plan-apply-revert.md`

---

## File Map

| File | Change |
|---|---|
| `monarch_money_tools/paths.py` | Add `review_revert_dir()`, `cleanup_revert_dir()`, `rules_revert_dir()` |
| `monarch_money_tools/revert.py` | **NEW** — all receipt logic + execute_revert |
| `monarch_money_tools/review.py` | Modify `apply_review_plan`, `apply_clear_review_plan` to emit receipts |
| `monarch_money_tools/llm_review.py` | Extract `apply_llm_review_plan` + emit receipt |
| `monarch_money_tools/taxonomy_cleanup.py` | Extract `apply_cleanup_plan` + emit receipt |
| `monarch_money_tools/rules.py` | Modify `apply_rules_plan` to emit receipt |
| `monarch_money_tools/cmd/review.py` | Add `revert` subcommand; update llm-apply to use extracted fn; rename `llm` → `llm-plan` |
| `monarch_money_tools/cmd/cleanup.py` | Add `revert` subcommand; update apply to use extracted fn |
| `monarch_money_tools/cmd/rules.py` | Add `revert` subcommand; emit receipt from `push` |
| `CLAUDE.md` | Add Plan/Apply/Revert invariant |
| `tests/test_revert.py` | **NEW** — all revert.py unit tests |
| `tests/test_review.py` | Update existing apply tests to patch `load_bundle` |

---

## Task 1: Add path helpers to `paths.py`

**Files:**
- Modify: `monarch_money_tools/paths.py`
- Test: `tests/test_revert.py` (create now, we'll add more tests in later tasks)

- [ ] **Step 1: Write the failing test**

Create `tests/test_revert.py`:

```python
from __future__ import annotations

from pathlib import Path

from monarch_money_tools.paths import cleanup_revert_dir, review_revert_dir, rules_revert_dir


def test_revert_dir_helpers_are_under_data(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert review_revert_dir() == tmp_path / "data" / "review" / "revert"
    assert cleanup_revert_dir() == tmp_path / "data" / "cleanup" / "revert"
    assert rules_revert_dir() == tmp_path / "data" / "rules" / "revert"
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
uv run pytest tests/test_revert.py::test_revert_dir_helpers_are_under_data -v
```

Expected: `FAILED` — `ImportError: cannot import name 'review_revert_dir'`

- [ ] **Step 3: Add the path helpers**

In `monarch_money_tools/paths.py`, append after `rules_latest_dir()`:

```python
def review_revert_dir() -> Path:
    return data_dir() / "review" / "revert"


def cleanup_revert_dir() -> Path:
    return data_dir() / "cleanup" / "revert"


def rules_revert_dir() -> Path:
    return data_dir() / "rules" / "revert"
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
uv run pytest tests/test_revert.py -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add monarch_money_tools/paths.py tests/test_revert.py
git commit -m "feat: add review/cleanup/rules revert dir path helpers"
```

---

## Task 2: Core `revert.py` pure functions

**Files:**
- Create: `monarch_money_tools/revert.py`
- Modify: `tests/test_revert.py`

These four functions have no API calls — they work only with dicts and the filesystem.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_revert.py`:

```python
import json

from monarch_money_tools.revert import (
    build_revert_receipt,
    find_latest_receipt,
    snapshot_transaction_before,
    write_revert_receipt,
)
from monarch_money_tools.storage import read_json


_MINI_BUNDLE = {
    "transactions": [
        {"id": "txn-1", "categoryName": "Uncategorized", "needsReview": True},
        {"id": "txn-2", "categoryName": "Coffee Shops", "needsReview": False},
    ],
    "categories": [
        {"id": "cat-0", "name": "Uncategorized"},
        {"id": "cat-1", "name": "Coffee Shops"},
    ],
}


def test_snapshot_returns_before_fields() -> None:
    before = snapshot_transaction_before("txn-1", _MINI_BUNDLE)
    assert before == {"categoryId": "cat-0", "categoryName": "Uncategorized", "needsReview": True}


def test_snapshot_returns_empty_for_missing_transaction() -> None:
    before = snapshot_transaction_before("txn-unknown", _MINI_BUNDLE)
    assert before == {}


def test_build_revert_receipt_shape() -> None:
    ops = [{"type": "update_transaction", "entityId": "txn-1"}]
    receipt = build_revert_receipt("monarch review apply", ops)
    assert receipt["command"] == "monarch review apply"
    assert receipt["reverted"] is False
    assert receipt["operations"] == ops
    assert "createdAt" in receipt


def test_write_revert_receipt_creates_timestamped_file(tmp_path) -> None:
    receipt = build_revert_receipt("monarch review apply", [])
    path = write_revert_receipt(tmp_path, receipt)
    assert path.exists()
    assert path.name.startswith("revert-")
    assert path.suffix == ".json"
    stored = read_json(path)
    assert stored["command"] == "monarch review apply"


def test_find_latest_receipt_skips_reverted(tmp_path) -> None:
    old_receipt = build_revert_receipt("monarch review apply", [])
    old_receipt["reverted"] = True
    (tmp_path / "revert-2026-05-26T10-00-00Z.json").write_text(
        json.dumps(old_receipt), encoding="utf-8"
    )

    new_receipt = build_revert_receipt("monarch review apply", [])
    new_receipt["reverted"] = False
    new_path = tmp_path / "revert-2026-05-26T11-00-00Z.json"
    new_path.write_text(json.dumps(new_receipt), encoding="utf-8")

    found = find_latest_receipt(tmp_path)
    assert found == new_path


def test_find_latest_receipt_returns_none_when_all_reverted(tmp_path) -> None:
    receipt = build_revert_receipt("monarch review apply", [])
    receipt["reverted"] = True
    (tmp_path / "revert-2026-05-26T10-00-00Z.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    assert find_latest_receipt(tmp_path) is None


def test_find_latest_receipt_returns_none_for_empty_dir(tmp_path) -> None:
    assert find_latest_receipt(tmp_path) is None


def test_find_latest_receipt_returns_none_for_missing_dir(tmp_path) -> None:
    assert find_latest_receipt(tmp_path / "nonexistent") is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_revert.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'monarch_money_tools.revert'`

- [ ] **Step 3: Create `monarch_money_tools/revert.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from .storage import ensure_dir, now_iso, read_json, timestamp_slug, write_json

JsonObject = dict[str, Any]


def snapshot_transaction_before(txn_id: str, bundle: JsonObject) -> JsonObject:
    """
    Look up txn_id in bundle["transactions"] and return its current field values
    as a before-dict: {categoryId, categoryName, needsReview}.

    categoryId is resolved from bundle["categories"] by matching categoryName.
    Returns {} if the transaction is not found (apply still proceeds; revert
    will skip that operation with a warning).
    """
    cat_by_name: dict[str, str] = {
        str(c.get("name", "")): str(c.get("id", ""))
        for c in (bundle.get("categories") or [])
    }
    txn = next(
        (t for t in (bundle.get("transactions") or []) if str(t.get("id", "")) == str(txn_id)),
        None,
    )
    if txn is None:
        return {}
    category_name = str(txn.get("categoryName") or "")
    return {
        "categoryId": cat_by_name.get(category_name, ""),
        "categoryName": category_name,
        "needsReview": bool(txn.get("needsReview")),
    }


def build_revert_receipt(command: str, operations: list[JsonObject]) -> JsonObject:
    """Construct the receipt envelope: {createdAt, command, reverted: False, operations}."""
    return {
        "createdAt": now_iso(),
        "command": command,
        "reverted": False,
        "operations": operations,
    }


def write_revert_receipt(revert_dir: Path, receipt: JsonObject) -> Path:
    """
    Write receipt to revert_dir/revert-<ts>.json.
    Creates the directory if it does not exist. Returns the path written.
    """
    ensure_dir(revert_dir)
    path = revert_dir / f"revert-{timestamp_slug()}.json"
    write_json(path, receipt)
    return path


def find_latest_receipt(revert_dir: Path) -> Path | None:
    """
    Return the path of the most recent receipt in revert_dir where reverted == False.
    Returns None if the directory does not exist or no eligible receipt is found.
    """
    if not revert_dir.exists():
        return None
    receipts = sorted(revert_dir.glob("revert-*.json"), key=lambda p: p.name, reverse=True)
    for path in receipts:
        try:
            data = read_json(path)
            if not data.get("reverted"):
                return path
        except Exception:
            continue
    return None
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_revert.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run the full test suite to check nothing broke**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/revert.py tests/test_revert.py
git commit -m "feat: add revert.py pure functions (snapshot, build, write, find_latest)"
```

---

## Task 3: `execute_revert` — async inversion dispatcher

**Files:**
- Modify: `monarch_money_tools/revert.py`
- Modify: `tests/test_revert.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_revert.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch

from monarch_money_tools.revert import execute_revert


def test_execute_revert_update_transaction(tmp_path) -> None:
    receipt = build_revert_receipt(
        "monarch review apply",
        [
            {
                "type": "update_transaction",
                "entityId": "txn-1",
                "merchantName": "Starbucks",
                "before": {"categoryId": "cat-0", "categoryName": "Uncategorized", "needsReview": True},
                "after": {"categoryId": "cat-1", "categoryName": "Coffee Shops", "needsReview": False},
            }
        ],
    )
    receipt_path = tmp_path / "revert-test.json"
    write_revert_receipt(tmp_path, receipt)
    receipt_path = find_latest_receipt(tmp_path)

    with patch(
        "monarch_money_tools.revert.apply_transaction_updates", new_callable=AsyncMock
    ) as mock_apply:
        mock_apply.return_value = [{"id": "txn-1"}]
        result = asyncio.run(execute_revert(receipt_path))

    mock_apply.assert_called_once_with(
        [
            {
                "transactionId": "txn-1",
                "merchantName": "Starbucks",
                "suggestedCategory": "Uncategorized",
                "categoryId": "cat-0",
                "setNeedsReview": True,
            }
        ]
    )
    assert result["revertedCount"] == 1
    assert result["skippedCount"] == 0
    updated = read_json(receipt_path)
    assert updated["reverted"] is True
    assert "revertedAt" in updated


def test_execute_revert_create_rule(tmp_path) -> None:
    receipt = build_revert_receipt(
        "monarch rules push",
        [
            {
                "type": "create_rule",
                "entityId": "rule-xyz",
                "ruleName": "Starbucks → Coffee Shops",
                "before": None,
                "after": {"monarchRuleId": "rule-xyz"},
            }
        ],
    )
    write_revert_receipt(tmp_path, receipt)
    receipt_path = find_latest_receipt(tmp_path)

    with patch(
        "monarch_money_tools.revert.delete_monarch_rule", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.return_value = {"deleted": True}
        result = asyncio.run(execute_revert(receipt_path))

    mock_delete.assert_called_once_with("rule-xyz")
    assert result["revertedCount"] == 1
    assert result["skippedCount"] == 0
    updated = read_json(receipt_path)
    assert updated["reverted"] is True


def test_execute_revert_skips_unknown_type(tmp_path) -> None:
    receipt = build_revert_receipt(
        "monarch future apply",
        [{"type": "future_operation", "entityId": "x"}],
    )
    write_revert_receipt(tmp_path, receipt)
    receipt_path = find_latest_receipt(tmp_path)

    result = asyncio.run(execute_revert(receipt_path))
    assert result["revertedCount"] == 0
    assert result["skippedCount"] == 1
    assert read_json(receipt_path)["reverted"] is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_revert.py::test_execute_revert_update_transaction tests/test_revert.py::test_execute_revert_create_rule tests/test_revert.py::test_execute_revert_skips_unknown_type -v
```

Expected: `FAILED` — `ImportError: cannot import name 'execute_revert'`

- [ ] **Step 3: Add `execute_revert` and `_invert_operation` to `revert.py`**

Append to `monarch_money_tools/revert.py` (after `find_latest_receipt`):

```python
async def execute_revert(receipt_path: Path) -> JsonObject:
    """
    Load the receipt at receipt_path, dispatch each operation to its inversion
    handler, mark receipt reverted=True, and overwrite the file.
    Returns {revertedAt, revertedCount, skippedCount}.
    """
    receipt = read_json(receipt_path)
    operations: list[JsonObject] = receipt.get("operations") or []
    reverted = 0
    skipped = 0
    for op in operations:
        success = await _invert_operation(op)
        if success:
            reverted += 1
        else:
            skipped += 1
    reverted_at = now_iso()
    receipt["reverted"] = True
    receipt["revertedAt"] = reverted_at
    write_json(receipt_path, receipt)
    return {"revertedAt": reverted_at, "revertedCount": reverted, "skippedCount": skipped}


async def _invert_operation(op: JsonObject) -> bool:
    """Dispatch one receipt operation to its inverse API call. Returns True on success."""
    from .monarch_api import apply_transaction_updates, delete_monarch_rule

    op_type = str(op.get("type", ""))
    before: JsonObject = op.get("before") or {}

    match op_type:
        case "update_transaction":
            await apply_transaction_updates(
                [
                    {
                        "transactionId": str(op["entityId"]),
                        "merchantName": op.get("merchantName", ""),
                        "suggestedCategory": before.get("categoryName"),
                        "categoryId": before.get("categoryId"),
                        "setNeedsReview": before.get("needsReview"),
                    }
                ]
            )
            return True
        case "create_rule":
            await delete_monarch_rule(str(op["entityId"]))
            return True
        case _:
            from rich.console import Console
            Console().print(f"[yellow]Unknown operation type '{op_type}', skipping.[/]")
            return False
```

- [ ] **Step 4: Run all revert tests**

```bash
uv run pytest tests/test_revert.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/revert.py tests/test_revert.py
git commit -m "feat: add execute_revert dispatcher with update_transaction and create_rule inversion"
```

---

## Task 4: `apply_review_plan` emits receipt

**Files:**
- Modify: `monarch_money_tools/review.py`
- Modify: `tests/test_review.py`

- [ ] **Step 1: Update the existing test to patch `load_bundle` and assert receipt**

Open `tests/test_review.py`. Replace `test_apply_review_plan_accepts_updates_directly`:

```python
def test_apply_review_plan_accepts_updates_directly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t1", "categoryName": "Uncategorized", "needsReview": True}],
        "categories": [
            {"id": "c0", "name": "Uncategorized"},
            {"id": "c1", "name": "Dining"},
        ],
    }
    updates = [
        {
            "transactionId": "t1",
            "merchantName": "Coffee",
            "categoryId": "c1",
            "suggestedCategory": "Dining",
            "setNeedsReview": False,
        }
    ]
    with (
        patch(
            "monarch_money_tools.review.apply_transaction_updates", new_callable=AsyncMock
        ) as mock_apply,
        patch("monarch_money_tools.review.load_bundle", return_value=mini_bundle),
        patch("monarch_money_tools.review.write_json"),
    ):
        mock_apply.return_value = [{"id": "t1"}]
        result = asyncio.run(apply_review_plan(updates))

    mock_apply.assert_called_once_with(updates)
    assert result["requestedCount"] == 1
    # Receipt is written under data/review/revert/
    assert (tmp_path / "data" / "review" / "revert").exists()
    receipts = list((tmp_path / "data" / "review" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
uv run pytest tests/test_review.py::test_apply_review_plan_accepts_updates_directly -v
```

Expected: `FAILED` — receipt directory does not exist

- [ ] **Step 3: Modify `apply_review_plan` in `review.py`**

Replace the existing `apply_review_plan` function:

```python
async def apply_review_plan(updates: list[JsonObject]) -> JsonObject:
    from .paths import review_revert_dir
    from .revert import build_revert_receipt, snapshot_transaction_before, write_revert_receipt

    bundle = load_bundle()
    operations: list[JsonObject] = []
    for update in updates:
        before = snapshot_transaction_before(update["transactionId"], bundle)
        after: JsonObject = {
            "categoryId": update.get("categoryId"),
            "categoryName": update.get("suggestedCategory"),
            "needsReview": update.get("setNeedsReview"),
        }
        operations.append(
            {
                "type": "update_transaction",
                "entityId": update["transactionId"],
                "merchantName": update.get("merchantName", ""),
                "before": before,
                "after": after,
            }
        )

    results = await apply_transaction_updates(updates)
    applied: JsonObject = {
        "appliedAt": now_iso(),
        "requestedCount": len(updates),
        "results": results,
    }
    write_json(review_latest_dir() / "review-apply-results.json", applied)
    receipt = build_revert_receipt("monarch review apply", operations)
    write_revert_receipt(review_revert_dir(), receipt)
    return applied
```

- [ ] **Step 4: Run the test**

```bash
uv run pytest tests/test_review.py::test_apply_review_plan_accepts_updates_directly -v
```

Expected: `PASSED`

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/review.py tests/test_review.py
git commit -m "feat: apply_review_plan emits revert receipt"
```

---

## Task 5: `apply_clear_review_plan` emits receipt

**Files:**
- Modify: `monarch_money_tools/review.py`
- Modify: `tests/test_review.py`

- [ ] **Step 1: Update the existing test for `apply_clear_review_plan`**

Replace `test_apply_clear_review_plan_accepts_updates_directly` in `tests/test_review.py`:

```python
def test_apply_clear_review_plan_accepts_updates_directly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t2", "categoryName": "Transfer", "needsReview": True}],
        "categories": [{"id": "c2", "name": "Transfer"}],
    }
    updates = [
        {
            "transactionId": "t2",
            "merchantName": "Gas",
            "categoryId": "",
            "suggestedCategory": "Transfer",
            "setNeedsReview": False,
        }
    ]
    with (
        patch(
            "monarch_money_tools.review.apply_transaction_updates", new_callable=AsyncMock
        ) as mock_apply,
        patch("monarch_money_tools.review.load_bundle", return_value=mini_bundle),
        patch("monarch_money_tools.review.write_json"),
    ):
        mock_apply.return_value = [{"id": "t2"}]
        result = asyncio.run(apply_clear_review_plan(updates))

    mock_apply.assert_called_once_with(updates)
    assert result["requestedCount"] == 1
    receipts = list((tmp_path / "data" / "review" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/test_review.py::test_apply_clear_review_plan_accepts_updates_directly -v
```

Expected: `FAILED`

- [ ] **Step 3: Modify `apply_clear_review_plan` in `review.py`**

Replace the existing `apply_clear_review_plan`:

```python
async def apply_clear_review_plan(updates: list[JsonObject]) -> JsonObject:
    from .paths import review_revert_dir
    from .revert import build_revert_receipt, snapshot_transaction_before, write_revert_receipt

    bundle = load_bundle()
    operations: list[JsonObject] = []
    for update in updates:
        before = snapshot_transaction_before(update["transactionId"], bundle)
        after: JsonObject = {
            "categoryId": update.get("categoryId"),
            "categoryName": update.get("suggestedCategory"),
            "needsReview": update.get("setNeedsReview"),
        }
        operations.append(
            {
                "type": "update_transaction",
                "entityId": update["transactionId"],
                "merchantName": update.get("merchantName", ""),
                "before": before,
                "after": after,
            }
        )

    results = await apply_transaction_updates(updates)
    applied: JsonObject = {
        "appliedAt": now_iso(),
        "requestedCount": len(updates),
        "results": results,
    }
    write_json(review_latest_dir() / "clear-review-apply-results.json", applied)
    receipt = build_revert_receipt("monarch review clear-apply", operations)
    write_revert_receipt(review_revert_dir(), receipt)
    return applied
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_review.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/review.py tests/test_review.py
git commit -m "feat: apply_clear_review_plan emits revert receipt"
```

---

## Task 6: Extract `apply_llm_review_plan` into `llm_review.py` + emit receipt

Currently the LLM apply logic lives inline in `cmd/review.py`. Extract it into `llm_review.py` as a proper domain function, then update the command to call it.

**Files:**
- Modify: `monarch_money_tools/llm_review.py`
- Modify: `monarch_money_tools/cmd/review.py`
- Modify: `tests/test_llm_review.py`

- [ ] **Step 1: Read `tests/test_llm_review.py` to understand current test coverage**

```bash
uv run cat tests/test_llm_review.py
```

(Read it to understand what already exists before writing new tests.)

- [ ] **Step 2: Write the failing test**

Append to `tests/test_llm_review.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch


def test_apply_llm_review_plan_emits_receipt(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.llm_review import apply_llm_review_plan

    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t3", "categoryName": "Uncategorized", "needsReview": True}],
        "categories": [
            {"id": "c0", "name": "Uncategorized"},
            {"id": "c3", "name": "Groceries"},
        ],
    }
    updates = [
        {
            "transactionId": "t3",
            "merchantName": "Trader Joes",
            "suggestedCategory": "Groceries",
            "categoryId": "c3",
            "confidence": 0.95,
        }
    ]
    with (
        patch(
            "monarch_money_tools.llm_review.apply_transaction_updates", new_callable=AsyncMock
        ) as mock_apply,
        patch("monarch_money_tools.llm_review.load_bundle", return_value=mini_bundle),
    ):
        mock_apply.return_value = [{"id": "t3"}]
        result = asyncio.run(apply_llm_review_plan(updates))

    assert result["appliedCount"] == 1
    receipts = list((tmp_path / "data" / "review" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1
```

- [ ] **Step 3: Run to confirm it fails**

```bash
uv run pytest tests/test_llm_review.py::test_apply_llm_review_plan_emits_receipt -v
```

Expected: `FAILED` — `cannot import name 'apply_llm_review_plan'`

- [ ] **Step 4: Add `apply_llm_review_plan` to `llm_review.py`**

Add these imports at the top of `monarch_money_tools/llm_review.py` (with existing imports):

```python
from .monarch_api import apply_transaction_updates
from .paths import review_revert_dir
from .storage import JsonObject, load_bundle
```

Then add the function at the bottom of `llm_review.py`:

```python
async def apply_llm_review_plan(updates: list[JsonObject]) -> JsonObject:
    """Apply LLM review plan updates to Monarch and write a revert receipt."""
    from .revert import build_revert_receipt, snapshot_transaction_before, write_revert_receipt

    bundle = load_bundle()
    operations: list[JsonObject] = []
    api_updates: list[JsonObject] = []

    for u in updates:
        if not u.get("categoryId"):
            continue
        api_update: JsonObject = {
            "transactionId": u["transactionId"],
            "merchantName": u["merchantName"],
            "suggestedCategory": u["suggestedCategory"],
            "categoryId": u["categoryId"],
            "setNeedsReview": False,
        }
        api_updates.append(api_update)
        before = snapshot_transaction_before(u["transactionId"], bundle)
        after: JsonObject = {
            "categoryId": u["categoryId"],
            "categoryName": u["suggestedCategory"],
            "needsReview": False,
        }
        operations.append(
            {
                "type": "update_transaction",
                "entityId": u["transactionId"],
                "merchantName": u.get("merchantName", ""),
                "before": before,
                "after": after,
            }
        )

    results = await apply_transaction_updates(api_updates)
    receipt = build_revert_receipt("monarch review llm-apply", operations)
    write_revert_receipt(review_revert_dir(), receipt)
    return {"appliedCount": len(results), "results": results}
```

- [ ] **Step 5: Update `cmd/review.py` to call the extracted function**

In `monarch_money_tools/cmd/review.py`, update the imports at the top to include `apply_llm_review_plan`:

```python
from ..llm_review import FOCUS_CATEGORIES, apply_llm_review_plan, build_llm_review_plan
```

Replace the end of `apply_llm_review_command` (the part that builds `api_updates` and calls the API directly):

```python
    # Remove this block:
    # api_updates = [...]
    # results = run_async(apply_transaction_updates(api_updates))
    # console.print(f"[green]Applied LLM review updates:[/] {len(results)}")

    # Replace with:
    result = run_async(apply_llm_review_plan(updates))
    console.print(f"[green]Applied LLM review updates:[/] {result['appliedCount']}")
```

Also remove the `apply_transaction_updates` import from `cmd/review.py` if it is no longer used after this change (check the file — it may still be used by other commands in the same file; only remove if unused).

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_llm_review.py -v
```

Expected: all `PASSED`

- [ ] **Step 7: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 8: Commit**

```bash
git add monarch_money_tools/llm_review.py monarch_money_tools/cmd/review.py tests/test_llm_review.py
git commit -m "feat: extract apply_llm_review_plan, emit revert receipt"
```

---

## Task 7: Extract `apply_cleanup_plan` into `taxonomy_cleanup.py` + emit receipt

**Files:**
- Modify: `monarch_money_tools/taxonomy_cleanup.py`
- Modify: `monarch_money_tools/cmd/cleanup.py`
- Modify: `tests/test_taxonomy_cleanup.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_taxonomy_cleanup.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch


def test_apply_cleanup_plan_emits_receipt(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.taxonomy_cleanup import apply_cleanup_plan

    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t4", "categoryName": "Misc Shopping", "needsReview": False}],
        "categories": [
            {"id": "c4", "name": "Misc Shopping"},
            {"id": "c5", "name": "Shopping"},
        ],
    }
    candidates = [
        {
            "transactionId": "t4",
            "merchantName": "Target",
            "suggestedCategory": "Shopping",
            "categoryId": "c5",
            "setNeedsReview": False,
        }
    ]
    with (
        patch(
            "monarch_money_tools.taxonomy_cleanup.apply_transaction_updates",
            new_callable=AsyncMock,
        ) as mock_apply,
        patch("monarch_money_tools.taxonomy_cleanup.load_bundle", return_value=mini_bundle),
    ):
        mock_apply.return_value = [{"id": "t4"}]
        result = asyncio.run(apply_cleanup_plan(candidates))

    assert result["appliedCount"] == 1
    receipts = list((tmp_path / "data" / "cleanup" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/test_taxonomy_cleanup.py::test_apply_cleanup_plan_emits_receipt -v
```

Expected: `FAILED` — `cannot import name 'apply_cleanup_plan'`

- [ ] **Step 3: Add `apply_cleanup_plan` to `taxonomy_cleanup.py`**

Add these imports to `monarch_money_tools/taxonomy_cleanup.py` (with existing imports):

```python
from .monarch_api import apply_transaction_updates
from .paths import cleanup_revert_dir
from .storage import JsonObject, load_bundle
```

Add the function at the bottom of `taxonomy_cleanup.py`:

```python
async def apply_cleanup_plan(candidates: list[JsonObject]) -> JsonObject:
    """Apply cleanup candidates to Monarch and write a revert receipt."""
    from .revert import build_revert_receipt, snapshot_transaction_before, write_revert_receipt

    bundle = load_bundle()
    operations: list[JsonObject] = []
    api_updates: list[JsonObject] = []

    for c in candidates:
        if not c.get("categoryId"):
            continue
        api_update: JsonObject = {
            "transactionId": c["transactionId"],
            "merchantName": c["merchantName"],
            "suggestedCategory": c["suggestedCategory"],
            "categoryId": c["categoryId"],
            "setNeedsReview": c.get("setNeedsReview", False),
        }
        api_updates.append(api_update)
        before = snapshot_transaction_before(c["transactionId"], bundle)
        after: JsonObject = {
            "categoryId": c["categoryId"],
            "categoryName": c["suggestedCategory"],
            "needsReview": c.get("setNeedsReview", False),
        }
        operations.append(
            {
                "type": "update_transaction",
                "entityId": c["transactionId"],
                "merchantName": c.get("merchantName", ""),
                "before": before,
                "after": after,
            }
        )

    results = await apply_transaction_updates(api_updates)
    receipt = build_revert_receipt("monarch cleanup apply", operations)
    write_revert_receipt(cleanup_revert_dir(), receipt)
    return {"appliedCount": len(results), "results": results}
```

- [ ] **Step 4: Update `cmd/cleanup.py` to call the extracted function**

In `monarch_money_tools/cmd/cleanup.py`, add the import:

```python
from ..taxonomy_cleanup import (
    apply_cleanup_plan,
    build_taxonomy_cleanup_plan,
    filter_cleanup_candidates,
    load_decisions,
)
```

In `apply_cleanup_command`, replace the inline API call block:

```python
    # Remove:
    # updates = [
    #     {
    #         "transactionId": c["transactionId"],
    #         ...
    #     }
    #     for c in candidates
    #     if c.get("categoryId")
    # ]
    # result = run_async(apply_transaction_updates(updates))
    # console.print(f"[green]Applied cleanup updates:[/] {len(result)}")

    # Replace with:
    result = run_async(apply_cleanup_plan(candidates))
    console.print(f"[green]Applied cleanup updates:[/] {result['appliedCount']}")
```

Remove the `apply_transaction_updates` import from `cmd/cleanup.py` if it is no longer used.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_taxonomy_cleanup.py -v
```

Expected: all `PASSED`

- [ ] **Step 6: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 7: Commit**

```bash
git add monarch_money_tools/taxonomy_cleanup.py monarch_money_tools/cmd/cleanup.py tests/test_taxonomy_cleanup.py
git commit -m "feat: extract apply_cleanup_plan, emit revert receipt"
```

---

## Task 8: `apply_rules_plan` emits receipt

**Files:**
- Modify: `monarch_money_tools/rules.py`
- Modify: `tests/test_rules.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rules.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch


def test_apply_rules_plan_emits_receipt(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.rules import apply_rules_plan

    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t5", "categoryName": "Uncategorized", "needsReview": True}],
        "categories": [
            {"id": "c0", "name": "Uncategorized"},
            {"id": "c6", "name": "Dining"},
        ],
    }
    # build_apply_plan reads from disk, so patch it to return a canned plan
    canned_plan = {
        "updates": [
            {
                "transactionId": "t5",
                "merchantName": "Chipotle",
                "suggestedCategory": "Dining",
                "categoryId": "c6",
                "clearNeedsReview": True,
                "ruleName": "Chipotle rule",
                "addTag": None,
            }
        ]
    }
    with (
        patch("monarch_money_tools.rules.build_apply_plan", return_value=canned_plan),
        patch(
            "monarch_money_tools.rules.apply_transaction_updates", new_callable=AsyncMock
        ) as mock_apply,
        patch("monarch_money_tools.rules.load_bundle", return_value=mini_bundle),
    ):
        mock_apply.return_value = [{"id": "t5"}]
        result = asyncio.run(apply_rules_plan())

    assert result["appliedCount"] == 1
    receipts = list((tmp_path / "data" / "rules" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/test_rules.py::test_apply_rules_plan_emits_receipt -v
```

Expected: `FAILED`

- [ ] **Step 3: Modify `apply_rules_plan` in `rules.py`**

Replace the existing `apply_rules_plan` function:

```python
async def apply_rules_plan(
    rules_path: str | None = None,
    limit: int | None = None,
    rules_filter: list[str] | None = None,
) -> JsonObject:
    from .monarch_api import apply_transaction_updates, tag_transactions
    from .paths import rules_revert_dir
    from .revert import build_revert_receipt, snapshot_transaction_before, write_revert_receipt
    from .storage import load_bundle

    plan = build_apply_plan(rules_path, rules_filter)
    updates = plan["updates"]

    if limit is not None:
        updates = updates[:limit]

    api_updates = [
        {
            "transactionId": u["transactionId"],
            "merchantName": u["merchantName"],
            "suggestedCategory": u["suggestedCategory"],
            "categoryId": u["categoryId"] or None,
            "setNeedsReview": False if u["clearNeedsReview"] else None,
        }
        for u in updates
        if u.get("categoryId") or u.get("clearNeedsReview")
    ]

    bundle = load_bundle()
    operations: list[JsonObject] = []
    for u in updates:
        if not (u.get("categoryId") or u.get("clearNeedsReview")):
            continue
        before = snapshot_transaction_before(u["transactionId"], bundle)
        after: JsonObject = {
            "categoryId": u.get("categoryId") or None,
            "categoryName": u.get("suggestedCategory"),
            "needsReview": False if u.get("clearNeedsReview") else None,
        }
        operations.append(
            {
                "type": "update_transaction",
                "entityId": u["transactionId"],
                "merchantName": u.get("merchantName", ""),
                "before": before,
                "after": after,
            }
        )

    tag_updates: dict[str, list[str]] = defaultdict(list)
    for u in updates:
        if u.get("addTag"):
            tag_updates[u["addTag"]].append(u["transactionId"])

    results = await apply_transaction_updates(api_updates) if api_updates else []
    for tag_name, txn_ids in tag_updates.items():
        await tag_transactions(txn_ids, tag_name)

    if operations:
        receipt = build_revert_receipt("monarch rules apply", operations)
        write_revert_receipt(rules_revert_dir(), receipt)

    return {
        "appliedCount": len(results),
        "taggedGroups": len(tag_updates),
        "updates": updates,
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_rules.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/rules.py tests/test_rules.py
git commit -m "feat: apply_rules_plan emits revert receipt"
```

---

## Task 9: `rules push` emits receipt

**Files:**
- Modify: `monarch_money_tools/cmd/rules.py`
- Modify: `tests/test_rules.py`

The `push` command is atomic (no plan file) but should still emit a `create_rule` receipt.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rules.py`:

```python
from typer.testing import CliRunner
from monarch_money_tools.cmd.rules import rules_app
from monarch_money_tools.storage import read_json, write_json


def test_push_rule_emits_create_rule_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    # Write a minimal rule-suggestions.json for the push command to find
    (tmp_path / "data" / "rules" / "latest").mkdir(parents=True)
    write_json(
        tmp_path / "data" / "rules" / "latest" / "rule-suggestions.json",
        [
            {
                "id": "rule-local-1",
                "name": "Chipotle → Dining",
                "enabled": True,
                "match": {"merchantNames": ["Chipotle"]},
                "action": {"setCategory": "Dining", "clearNeedsReview": True},
            }
        ],
    )

    fake_result = {"transactionRule": {"id": "monarch-rule-99", "order": 1}, "errors": None}

    runner = CliRunner()
    # run_async is patched so the inner _push() coroutine is never awaited —
    # no real API client is created. monkeypatch.chdir handles the revert dir path.
    with patch("monarch_money_tools.cmd.rules.run_async", return_value=fake_result):
        result = runner.invoke(rules_app, ["push", "rule-local-1", "--yes"])

    assert result.exit_code == 0, result.output
    receipts = list((tmp_path / "data" / "rules" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1
    receipt = read_json(receipts[0])
    assert receipt["operations"][0]["type"] == "create_rule"
    assert receipt["operations"][0]["entityId"] == "monarch-rule-99"
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/test_rules.py::test_push_rule_emits_create_rule_receipt -v
```

Expected: `FAILED`

- [ ] **Step 3: Update `push_rule_command` in `cmd/rules.py`**

Add the import at the top of `cmd/rules.py`:

```python
from ..paths import rules_revert_dir
from ..revert import build_revert_receipt, write_revert_receipt
```

After the successful `console.print(f"[green]Created Monarch rule:[/] ...")` line in `push_rule_command`, add:

```python
    receipt_op: dict[str, object] = {
        "type": "create_rule",
        "entityId": str(new_rule.get("id", "")),
        "ruleName": match["name"],
        "before": None,
        "after": {"monarchRuleId": str(new_rule.get("id", ""))},
    }
    receipt = build_revert_receipt("monarch rules push", [receipt_op])
    write_revert_receipt(rules_revert_dir(), receipt)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_rules.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/cmd/rules.py tests/test_rules.py
git commit -m "feat: rules push emits create_rule revert receipt"
```

---

## Task 10: `monarch review revert` subcommand

**Files:**
- Modify: `monarch_money_tools/cmd/review.py`
- Modify: `tests/test_review.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_review.py`:

```python
from typer.testing import CliRunner
from monarch_money_tools.cmd.review import review_app


def test_review_revert_no_receipt_exits_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(review_app, ["revert"])
    assert result.exit_code == 1
    assert "No revert receipt found" in result.output


def test_review_revert_dry_run_shows_table(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.revert import build_revert_receipt, write_revert_receipt
    from monarch_money_tools.paths import review_revert_dir

    monkeypatch.chdir(tmp_path)
    receipt = build_revert_receipt(
        "monarch review apply",
        [
            {
                "type": "update_transaction",
                "entityId": "txn-1",
                "merchantName": "Starbucks",
                "before": {"categoryId": "cat-0", "categoryName": "Uncategorized", "needsReview": True},
                "after": {"categoryId": "cat-1", "categoryName": "Coffee Shops", "needsReview": False},
            }
        ],
    )
    write_revert_receipt(review_revert_dir(), receipt)

    runner = CliRunner()
    result = runner.invoke(review_app, ["revert", "--dry-run"])
    assert result.exit_code == 0
    assert "Starbucks" in result.output
    assert "Uncategorized" in result.output
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/test_review.py::test_review_revert_no_receipt_exits_cleanly tests/test_review.py::test_review_revert_dry_run_shows_table -v
```

Expected: `FAILED` — `No such command 'revert'`

- [ ] **Step 3: Add the `revert` subcommand to `cmd/review.py`**

Add imports at top of `cmd/review.py`:

```python
from ..paths import review_revert_dir
from ..revert import execute_revert, find_latest_receipt
```

Add the new command after the existing commands:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_review.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/cmd/review.py tests/test_review.py
git commit -m "feat: add monarch review revert subcommand"
```

---

## Task 11: `monarch cleanup revert` subcommand

**Files:**
- Modify: `monarch_money_tools/cmd/cleanup.py`
- Modify: `tests/test_taxonomy_cleanup.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_taxonomy_cleanup.py`:

```python
from typer.testing import CliRunner
from monarch_money_tools.cmd.cleanup import cleanup_app


def test_cleanup_revert_no_receipt_exits_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cleanup_app, ["revert"])
    assert result.exit_code == 1
    assert "No revert receipt found" in result.output


def test_cleanup_revert_dry_run_shows_table(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.revert import build_revert_receipt, write_revert_receipt
    from monarch_money_tools.paths import cleanup_revert_dir

    monkeypatch.chdir(tmp_path)
    receipt = build_revert_receipt(
        "monarch cleanup apply",
        [
            {
                "type": "update_transaction",
                "entityId": "txn-2",
                "merchantName": "Target",
                "before": {"categoryId": "cat-4", "categoryName": "Misc Shopping", "needsReview": False},
                "after": {"categoryId": "cat-5", "categoryName": "Shopping", "needsReview": False},
            }
        ],
    )
    write_revert_receipt(cleanup_revert_dir(), receipt)

    runner = CliRunner()
    result = runner.invoke(cleanup_app, ["revert", "--dry-run"])
    assert result.exit_code == 0
    assert "Target" in result.output
```

- [ ] **Step 2: Run to confirm they fail**

```bash
uv run pytest tests/test_taxonomy_cleanup.py::test_cleanup_revert_no_receipt_exits_cleanly tests/test_taxonomy_cleanup.py::test_cleanup_revert_dry_run_shows_table -v
```

Expected: `FAILED`

- [ ] **Step 3: Add `revert` subcommand to `cmd/cleanup.py`**

Add imports at top of `cmd/cleanup.py`:

```python
from ..paths import cleanup_revert_dir
from ..revert import execute_revert, find_latest_receipt
```

Append the new command:

```python
_REVERT_COLUMNS = [
    ("Merchant", None),
    ("Current Category", None),
    ("Restoring Category", None),
    ("Review", None),
]


@cleanup_app.command("revert")
def revert_cleanup_command(
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
    """Revert the latest cleanup apply using its revert receipt."""
    from pathlib import Path

    receipt_path = Path(receipt) if receipt else find_latest_receipt(cleanup_revert_dir())
    if not receipt_path:
        console.print("[red]No revert receipt found.[/] Run `monarch cleanup apply` first.")
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_taxonomy_cleanup.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/cmd/cleanup.py tests/test_taxonomy_cleanup.py
git commit -m "feat: add monarch cleanup revert subcommand"
```

---

## Task 12: `monarch rules revert` subcommand

**Files:**
- Modify: `monarch_money_tools/cmd/rules.py`
- Modify: `tests/test_rules.py`

The rules revert handles both `update_transaction` (from `rules apply`) and `create_rule` (from `rules push`) operations.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rules.py`:

```python
def test_rules_revert_no_receipt_exits_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(rules_app, ["revert"])
    assert result.exit_code == 1
    assert "No revert receipt found" in result.output


def test_rules_revert_dry_run_shows_table(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.revert import build_revert_receipt, write_revert_receipt
    from monarch_money_tools.paths import rules_revert_dir

    monkeypatch.chdir(tmp_path)
    receipt = build_revert_receipt(
        "monarch rules apply",
        [
            {
                "type": "update_transaction",
                "entityId": "txn-3",
                "merchantName": "Chipotle",
                "before": {"categoryId": "cat-0", "categoryName": "Uncategorized", "needsReview": True},
                "after": {"categoryId": "cat-6", "categoryName": "Dining", "needsReview": False},
            }
        ],
    )
    write_revert_receipt(rules_revert_dir(), receipt)

    runner = CliRunner()
    result = runner.invoke(rules_app, ["revert", "--dry-run"])
    assert result.exit_code == 0
    assert "Chipotle" in result.output
```

- [ ] **Step 2: Run to confirm they fail**

```bash
uv run pytest tests/test_rules.py::test_rules_revert_no_receipt_exits_cleanly tests/test_rules.py::test_rules_revert_dry_run_shows_table -v
```

Expected: `FAILED`

- [ ] **Step 3: Add `revert` subcommand to `cmd/rules.py`**

`rules_revert_dir` and `write_revert_receipt` are already imported (from Task 9). Add `execute_revert` and `find_latest_receipt` to the import:

```python
from ..revert import build_revert_receipt, execute_revert, find_latest_receipt, write_revert_receipt
```

Append the new command:

```python
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
            "[red]No revert receipt found.[/] Run `monarch rules apply` or `monarch rules push` first."
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
            [("Merchant", None), ("Current Category", None), ("Restoring Category", None), ("Review", None)],
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
```

Also add `read_json` to the imports from `..storage` if not already present.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_rules.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/cmd/rules.py tests/test_rules.py
git commit -m "feat: add monarch rules revert subcommand"
```

---

## Task 13: Rename `review llm` → `review llm-plan`

**Files:**
- Modify: `monarch_money_tools/cmd/review.py`
- Modify: `tests/test_cli.py` (update any CLI invocation tests that use `llm`)

- [ ] **Step 1: Check for existing tests that invoke `review llm`**

```bash
grep -rn "review.*llm\|llm.*review" tests/
```

Note every occurrence — you'll need to update those tests.

- [ ] **Step 2: Rename the command decorator and add a deprecated alias**

In `cmd/review.py`, find:

```python
@review_app.command("llm")
def llm_review_command(
```

Change to:

```python
@review_app.command("llm-plan")
def llm_review_command(
```

Then add a deprecated alias immediately after the function definition:

```python
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
```

- [ ] **Step 3: Update any test invocations of `review llm` to `review llm-plan`**

Search results from Step 1 — update each one.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli.py tests/test_llm_review.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add monarch_money_tools/cmd/review.py tests/
git commit -m "feat: rename review llm → review llm-plan, keep llm as deprecated alias"
```

---

## Task 14: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the Plan/Apply/Revert invariant**

Open `CLAUDE.md`. In the **Key Invariants** section, after `**Preview before mutation.**`, add:

```markdown
**Plan / Apply / Revert.** Every mutation follows plan → apply → revert. `plan` writes a human-readable plan file. `apply` reads the plan, calls the API, and writes a timestamped revert receipt at `data/<group>/revert/`. `revert` reads the latest receipt and restores the before-state. See `docs/patterns/plan-apply-revert.md`.
```

- [ ] **Step 2: Verify the full test suite still passes (smoke check)**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
```

Expected: all green

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Plan/Apply/Revert invariant to CLAUDE.md"
```

---

## Final verification

- [ ] **Smoke-test the new commands exist**

```bash
uv run monarch review --help   # should list: plan, apply, revert, clear-plan, clear-apply, llm-plan, llm (deprecated), llm-apply, bulk-clear
uv run monarch cleanup --help  # should list: plan, review, apply, revert
uv run monarch rules --help    # should list: suggest, apply, revert, list, push, delete
```

- [ ] **Run the complete test suite one final time**

```bash
uv run pytest -v
```

Expected: all 15+ tests green
