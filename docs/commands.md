# Command Reference

Run `monarch --help` for a full list, or `monarch <command> --help` for per-command options.

---

## Data

| Command | Description |
|---|---|
| `monarch init` | Run the setup wizard for credentials, taxonomy, profile, and doctor checks |
| `monarch pull` | Pull transaction data from Monarch via the unofficial API |
| `monarch import [CSV]` | Import and normalize a Monarch transaction CSV export |
| `monarch run [CSV]` | Import, analyze, and report in one pass |
| `monarch analyze` | Analyze normalized transactions for review and rule opportunities |
| `monarch report` | Render Markdown and CSV reports from the latest analysis |
| `monarch recurring` | Detect recurring subscriptions, bills, transfers, and price drift |
| `monarch income-overlay` | Classify transactions into salary, reimbursement, transfer, investment, or spending |
| `monarch backup` | Back up data/ and reports/ before destructive operations |
| `monarch doctor` | Check local setup and artifact availability |

---

## Reviews

| Command | Description |
|---|---|
| `monarch plan-reviews` | Plan category updates for Needs-Review transactions |
| `monarch apply-reviews` | Apply the latest review plan to Monarch; supports `--dry-run` |
| `monarch plan-clear-reviews` | Plan clearing Needs-Review on trusted categories |
| `monarch apply-clear-reviews` | Apply the clear-review plan; supports `--dry-run` |
| `monarch bulk-clear-reviews` | Plan and apply a clear-review pass in one step |
| `monarch llm-review` | Run an LLM-assisted categorization pass |
| `monarch apply-llm-review` | Apply the latest LLM review plan; supports `--dry-run` |

---

## Cleanup

| Command | Description |
|---|---|
| `monarch cleanup-plan` | Generate taxonomy migration and merchant-consistency candidates |
| `monarch review-cleanup` | Interactively accept, reject, or skip cleanup candidates |
| `monarch apply-cleanup` | Apply the latest cleanup plan to Monarch; supports `--dry-run` |

---

## Rules

| Command | Description |
|---|---|
| `monarch suggest-rules` | Analyze transaction history and suggest automation rules |
| `monarch apply-rules` | Apply enabled rules from the latest suggestions; supports `--dry-run` |
| `monarch push-rule <id>` | Push a single local rule suggestion into Monarch |
| `monarch list-monarch-rules` | List all rules currently stored in Monarch |
| `monarch delete-monarch-rule <id>` | Delete a rule from Monarch by ID |

---

## Portfolio

| Command | Description |
|---|---|
| `monarch portfolio` | Fetch and display portfolio holdings and allocation |

---

## Retirement

| Command | Description |
|---|---|
| `monarch init-profile` | Write a starter `profile.yaml` to the current directory |
| `monarch retire` | Generate a personalized retirement simulation HTML from `profile.yaml` |

See the [Retirement Simulator](retirement-simulator.md) guide for full details.
