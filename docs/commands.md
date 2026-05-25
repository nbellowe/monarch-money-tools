# Command Reference

Run `monarch --help` for the main command groups, or `monarch <group> --help` for grouped
workflows. Legacy flat commands such as `monarch plan-reviews` still work, but the grouped
commands are easier to scan.

---

## Data

| Command | Description |
|---|---|
| `monarch init` | Run the setup wizard for credentials, taxonomy, profile, and doctor checks |
| `monarch pull` / `monarch data pull` | Pull transaction data from Monarch via the unofficial API |
| `monarch import [CSV]` / `monarch data import [CSV]` | Import and normalize a Monarch transaction CSV export |
| `monarch run [CSV]` / `monarch data run [CSV]` | Import if needed, then analyze and report. With no CSV, uses existing pulled/imported data |
| `monarch data analyze` | Analyze normalized transactions for review and rule opportunities |
| `monarch data report` | Render Markdown and CSV reports from the latest analysis |
| `monarch data recurring` | Detect recurring subscriptions, bills, transfers, and price drift |
| `monarch data income-overlay` | Classify transactions into salary, reimbursement, transfer, investment, or spending |
| `monarch data backup` | Back up data/ and reports/ before destructive operations |
| `monarch doctor` / `monarch data doctor` | Check local setup and artifact availability |

---

## Reviews

| Command | Description |
|---|---|
| `monarch review plan` | Plan category updates for Needs-Review transactions |
| `monarch review apply` | Apply the latest review plan to Monarch; supports `--dry-run` |
| `monarch review clear-plan` | Plan clearing Needs-Review on trusted categories |
| `monarch review clear-apply` | Apply the clear-review plan; supports `--dry-run` |
| `monarch review llm` | Run an LLM-assisted categorization pass |
| `monarch review llm-apply` | Apply the latest LLM review plan; supports `--dry-run` |

---

## Cleanup

| Command | Description |
|---|---|
| `monarch cleanup plan` | Generate taxonomy migration and merchant-consistency candidates |
| `monarch cleanup review` | Interactively accept, reject, or skip cleanup candidates |
| `monarch cleanup apply` | Apply the latest cleanup plan to Monarch; supports `--dry-run` |

---

## Rules

| Command | Description |
|---|---|
| `monarch rules suggest` | Analyze transaction history and suggest automation rules |
| `monarch rules apply` | Apply enabled rules from the latest suggestions; supports `--dry-run` |
| `monarch rules push <id>` | Push a single local rule suggestion into Monarch |
| `monarch rules list` | List all rules currently stored in Monarch |
| `monarch rules delete <id>` | Delete a rule from Monarch by ID |

---

## Portfolio

| Command | Description |
|---|---|
| `monarch portfolio` | Fetch and display portfolio holdings and allocation |

---

## Retirement

| Command | Description |
|---|---|
| `monarch retirement init` / `monarch init-profile` | Write a starter `profile.yaml` to the current directory |
| `monarch retirement run` / `monarch retire` | Generate a personalized retirement simulation HTML from `profile.yaml` |

See the [Retirement Simulator](retirement-simulator.md) guide for full details.
