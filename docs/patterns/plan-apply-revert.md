# Plan / Apply / Revert Pattern

All mutations in Monarch Money Tools follow a three-step lifecycle:

```
plan  →  apply  →  revert
```

No step is required before another in absolute terms, but the pattern is designed so each step is safe to inspect and stop at.

---

## The Three Steps

### plan

Generates a human-readable plan file. **No API calls. No side effects.**

- Reads from `data/normalized/latest/bundle.json`
- Writes one or more files to `data/<group>/latest/` (JSON, CSV, Markdown)
- Prints a dry-run table so the user can review before committing

### apply

Reads the latest plan file, calls the Monarch API, and writes a **revert receipt**.

- Reads from `data/<group>/latest/<plan-file>.json`
- Sends mutations to Monarch via the unofficial GraphQL API
- Writes a timestamped receipt to `data/<group>/revert/revert-<ts>.json`
- The receipt captures the exact before-state of every entity that was changed

### revert

Reads the latest revert receipt and sends the before-state back to the API.

- Reads from `data/<group>/revert/revert-<ts>.json` (latest non-reverted by default)
- Sends inverse API calls to restore the prior state
- Marks the receipt `reverted: true` on success
- Subsequent `revert` calls pick the next-oldest eligible receipt

---

## Command Inventory

| Command | Step | Plan file | Receipt |
|---|---|---|---|
| `monarch cleanup plan` | plan | `data/cleanup/latest/cleanup-plan.json` | — |
| `monarch cleanup apply` | apply | reads above | `data/cleanup/revert/revert-<ts>.json` |
| `monarch cleanup revert` | revert | — | reads above |
| `monarch review plan` | plan | `data/review/latest/review-plan.json` | — |
| `monarch review apply` | apply | reads above | `data/review/revert/revert-<ts>.json` |
| `monarch review revert` | revert | — | reads above |
| `monarch review clear-plan` | plan | `data/review/latest/clear-review-plan.json` | — |
| `monarch review clear-apply` | apply | reads above | `data/review/revert/revert-<ts>.json` |
| `monarch review llm-plan` | plan | `data/review/latest/llm-review-plan.json` | — |
| `monarch review llm-apply` | apply | reads above | `data/review/revert/revert-<ts>.json` |
| `monarch review bulk-clear` | plan+apply | *(combined)* | `data/review/revert/revert-<ts>.json` |
| `monarch rules suggest` | plan | `data/rules/latest/rule-suggestions.json` | — |
| `monarch rules apply` | apply | reads above | `data/rules/revert/revert-<ts>.json` |
| `monarch rules push` | apply (atomic) | *(no plan file)* | `data/rules/revert/revert-<ts>.json` |
| `monarch rules revert` | revert | — | reads above |

---

## Receipt Format

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

The `before` dict contains the field values **as they were at apply time**, snapshotted from `data/normalized/latest/bundle.json`. The `after` dict contains the values that were sent to the API.

### Operation types

| `type` | Description | Inverted by |
|---|---|---|
| `update_transaction` | Category and/or `needsReview` change on a transaction | Re-send `before` fields via `updateTransaction` mutation |
| `create_rule` | A new transaction rule was created in Monarch | `deleteTransactionRule(entityId)` |

---

## Adding a New Operation Type

1. Give the operation a `type` string (snake_case, e.g. `set_transaction_tags`)
2. In the apply function, build `before` and `after` dicts for each affected entity
3. In `revert.py`, add a `case "set_transaction_tags":` branch to `_invert_operation` with the inverse API call
4. Add the new type to the table above

No receipt format changes are needed — the `before`/`after` shape is generic.

---

## Extending for New Fields on Existing Operation Types

To add a new field to `update_transaction` reverts (e.g. `notes`):

1. Add `"notes": txn.get("notes")` to `snapshot_transaction_before()` in `revert.py`
2. Add `"notes": update.get("notes")` to the `after` dict in the relevant apply function
3. Add `notes` to the `client.update_transaction(...)` call in `_invert_operation`

No schema migration needed — old receipts without `notes` will just have `None` for that field and the API call will leave it unchanged.

---

## Key Properties

- **Receipts are immutable after revert.** A receipt marked `reverted: true` is never overwritten again. `find_latest_receipt` skips it.
- **Receipts stack.** Running `apply` twice produces two receipts; running `revert` twice undoes both in order (newest first).
- **Revert is idempotent at the receipt level.** If the API call fails mid-revert, the receipt is not marked `reverted: true`, so you can run `revert` again safely.
- **No plan format changes.** The before-state is snapshotted from the bundle at apply time, not stored in plan files.
- **`--dry-run` on revert** shows a table of what would be restored without calling the API.
