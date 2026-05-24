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

## Install

```bash
uv tool install .
```

Or for development (editable install with dev dependencies):

```bash
uv sync --extra dev --extra api --extra llm
```

---

## Auth Setup

The CLI uses browser cookie auth by default. After logging in to monarchmoney.com:

1. Open DevTools → Application → Cookies
2. Copy the session cookie value
3. Either:
   - Set `MONARCH_SESSION_TOKEN=<value>` in a `.env` file at your working directory, **or**
   - Let the `monarchmoney` library auto-detect your browser session

Alternatively, run `monarch pull` and follow the interactive login prompt on first use.

---

## Quick-Start Workflow

```bash
# 1. Pull your transaction data from Monarch
monarch pull

# 2. Import, analyze, and generate reports in one pass
monarch run

# 3. Review the Markdown report
open reports/latest/report.md

# 4. Plan which Needs-Review transactions to resolve
monarch plan-reviews

# 5. Apply the plan to Monarch
monarch apply-reviews --yes
```

---

## Command Reference

### Data

| Command | Description |
|---|---|
| `monarch pull` | Pull transaction data from Monarch via the unofficial API |
| `monarch import [CSV]` | Import and normalize a Monarch transaction CSV export |
| `monarch run [CSV]` | Import, analyze, and report in one pass |
| `monarch analyze` | Analyze normalized transactions for review and rule opportunities |
| `monarch report` | Render Markdown and CSV reports from the latest analysis |
| `monarch recurring` | Detect recurring subscriptions, bills, transfers, and price drift |
| `monarch backup` | Back up data/ and reports/ before destructive operations |
| `monarch doctor` | Check local setup and artifact availability |

### Reviews

| Command | Description |
|---|---|
| `monarch plan-reviews` | Plan category updates for Needs-Review transactions |
| `monarch apply-reviews` | Apply the latest review plan to Monarch |
| `monarch plan-clear-reviews` | Plan clearing Needs-Review on trusted categories |
| `monarch apply-clear-reviews` | Apply the clear-review plan |
| `monarch bulk-clear-reviews` | Plan and apply a clear-review pass in one step |
| `monarch llm-review` | Run an LLM-assisted categorization pass |
| `monarch apply-llm-review` | Apply the latest LLM review plan |

### Cleanup

| Command | Description |
|---|---|
| `monarch cleanup-plan` | Generate taxonomy migration and merchant-consistency candidates |
| `monarch apply-cleanup` | Apply the latest cleanup plan to Monarch |
| `monarch tag-reimbursements` | Reclassify Expensify/Navan reimbursements to Other Income |

### Rules

| Command | Description |
|---|---|
| `monarch suggest-rules` | Analyze transaction history and suggest automation rules |
| `monarch apply-rules` | Apply enabled rules from the latest suggestions |
| `monarch push-rule <id>` | Push a single local rule suggestion into Monarch |
| `monarch list-monarch-rules` | List all rules currently stored in Monarch |
| `monarch delete-monarch-rule <id>` | Delete a rule from Monarch by ID |

### Portfolio

| Command | Description |
|---|---|
| `monarch portfolio` | Fetch and display portfolio holdings and allocation |

---

## Taxonomy

`taxonomy/canonical-taxonomy.yaml` provides a reference category structure for Monarch Money — 71 categories across 15 groups with migration mappings from legacy Monarch categories.

Use it as a starter for your own taxonomy cleanup, or load it into the cleanup workflow:

```bash
monarch cleanup-plan
monarch apply-cleanup
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
