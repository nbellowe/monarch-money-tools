# Docs Site Design

**Date:** 2026-05-24
**Issue:** #14 (docs site + sample retirement.html)
**Status:** Approved design, ready for implementation plan

---

## Problem

monarch-money-tools has a detailed README but no user-facing documentation site. The CLI has grown to ~30 commands and a retirement simulator feature that produces a standalone HTML file — both deserve proper docs. The goal is a public GitHub Pages site with an auto-regenerating sample retirement simulation.

---

## Solution

MkDocs + Material theme deployed to GitHub Pages via GitHub Actions. Sample retirement HTML is generated from fictional profile data and regenerated in CI on every push to `main`.

---

## File Structure

```
mkdocs.yml                              # MkDocs config at repo root
docs/
  index.md                              # Overview, quick-start workflow
  install.md                            # Prerequisites, install, auth setup
  commands.md                           # Full CLI command reference tables
  retirement-simulator.md               # Simulator guide + link to sample
  retirement-simulator/
    sample-profile.yaml                 # Fictional Alex & Jordan profile
    sample.html                         # Pre-generated; regenerated in CI
  superpowers/                          # Internal design specs (excluded from nav)
    specs/
      ...
scripts/
  generate_sample_html.py               # Loads sample-profile.yaml, writes sample.html
.github/
  workflows/
    docs.yml                            # CI: regen sample HTML + mkdocs gh-deploy
```

---

## Content Plan

### `docs/index.md`
- One-paragraph description of what the tool does
- Badges (license badge from shields.io, Python version — no PyPI badge since it's not published)
- Quick-start workflow (the 5-step sequence from README)
- Link to install and commands pages

### `docs/install.md`
- Prerequisites (Python 3.11+, uv)
- Install command (`uv tool install .`)
- Dev install (`uv sync --extra dev ...`)
- Auth setup (session token, DevTools steps, .env file)

### `docs/commands.md`
- All command reference tables from README, organized by group:
  Data, Reviews, Cleanup, Rules, Portfolio, Retirement

### `docs/retirement-simulator.md`
- What the simulator does (Monte Carlo, Chart.js, profile-driven)
- Step-by-step: `monarch init-profile` → edit `profile.yaml` → `monarch retire`
- Configuration reference: key profile.yaml fields explained
- Prominent link to `retirement-simulator/sample.html` ("See a live example →")
- Note about future goal: web-usable without CLI

---

## Sample HTML Generation

**Approach:** A `scripts/generate_sample_html.py` script that:
1. Loads `docs/retirement-simulator/sample-profile.yaml` via `UserProfile.from_yaml()`
2. Calls `generate_retirement_html(profile)` from `retire.py`
3. Writes the result to `docs/retirement-simulator/sample.html`

**Sample profile (Alex & Jordan):** Two-person scenario with spouse, two kids, RSUs, house upgrade — chosen to exercise the full simulator feature set. All values are fictional and representative, not minimal defaults.

MkDocs copies `sample.html` through to the built site as-is (Chart.js loads from CDN). The page is accessible at `/retirement-simulator/sample.html` on the live site.

---

## MkDocs Configuration

```yaml
# mkdocs.yml (key settings)
site_name: monarch-money-tools
docs_dir: docs
theme:
  name: material
  palette:
    scheme: slate          # dark mode to match simulator aesthetic
    primary: deep purple
    accent: deep purple
nav:
  - Home: index.md
  - Install: install.md
  - Commands: commands.md
  - Retirement Simulator: retirement-simulator.md
  # sample.html is linked from retirement-simulator.md, not in nav
exclude_docs: |
  superpowers/**
```

The explicit `nav` ensures `docs/superpowers/` design specs do not appear in the generated site. `exclude_docs` additionally prevents them from being copied to the output.

---

## GitHub Actions Workflow

```yaml
# .github/workflows/docs.yml
on:
  push:
    branches: [main]

jobs:
  deploy-docs:
    runs-on: ubuntu-latest
    permissions:
      contents: write          # needed for gh-deploy to push gh-pages branch
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install uv && uv sync --extra docs
      - run: uv run python scripts/generate_sample_html.py
      - run: uv run mkdocs gh-deploy --force
```

**One-time GitHub setup:** Enable GitHub Pages to serve from the `gh-pages` branch (Settings → Pages → Source: gh-pages branch). This can be done via `gh api` or the UI.

---

## pyproject.toml Changes

Add a `docs` optional-dependencies group:

```toml
[project.optional-dependencies]
docs = [
  "mkdocs-material>=9.5",
]
```

---

## What's Excluded

- No taxonomy/rules documentation page (can be added later)
- No API reference generated from docstrings (overkill for this tool's scope)
- No versioning or multi-version docs
- The sample HTML is fictional — no real financial data is ever committed

---

## Future Goal

The retirement simulator HTML is already a standalone JS app (Chart.js, no server). The "web-usable without CLI" goal is achievable by adding a `<input type="file">` YAML loader in the HTML that reads a `profile.yaml` dropped by the user. This is a separate issue and does not affect the current design.
