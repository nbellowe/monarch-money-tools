# GitHub Issues Implementation Design

**Date:** 2026-05-24  
**Scope:** All open GitHub issues except #14 (docs site, separate session) and #11 (web app, deferred)

---

## Issues In Scope

| # | Title | Section |
|---|-------|---------|
| #6 | Add conftest.py with shared pytest fixtures | Infrastructure |
| #5 | Document or scope workbench command | Infrastructure |
| #12 | monarch tag-reimbursements is not generic | Infrastructure |
| #8 | Consistent --dry-run flag across all apply commands | CLI consistency |
| #7 | monarch init: setup wizard for new users | Auth/Setup |
| #13 | better auth flow | Auth/Setup |
| #2 | Configurable cashflow/income classifier | New feature |
| #4 | Interactive accept/reject/defer loop for taxonomy cleanup | New feature |
| #10 | PyPI release criteria and checklist | Release |

---

## Implementation Order

Infrastructure → CLI consistency → Auth/Setup → New features → Release

---

## Section 1: Infrastructure & Quick Cleanup

### #6 — conftest.py

Add `tests/conftest.py` with two shared fixtures:

- **`normalized_bundle(tmp_path)`** — parses `tests/fixtures/monarch_transactions.csv`, writes a minimal bundle JSON to a temp dir, returns the bundle `dict` (keys: `transactions`, `accounts`, `categories`) as `storage.read_json()` would return it. Existing tests are unmodified; fixtures are purely additive.
- **`monarch_data_dir(tmp_path, monkeypatch)`** — patches `paths.root_dir()` to point at a temp dir pre-populated with fixture data.

Both fixtures load from `tests/fixtures/monarch_transactions.csv` to stay grounded in realistic data.

### #5 — workbench: mark as internal

Add a one-line docstring to `workbench.py` and the `@app.command("workbench")` handler:

> "Internal investigation tool — not part of the stable CLI surface."

No README changes. The command remains registered but is explicitly scoped as internal.

### #12 — remove tag-reimbursements

Delete `tag_reimbursements_command` from `cli.py`. Remove any tests that exercise it. No other modules reference it.

---

## Section 2: `--dry-run` Consistency (#8)

Add `--dry-run` to four apply commands that currently lack it:
- `apply-reviews`
- `apply-clear-reviews`
- `apply-cleanup`
- `apply-llm-review`

(Already present on `llm-review` and `apply-rules`.)

**Consistent behavior:**
- Print a `rich` table showing what would be applied (columns vary per command: merchant / current value / new value / count)
- Truncate at 50 rows with `… and N more` suffix for large result sets
- Respects `--limit` — shows exactly what the live run would apply (for `apply-cleanup`, this means only accepted candidates from the decision log)
- Exits 0 without making any API calls

Rendering logic lives in each command handler in `cli.py` — no new module needed. Tests assert the API is not called and the table contains expected rows.

---

## Section 3: `monarch init` Setup Wizard (#7 + #13)

New `monarch init` command (distinct from `monarch init-profile`). Implemented in a new `init_wizard.py` module; `cli.py` delegates to it.

**Steps (each individually skippable):**

1. **Credentials** — prompts for `MONARCH_EMAIL`, `MONARCH_PASSWORD`, and optionally `MONARCH_MFA_SECRET`. Explains how to obtain the BASE32 MFA secret (disable/re-enable 2FA in Monarch settings, click "Can't scan?"). Appends missing keys to `.env` — never overwrites existing values. Skips if all are already set.
2. **Connection test** — runs a lightweight API call (categories fetch) to verify credentials work. Prints success or a friendly error with next steps.
3. **Taxonomy check** — compares live Monarch categories against `taxonomy/canonical-taxonomy.yaml` and reports mismatches.
4. **Profile bootstrap** — if `profile.yaml` doesn't exist, runs `monarch init-profile` to generate a starter file.
5. **Doctor** — runs `monarch doctor` and prints the summary.

**`--yes` flag** — skips all interactive prompts, uses existing env values (for scripting). Steps requiring API access are silently skipped if credentials are unavailable.

Tests mock credential prompts and API calls.

---

## Section 4: `monarch income-overlay` (#2)

New command classifying transactions from the normalized bundle. Implementation in a new `cashflow.py` module.

**Classification labels:** `salary`, `reimbursement`, `transfer`, `investment_proceeds`, `spending`

**Classification logic:**
- Reads regex pattern lists from `profile.yaml`: `income_sources`, `reimbursement_patterns`, `transfer_patterns`
- Falls back to category-based heuristics when profile config is absent (e.g. "Paychecks" → salary, "Sell Investment" → investment_proceeds)
- Sets `manual_review: true` for partial or ambiguous matches
- Pure function — no API calls, deterministic

**Profile additions** — new optional fields in `ProfileConfig`:
```yaml
income_sources:
  - pattern: "Acme Corp Payroll"
reimbursement_patterns:
  - pattern: "Expensify"
  - pattern: "Navan"
transfer_patterns:
  - pattern: "Zelle from"
```

**CLI flags:** `--start` / `--end` date filters (optional)

**Output:** `data/cashflow/latest/income-overlay.{json,csv,md}`

**CLI output:** summary table (classification → count → total), `manual_review` count surfaced prominently.

Tests use `normalized_bundle` fixture and a minimal inline profile config.

---

## Section 5: Interactive Cleanup Review (#4)

New `monarch review-cleanup` command. Implementation in a new `review_cleanup.py` module.

**Terminal UI** (pure `rich`, no external TUI dependency):
```
[12/47] Amazon.com → Shopping
  Current:   Uncategorized
  Suggested: Shopping
  Samples:   2025-03-14  $34.99 · 2025-02-28  $129.00

  (a)ccept  (r)eject  (s)kip  (q)uit
```

**Persistence:** decisions written to `data/cleanup/latest/decisions.json` after each keypress (not batched). Session is resumable — already-decided candidates are skipped on re-entry.

**Integration with existing commands:**
- `cleanup-plan` filters out rejected candidates by default; `--show-rejected` flag to include them
- `apply-cleanup` only applies accepted candidates; undecided and rejected are skipped

**Module changes:**
- New `review_cleanup.py` — interactive loop + keypress handling
- `taxonomy_cleanup.py` — gains `load_decisions()` / `save_decision()` helpers
- `cli.py` — adds `review-cleanup` command, `--show-rejected` on `cleanup-plan`

Tests cover: decision persistence, resume behavior, apply-cleanup filtering.

---

## Section 6: PyPI Release (#10)

**Version:** bump `pyproject.toml` to `0.0.1`.

**GitHub Actions:**

`ci.yml` — runs on every push and PR to `main`:
```
uv sync --extra dev --extra api --extra llm
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

`publish.yml` — runs on tag push matching `v*`:
- Runs same checks as CI
- `uv build`
- Publishes via `pypa/gh-action-pypi-publish` using `PYPI_API_TOKEN` secret

**README:** replace `uv tool install .` with `uv tool install monarch-money-tools`; retain clone-based path as "development install" alternative.

No package structure changes required.
