# monarch-money-tools

CLI for Monarch Money transaction categorization, cleanup, and rule management.

## Dev Setup

```bash
uv sync --extra dev --extra api --extra llm
uv run pytest          # run tests
uv run ruff check .    # lint
uv run ruff format .   # format
uv run monarch doctor  # check local setup
```

Tests are fixture-based and run without live credentials. All 15 tests should pass before committing.

## Architecture

```
monarch_money_tools/
  cli.py           — typer app, all commands, run_async() wrapper
  models.py        — pydantic models (Transaction, Category, Rule, etc.)
  monarch_api.py   — unofficial Monarch GraphQL adapter (optional)
  analyzer.py      — finds miscategorizations, owner issues, rule opportunities
  analysis.py      — runs analyzer, writes data/analysis/latest/
  normalizer.py    — CSV → typed transactions (monarch_transactions.csv format)
  exporter.py      — runs normalizer, writes data/normalized/latest/
  csv_adapter.py   — low-level CSV parsing
  reporter.py      — Markdown + CSV reports from analysis output
  review.py        — plan/apply Needs-Review transaction updates
  llm_review.py    — LLM-assisted categorization (Anthropic Claude)
  rules.py         — local rule suggestions, apply to Monarch
  taxonomy_cleanup.py — taxonomy migration + merchant consistency cleanup
  backup.py        — pre-operation backup of data/ and reports/
  storage.py       — read_json / write_json helpers
  paths.py         — all data directory paths (data_dir(), reports_latest_dir(), etc.)
  env.py           — loads .env, MONARCH_SESSION_TOKEN
  doctor.py        — checks for required files and config
  workbench.py     — interactive investigation helpers
```

## Data Flow

```
CSV export  →  normalizer  →  data/normalized/latest/bundle.json
                                    ↓
                              analyzer  →  data/analysis/latest/analysis.json
                                    ↓
                              reporter  →  reports/latest/{report.md, report.csv}
                                    ↓
                         review/llm_review/rules  →  data/review/latest/plan.json
                                    ↓
                              monarch_api  →  Monarch (write-back)
```

## Key Invariants

**Preview before mutation.** Every write-back generates a plan file first (`data/review/latest/`, `data/rules/latest/`, `data/cleanup/latest/`). The user reviews, then applies with `--yes` or an explicit apply command. Never batch-apply without a human-readable diff step.

**CSV-first.** All analysis commands work from `data/normalized/latest/bundle.json`. API access (`monarch pull`) is optional — users can always drop a CSV from the Monarch UI and run `monarch import`.

**Local by default.** No credentials, no financial data, no generated output should leave the machine or be tracked by git. `data/`, `reports/`, `backups/` are all gitignored.

**Unofficial API.** `monarch_api.py` uses the `monarchmoney` library against Monarch's unofficial GraphQL API. It can break without notice. All API calls go through `run_async()` in cli.py which handles rate-limit errors.

## Adding Commands

1. Add business logic to the appropriate module (not in `cli.py`)
2. Add a `@app.command("name")` in `cli.py` with a docstring — Typer renders it as `--help`
3. Use `run_async()` for any async calls; it handles rate-limit error formatting
4. Write at least one test using the fixture CSV at `tests/fixtures/monarch_transactions.csv`

## Taxonomy

`taxonomy/canonical-taxonomy.yaml` defines the canonical category structure (71 categories, 15 groups) with migration mappings from legacy Monarch categories. The `taxonomy_cleanup` module uses it to generate deterministic cleanup candidates. Edit it to add or retire categories — the `migrations` list is how old categories get remapped.
