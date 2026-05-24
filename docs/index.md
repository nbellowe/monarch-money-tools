# monarch-money-tools

A CLI for Monarch Money users who want programmatic control over transaction categorization,
cleanup, and rule management — beyond what the Monarch UI provides.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/nbellowe/monarch-money-tools/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

> **Unofficial API notice:** This tool uses Monarch Money's unofficial GraphQL API.
> It may break without notice. Not affiliated with Monarch Money.

---

## Quick Start

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

## What It Does

monarch-money-tools complements the Monarch Money UI for tasks that need bulk operations or
programmatic control:

- **Categorization:** Bulk-update miscategorized transactions, run LLM-assisted review passes
- **Rules:** Generate and apply automation rules from transaction history
- **Cleanup:** Migrate legacy categories, fix merchant-name inconsistencies
- **Retirement Simulator:** Generate a personalized Monte Carlo retirement simulation HTML from a `profile.yaml` config

→ [Install](install.md) | [Command Reference](commands.md) | [Retirement Simulator](retirement-simulator.md)
