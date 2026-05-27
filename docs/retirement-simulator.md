# Retirement Simulator

monarch-money-tools can generate a personalized, self-contained retirement simulation as a
single HTML file — no server required. Open it in any browser. It runs a Monte Carlo
simulation with Chart.js visualizations entirely client-side.
The generated UI exposes every field in the starter `profile.yaml`, including
the return model, withdrawal strategy, and guardrail settings.
Its scenario shortcuts are grouped by assumption type, so you can compose changes
such as historical returns plus Guyton-Klinger withdrawals plus lean spending.
The same settings are also editable as a profile-shaped YAML blob in the generated
HTML; applying YAML updates the sliders and buttons, and changing controls refreshes
the YAML.

[**See a live example →**](retirement-simulator/sample.html){ .md-button .md-button--primary }

---

## How It Works

The simulator reads a `profile.yaml` file you maintain locally and injects your numbers into
a parameterized HTML template. The output HTML is fully standalone: it loads Chart.js and
YAML parsing from CDNs and runs the simulation in your browser each time you open the file.

---

## Quick Start

```bash
# 1. Create a starter profile in your current directory
monarch init-profile

# 2. Edit profile.yaml with your real numbers
open profile.yaml

# 3. Generate the simulation HTML
monarch retire

# 4. Open it in your browser
open reports/retirement/simulation.html
```

---

## profile.yaml Reference

All monetary values are in **today's dollars** (real, before inflation). The simulator applies
inflation internally.

### People

```yaml
people:
  primary:
    name: Alex          # Displayed in chart labels
    current_age: 35
    retire_at: 52

  spouse:               # Optional — comment out if single
    name: Jordan
    current_age: 33
    retire_at: 50
```

### Portfolio & Income

```yaml
portfolio:
  total: 850000         # Total investable assets today ($)

income:
  primary_salary: 185000
  primary_rsus_annual: 60000    # Annual RSU grant value at full vest
  spouse_salary: 140000
  spouse_rsus_annual: 40000
  rsu_vesting_years: 4
  income_growth_real: 0.02      # Real annual income growth
  effective_income_tax: 0.30
```

### Spending

```yaml
spending:
  base_annual: 130000           # Annual spending during working years
  retirement_fraction: 0.80     # Retirement spending as fraction of above
  growth_real: 0.005            # Real annual spending growth
  healthcare_annual: 20000      # Pre-Medicare annual healthcare cost
  medicare_age: 65
  floor: 0.75                   # Minimum spend fraction (guardrail lower)
  ceiling: 1.20                 # Maximum spend fraction (guardrail upper)
```

### Kids, House, Social Security

```yaml
kids:
  count: 2
  first_kid_year: 2             # Years from now until first child
  childcare_annual: 30000       # Per child, ages 0–5
  k12_annual: 8000              # Per child, per year
  college_contribution: 75000   # Lump sum per child

house:
  upgrade: true
  upgrade_year: 3               # Years from now
  upgrade_additional_cost: 500000

social_security:
  primary_annual: 28000         # Estimated annual benefit at claim age
  spouse_annual: 22000
  claim_age: 67
  reduction_factor: 0.85        # Apply uncertainty (85% of estimate)
```

### Market

```yaml
market:
  equity_return_nominal: 0.09
  equity_std: 0.17
  bond_return_nominal: 0.04
  inflation: 0.03
  equity_fraction_working: 0.85
  equity_fraction_retired: 0.60
```

### Simulation Settings

```yaml
simulation:
  method: monte_carlo                # monte_carlo, historical_bootstrap, deterministic
  withdrawal_strategy: guardrails     # constant_dollar, percent_portfolio, one_over_n, guardrails, guyton_klinger, vanguard_dynamic
  withdrawal_rate: 0.04               # Target rate for variable strategies
  swr: 0.04                           # Safe withdrawal rate threshold
  years: 70                           # Horizon (primary.current_age + years)
  mc_runs: 500                        # Stochastic iterations
  guardrails:
    upper: 0.05   # Withdrawal rate above this cuts spending
    lower: 0.03   # Withdrawal rate below this can raise spending
    cut: 0.10
  dynamic_spending:
    floor: -0.025 # Max annual cut for Vanguard-style dynamic spending
    ceiling: 0.05 # Max annual raise for Vanguard-style dynamic spending
  guyton_klinger:
    capital_preservation: 1.20 # Cut if current rate > 120% of initial rate
    prosperity: 0.80           # Raise if current rate < 80% of initial rate
    adjustment: 0.10           # Raise/cut amount when a decision rule triggers
    sunset_years: 15           # Disable capital preservation in final N years
```

---

## Output

The simulator writes to `reports/retirement/simulation.html` by default. Pass `--output` to
specify a different path:

```bash
monarch retire --output ~/Desktop/my-retirement.html
```
