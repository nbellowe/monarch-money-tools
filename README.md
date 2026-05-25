# monarch-money-tools

A CLI for Monarch Money users who want programmatic control over transaction categorization, cleanup, and rule management — beyond what the Monarch UI provides.

Built for technical users who want to bulk-categorize transactions, apply deterministic cleanup rules, run LLM-assisted reviews, and push changes back to Monarch via its unofficial API.

> **Unofficial API notice:** This tool uses Monarch Money's unofficial GraphQL API. It may break without notice. Use at your own risk. Not affiliated with Monarch Money.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A Monarch Money account

---

## Installation

```bash
uv tool install monarch-money-tools
```

For a development install from a cloned repo:

```bash
git clone https://github.com/<your-username>/monarch-money-tools.git
cd monarch-money-tools
uv sync --extra dev --extra api --extra llm
```

---

## Auth Setup

The CLI supports browser-cookie, saved-session, and password fallback auth. Browser-cookie or
saved-session auth is preferred because it avoids storing your Monarch password locally.

After logging in to monarchmoney.com, copy the full cookie header and put it in `.env`:

```bash
MONARCH_COOKIE="session_id=...; csrftoken=..."
```

You can also set `MONARCH_SESSION_TOKEN`, or use `MONARCH_EMAIL`, `MONARCH_PASSWORD`, and
optionally `MONARCH_MFA_SECRET` as a fallback.

---

## Quick-Start Workflow

```bash
# API path
monarch init
monarch pull
monarch data analyze
monarch data report

# CSV-only path
monarch run ~/Downloads/monarch_transactions.csv

# Review categorization output
open reports/latest/summary.md

# Plan and apply Needs-Review changes
monarch review plan
open reports/latest/review-plan.md
monarch review apply --dry-run
monarch review apply --yes
```

---

## Command Reference

### Data

| Command | Description |
|---|---|
| `monarch init` | Run the setup wizard for credentials, taxonomy, profile, and doctor checks |
| `monarch pull` / `monarch data pull` | Pull transaction data from Monarch via the unofficial API |
| `monarch import [CSV]` / `monarch data import [CSV]` | Import and normalize a Monarch transaction CSV export |
| `monarch run [CSV]` / `monarch data run [CSV]` | Import if needed, then analyze and report |
| `monarch data analyze` | Analyze normalized transactions for review and rule opportunities |
| `monarch data report` | Render Markdown and CSV reports from the latest analysis |
| `monarch data recurring` | Detect recurring subscriptions, bills, transfers, and price drift |
| `monarch data income-overlay` | Classify transactions into salary, reimbursement, transfer, investment, or spending |
| `monarch data backup` | Back up data/ and reports/ before destructive operations |
| `monarch doctor` | Check local setup and artifact availability |

### Reviews

| Command | Description |
|---|---|
| `monarch review plan` | Plan category updates for Needs-Review transactions |
| `monarch review apply` | Apply the latest review plan to Monarch |
| `monarch review clear-plan` | Plan clearing Needs-Review on trusted categories |
| `monarch review clear-apply` | Apply the clear-review plan |
| `monarch review llm` | Run an LLM-assisted categorization pass |
| `monarch review llm-apply` | Apply the latest LLM review plan |

### Cleanup

| Command | Description |
|---|---|
| `monarch cleanup plan` | Generate taxonomy migration and merchant-consistency candidates |
| `monarch cleanup review` | Interactively accept, reject, or skip cleanup candidates |
| `monarch cleanup apply` | Apply the latest cleanup plan to Monarch |

### Rules

| Command | Description |
|---|---|
| `monarch rules suggest` | Analyze transaction history and suggest automation rules |
| `monarch rules apply` | Apply enabled rules from the latest suggestions |
| `monarch rules push <id>` | Push a single local rule suggestion into Monarch |
| `monarch rules list` | List all rules currently stored in Monarch |
| `monarch rules delete <id>` | Delete a rule from Monarch by ID |

### Portfolio

| Command | Description |
|---|---|
| `monarch portfolio` | Fetch and display portfolio holdings and allocation |

---

## Taxonomy

`taxonomy/canonical-taxonomy.yaml` provides a reference category structure for Monarch Money — 71 categories across 15 groups with migration mappings from legacy Monarch categories.

Use it as a starter for your own taxonomy cleanup, or load it into the cleanup workflow:

```bash
monarch cleanup plan
monarch cleanup apply --dry-run
monarch cleanup apply --yes
```

---

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format --check .
```

---

## License

MIT
