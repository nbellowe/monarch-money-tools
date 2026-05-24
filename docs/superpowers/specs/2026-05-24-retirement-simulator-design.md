# Retirement Simulator: Config-Driven HTML Generator

**Date:** 2026-05-24  
**Issues:** #1 (profile.yaml), #3 (monarch retire command)  
**Status:** Approved design, ready for implementation plan

---

## Problem

`retirement_simulator.html` is a sophisticated single-file Monte Carlo retirement simulator with Chart.js visualizations. It was excluded from the OSS release because it hardcodes personal data: two people's names, ages, salaries, RSU grants, portfolio balance, and Social Security estimates in a `DEFAULT` config object.

The goal is to make it usable by anyone: a `profile.yaml` config file drives the defaults, and `monarch retire` generates a personalized HTML file from a generic template.

---

## Approach: Pydantic Profile + JSON Injection

Three new pieces, each building on the last:

```
profile.yaml  →  profile.py (load + validate)  →  retire.py (generate HTML)
                      ↓
                monarch init-profile  (write starter yaml)
                monarch retire        (write reports/retirement/simulation.html)
```

No new dependencies. Pydantic is already used in `models.py`. HTML injection uses plain string replacement against two sentinel comments.

---

## New Files

| Path | Purpose |
|------|---------|
| `monarch_money_tools/profile.py` | `UserProfile` Pydantic model, `load_profile()`, `find_profile()` |
| `monarch_money_tools/retire.py` | Maps `UserProfile` → HTML DEFAULT dict, injects into template |
| `monarch_money_tools/templates/retirement_simulator.html` | Generic template (no personal data) |
| `tests/test_profile.py` | Profile loading and validation tests |
| `tests/test_retire.py` | HTML generation tests |
| `tests/fixtures/profile.yaml` | Minimal fixture profile for tests |

`cli.py` gets two new commands: `init-profile` and `retire`.

---

## profile.yaml Schema

Lives in the working directory (alongside `data/`, `reports/`). All fields have defaults so `monarch init-profile` produces a fully functional starter file.

```yaml
people:
  primary:
    name: Alex
    current_age: 35
    retire_at: 55
  spouse:              # optional — omit for single-person households
    name: Jordan
    current_age: 37
    retire_at: 57

portfolio:
  total: 500000

income:
  primary_salary: 120000
  primary_rsus_annual: 0
  spouse_salary: 0
  spouse_rsus_annual: 0
  rsu_vesting_years: 4
  income_growth_real: 0.02
  effective_income_tax: 0.28

spending:
  base_annual: 80000
  retirement_fraction: 0.85
  growth_real: 0.005
  healthcare_annual: 15000
  medicare_age: 65
  flexible: false
  floor: 0.75
  ceiling: 1.20

kids:
  count: 0
  first_kid_year: 0
  childcare_annual: 25000
  k12_annual: 5000
  college_contribution: 50000

social_security:
  primary_annual: 20000
  spouse_annual: 0
  claim_age: 67
  reduction_factor: 1.0

house:
  upgrade: false
  upgrade_year: 5
  upgrade_additional_cost: 0

market:
  equity_return_nominal: 0.09
  equity_std: 0.17
  bond_return_nominal: 0.04
  inflation: 0.03
  equity_fraction_working: 0.85
  equity_fraction_retired: 0.60
  use_historical_returns: false

simulation:
  swr: 0.04
  years: 70
  mc_runs: 300
  guardrails:
    upper: 0.05
    lower: 0.03
    cut: 0.10
```

---

## profile.py Module

```python
# Key API
def find_profile(start: Path | None = None) -> Path | None:
    """Search ./profile.yaml then ~/.config/monarch-money-tools/profile.yaml"""

def load_profile(path: Path | None = None) -> UserProfile:
    """Load and validate profile.yaml. Raises ProfileNotFoundError or ValidationError."""
```

**Pydantic models** (nested, one per schema section):
- `PersonConfig` — name, current_age, retire_at
- `PeopleConfig` — primary: PersonConfig, spouse: Optional[PersonConfig]
- `PortfolioConfig`, `IncomeConfig`, `SpendingConfig`, `KidsConfig`
- `SocialSecurityConfig`, `HouseConfig`, `MarketConfig`, `SimulationConfig`
- `UserProfile` — root model composing all sections

All section models have field-level defaults so partial configs are valid. `ProfileNotFoundError` (a `typer.Exit`-friendly exception) is raised when no file is found, with a message pointing to `monarch init-profile`.

---

## retire.py Module

```python
def profile_to_html_defaults(profile: UserProfile) -> dict:
    """Map UserProfile → the flat dict matching the HTML DEFAULT config keys."""

def generate_retirement_html(profile: UserProfile, template_path: Path) -> str:
    """Read template, inject DEFAULT dict + person meta, return complete HTML string."""
```

**Injection points in the template HTML:**

```javascript
// Injection point 1 — DEFAULT config block
const DEFAULT = /* __MONARCH_DEFAULT__ */ {};

// Injection point 2 — person meta (names, title, subtitle)
const MONARCH_META = /* __MONARCH_META__ */ {};
```

`generate_retirement_html` replaces each sentinel with real JSON. The HTML JS reads `MONARCH_META` to set the page title, header subtitle, and slider labels dynamically at load time.

The mapping from profile fields to HTML DEFAULT keys:
- `people.primary.current_age` → `nathanAge` (internal names kept; labels come from meta)
- `people.spouse.current_age` → `tanyaAge` (defaults to primary age if no spouse)
- `people.primary.retire_at` → `retireNathanAge`
- `income.primary_salary` → `nathanSalaryBase`
- etc. — full 1:1 mapping in `profile_to_html_defaults()`

**No-spouse behavior:** When `people.spouse` is omitted, `MONARCH_META.hasSpouse` is `false`. The HTML hides all spouse-specific sliders (salary, RSU, retire age, SS benefit) via a CSS class toggled at load time. The simulation still runs correctly since spouse income/spend contributions become zero.

---

## CLI Commands

### `monarch init-profile`

Writes a heavily-commented `profile.yaml` to `./profile.yaml`. If the file already exists, prompts before overwriting. The comments are the primary user documentation — each field explains its purpose and units.

### `monarch retire [--profile PATH] [--output PATH] [--open]`

1. Locate `profile.yaml` via `find_profile()` or `--profile`
2. Load and validate with `load_profile()` — clear Pydantic error messages on failure
3. Generate HTML via `generate_retirement_html()`
4. Write to `reports/retirement/simulation.html` (default) or `--output`
5. Print output path; `--open` launches default browser

Follows the existing `run_async()` / `paths.py` patterns in `cli.py`.

---

## HTML Template Changes

The template is `retirement_simulator.html` with three modifications from the original:

1. **Injection sentinels** replace the hardcoded `DEFAULT` block and add the `MONARCH_META` block
2. **Generic neutral defaults** in the sentinel fallback (zero balances, age 35/37, `$0` salaries) — safe to commit
3. **Dynamic labels** — "Nathan retires at age" becomes a JS-rendered label using `MONARCH_META.person1` and `MONARCH_META.person2`; the page title and header subtitle likewise

The template is included as package data:

```toml
# pyproject.toml
[tool.setuptools.package-data]
monarch_money_tools = ["templates/*.html"]
```

---

## Testing

**`tests/fixtures/profile.yaml`** — minimal valid profile (primary only, no spouse, zero balances)

**`tests/test_profile.py`**
- Load valid single-person profile → assert field values
- Load valid couple profile → assert spouse present
- Load profile with spouse omitted → spouse is None
- Missing file → ProfileNotFoundError with helpful message
- Bad field type → Pydantic ValidationError

**`tests/test_retire.py`**
- `profile_to_html_defaults()` with fixture profile → assert key DEFAULT fields match
- `generate_retirement_html()` → assert sentinel markers absent in output
- Assert person name from profile appears in output HTML
- Assert `portfolio.total` from profile appears in DEFAULT JSON in output

---

## Acceptance Criteria

- `monarch init-profile` writes a valid, commented `profile.yaml` with no personal data
- `monarch retire` with no args finds `profile.yaml` in cwd and produces a valid HTML file
- Opening the generated HTML in a browser shows the correct person names and default values
- All fields are sourced from `profile.yaml` — no hardcoded personal values in the template
- `monarch retire` fails with a clear message when `profile.yaml` is missing
- All 15 existing tests still pass; new tests bring total to ~25
- `profile.yaml` is added to `.gitignore` (contains personal financial data)
