# Retirement Simulator: Config-Driven HTML Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `profile.yaml` config layer + `monarch init-profile` / `monarch retire` CLI commands that generate a personalized retirement simulator HTML from any user's data.

**Architecture:** `profile.py` defines a `UserProfile` Pydantic model and `load_profile()`; `retire.py` maps that model to the HTML's `DEFAULT` config and injects it into a template via two sentinel comments; `cli.py` gets two new commands.

**Tech Stack:** Python 3.11, Pydantic v2, PyYAML (already deps), Typer + Rich (already deps), single-file HTML + Chart.js (no new JS deps).

**Source HTML:** `~/Library/CloudStorage/Dropbox/Personal/Finance/monarch/retirement_simulator.html` — copy this into the package template and edit it.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `monarch_money_tools/profile.py` | Pydantic `UserProfile` model + `load_profile()` + `find_profile()` + `PROFILE_TEMPLATE` |
| Create | `monarch_money_tools/retire.py` | `profile_to_html_defaults()` + `_build_meta()` + `generate_retirement_html()` |
| Create | `monarch_money_tools/templates/retirement_simulator.html` | Generic HTML template with injection sentinels |
| Modify | `monarch_money_tools/paths.py` | Add `retirement_dir()` |
| Modify | `monarch_money_tools/cli.py` | Add `init-profile` and `retire` commands |
| Modify | `pyproject.toml` | Add `[tool.setuptools.package-data]` |
| Modify | `.gitignore` | Add `profile.yaml` |
| Create | `tests/test_profile.py` | Profile load/validate tests |
| Create | `tests/test_retire.py` | HTML generation tests |
| Create | `tests/fixtures/profile.yaml` | Minimal single-person fixture |

---

## Task 1: Bootstrap — paths.py, .gitignore, pyproject.toml

**Files:**
- Modify: `monarch_money_tools/paths.py`
- Modify: `.gitignore`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `retirement_dir()` to paths.py**

  Open `monarch_money_tools/paths.py` and append after the last function:

  ```python
  def retirement_dir() -> Path:
      return root_dir() / "reports" / "retirement"
  ```

- [ ] **Step 2: Add profile.yaml to .gitignore**

  Append to `.gitignore`:
  ```
  profile.yaml
  ```

- [ ] **Step 3: Add package-data to pyproject.toml**

  Add after `[tool.setuptools.packages.find]` block:
  ```toml
  [tool.setuptools.package-data]
  monarch_money_tools = ["templates/*.html"]
  ```

- [ ] **Step 4: Create the templates directory**

  ```bash
  mkdir -p monarch_money_tools/templates
  ```

- [ ] **Step 5: Verify tests still pass**

  ```bash
  uv run pytest -q
  ```
  Expected: all 15 tests pass.

- [ ] **Step 6: Commit**

  ```bash
  git add monarch_money_tools/paths.py .gitignore pyproject.toml monarch_money_tools/templates/
  git commit -m "feat: add retirement_dir(), package-data config, and profile.yaml to .gitignore"
  ```

---

## Task 2: profile.py — Pydantic Models + load/find

**Files:**
- Create: `tests/test_profile.py`
- Create: `tests/fixtures/profile.yaml`
- Create: `monarch_money_tools/profile.py`

- [ ] **Step 1: Create the fixture profile**

  Create `tests/fixtures/profile.yaml`:
  ```yaml
  people:
    primary:
      name: Alex
      current_age: 35
      retire_at: 55
  portfolio:
    total: 600000
  income:
    primary_salary: 130000
  ```

- [ ] **Step 2: Write failing tests**

  Create `tests/test_profile.py`:
  ```python
  from __future__ import annotations

  from pathlib import Path

  import pytest
  from pydantic import ValidationError

  from monarch_money_tools.profile import ProfileNotFoundError, UserProfile, find_profile, load_profile

  FIXTURES = Path(__file__).parent / "fixtures"


  def test_load_single_person_profile():
      profile = load_profile(FIXTURES / "profile.yaml")
      assert profile.people.primary.name == "Alex"
      assert profile.people.primary.current_age == 35
      assert profile.people.primary.retire_at == 55
      assert profile.portfolio.total == 600000
      assert profile.income.primary_salary == 130000
      assert profile.people.spouse is None


  def test_load_profile_spouse_is_none_when_omitted():
      profile = load_profile(FIXTURES / "profile.yaml")
      assert profile.people.spouse is None


  def test_load_couple_profile(tmp_path):
      p = tmp_path / "profile.yaml"
      p.write_text(
          "people:\n"
          "  primary:\n"
          "    name: Alex\n"
          "    current_age: 35\n"
          "    retire_at: 55\n"
          "  spouse:\n"
          "    name: Jordan\n"
          "    current_age: 37\n"
          "    retire_at: 57\n"
      )
      profile = load_profile(p)
      assert profile.people.spouse is not None
      assert profile.people.spouse.name == "Jordan"
      assert profile.people.spouse.current_age == 37
      assert profile.people.spouse.retire_at == 57


  def test_load_profile_uses_defaults_for_missing_sections():
      profile = load_profile(FIXTURES / "profile.yaml")
      assert profile.income.effective_income_tax == 0.28
      assert profile.market.inflation == 0.03
      assert profile.simulation.swr == 0.04
      assert profile.kids.count == 0
      assert profile.house.upgrade is False


  def test_find_profile_returns_none_when_missing(tmp_path):
      result = find_profile(tmp_path)
      assert result is None


  def test_find_profile_returns_path_when_present(tmp_path):
      p = tmp_path / "profile.yaml"
      p.write_text("people:\n  primary:\n    name: Test\n")
      result = find_profile(tmp_path)
      assert result == p


  def test_load_profile_raises_profile_not_found_error(tmp_path):
      with pytest.raises(ProfileNotFoundError, match="monarch init-profile"):
          load_profile(tmp_path / "nonexistent.yaml")


  def test_load_profile_raises_validation_error_on_bad_type(tmp_path):
      p = tmp_path / "profile.yaml"
      p.write_text("people:\n  primary:\n    current_age: not_a_number\n")
      with pytest.raises(ValidationError):
          load_profile(p)
  ```

- [ ] **Step 3: Verify tests fail**

  ```bash
  uv run pytest tests/test_profile.py -v
  ```
  Expected: `ModuleNotFoundError` or `ImportError` — `profile.py` does not exist yet.

- [ ] **Step 4: Implement `profile.py`**

  Create `monarch_money_tools/profile.py`:
  ```python
  from __future__ import annotations

  from pathlib import Path
  from typing import Optional

  import yaml
  from pydantic import BaseModel, ConfigDict, Field


  class ProfileNotFoundError(Exception):
      pass


  class PersonConfig(BaseModel):
      name: str = "Person 1"
      current_age: int = 35
      retire_at: int = 55


  class PeopleConfig(BaseModel):
      primary: PersonConfig = Field(default_factory=PersonConfig)
      spouse: Optional[PersonConfig] = None


  class PortfolioConfig(BaseModel):
      total: float = 500_000


  class IncomeConfig(BaseModel):
      primary_salary: float = 120_000
      primary_rsus_annual: float = 0
      spouse_salary: float = 0
      spouse_rsus_annual: float = 0
      rsu_vesting_years: int = 4
      income_growth_real: float = 0.02
      effective_income_tax: float = 0.28


  class SpendingConfig(BaseModel):
      base_annual: float = 80_000
      retirement_fraction: float = 0.85
      growth_real: float = 0.005
      healthcare_annual: float = 15_000
      medicare_age: int = 65
      flexible: bool = False
      floor: float = 0.75
      ceiling: float = 1.20


  class KidsConfig(BaseModel):
      count: int = 0
      first_kid_year: int = 0
      childcare_annual: float = 25_000
      k12_annual: float = 5_000
      college_contribution: float = 50_000


  class SocialSecurityConfig(BaseModel):
      primary_annual: float = 20_000
      spouse_annual: float = 0
      claim_age: int = 67
      reduction_factor: float = 1.0


  class HouseConfig(BaseModel):
      upgrade: bool = False
      upgrade_year: int = 5
      upgrade_additional_cost: float = 0


  class GuardrailsConfig(BaseModel):
      upper: float = 0.05
      lower: float = 0.03
      cut: float = 0.10


  class MarketConfig(BaseModel):
      equity_return_nominal: float = 0.09
      equity_std: float = 0.17
      bond_return_nominal: float = 0.04
      inflation: float = 0.03
      equity_fraction_working: float = 0.85
      equity_fraction_retired: float = 0.60
      use_historical_returns: bool = False


  class SimulationConfig(BaseModel):
      swr: float = 0.04
      years: int = 70
      mc_runs: int = 300
      guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)


  class UserProfile(BaseModel):
      model_config = ConfigDict(extra="ignore")

      people: PeopleConfig = Field(default_factory=PeopleConfig)
      portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
      income: IncomeConfig = Field(default_factory=IncomeConfig)
      spending: SpendingConfig = Field(default_factory=SpendingConfig)
      kids: KidsConfig = Field(default_factory=KidsConfig)
      social_security: SocialSecurityConfig = Field(default_factory=SocialSecurityConfig)
      house: HouseConfig = Field(default_factory=HouseConfig)
      market: MarketConfig = Field(default_factory=MarketConfig)
      simulation: SimulationConfig = Field(default_factory=SimulationConfig)


  def find_profile(start: Path | None = None) -> Path | None:
      """Search start/profile.yaml then ~/.config/monarch-money-tools/profile.yaml."""
      base = start or Path(".")
      candidates = [
          base / "profile.yaml",
          Path.home() / ".config" / "monarch-money-tools" / "profile.yaml",
      ]
      return next((p for p in candidates if p.exists()), None)


  def load_profile(path: Path | None = None) -> UserProfile:
      """Load and validate profile.yaml. Raises ProfileNotFoundError if not found."""
      resolved = path if path is not None else find_profile()
      if resolved is None or not resolved.exists():
          raise ProfileNotFoundError(
              "No profile.yaml found. Run `monarch init-profile` to create one."
          )
      raw = yaml.safe_load(resolved.read_text()) or {}
      return UserProfile.model_validate(raw)


  PROFILE_TEMPLATE = """\
  # profile.yaml — Monarch Money Tools retirement profile
  # Run `monarch retire` to generate a simulation HTML from this config.
  # All monetary values are in today's dollars (real, inflation-adjusted).

  people:
    primary:
      name: Alex              # Your first name
      current_age: 35         # Your current age
      retire_at: 55           # Target retirement age

    # Uncomment to add a spouse or partner:
    # spouse:
    #   name: Jordan
    #   current_age: 37
    #   retire_at: 57

  portfolio:
    total: 500000             # Total investable assets today ($)

  income:
    primary_salary: 120000    # Annual base salary ($)
    primary_rsus_annual: 0    # Annual RSU/equity grants at full vest ($)
    spouse_salary: 0          # Spouse annual salary (0 if no spouse)
    spouse_rsus_annual: 0     # Spouse annual RSU grants (0 if no spouse)
    rsu_vesting_years: 4      # Years to full vest (applied linearly)
    income_growth_real: 0.02  # Expected annual real income growth
    effective_income_tax: 0.28  # Effective combined income tax rate (0–1)

  spending:
    base_annual: 80000        # Annual spending during working years ($)
    retirement_fraction: 0.85 # Retirement spending as fraction of above
    growth_real: 0.005        # Annual real spending growth rate
    healthcare_annual: 15000  # Annual pre-Medicare healthcare cost ($)
    medicare_age: 65          # Age Medicare begins
    flexible: false           # Enable guardrail-based flexible spending
    floor: 0.75               # Minimum spending as fraction of baseline
    ceiling: 1.20             # Maximum spending as fraction of baseline

  kids:
    count: 0                  # Number of children
    first_kid_year: 0         # Years from now until first child
    childcare_annual: 25000   # Childcare cost per child per year (ages 0–5)
    k12_annual: 5000          # Incremental K–12 cost per child per year
    college_contribution: 50000  # Lump-sum college contribution per child

  social_security:
    primary_annual: 20000     # Estimated annual SS benefit at claim age ($)
    spouse_annual: 0          # Spouse SS benefit (0 if no spouse)
    claim_age: 67             # Age to begin claiming SS benefits
    reduction_factor: 1.0     # Uncertainty factor: 0.75 = 75% of estimate

  house:
    upgrade: false            # Include a future home upgrade scenario
    upgrade_year: 5           # Years from now for the upgrade
    upgrade_additional_cost: 0  # Additional cost above current home ($)

  market:
    equity_return_nominal: 0.09   # Expected nominal annual equity return
    equity_std: 0.17              # Equity return standard deviation
    bond_return_nominal: 0.04     # Expected nominal annual bond return
    inflation: 0.03               # Expected annual inflation rate
    equity_fraction_working: 0.85 # Equity allocation during working years
    equity_fraction_retired: 0.60 # Equity allocation in retirement
    use_historical_returns: false # Use bootstrapped historical returns

  simulation:
    swr: 0.04     # Safe withdrawal rate (planning threshold, not actual spend)
    years: 70     # Simulation horizon in years
    mc_runs: 300  # Monte Carlo iterations
    guardrails:
      upper: 0.05   # Withdraw rate above this → can increase spend
      lower: 0.03   # Withdraw rate below this → cut spend by `cut`
      cut: 0.10     # Spending cut when lower guardrail triggers
  """
  ```

- [ ] **Step 5: Verify tests pass**

  ```bash
  uv run pytest tests/test_profile.py -v
  ```
  Expected: 8 tests pass.

- [ ] **Step 6: Run full suite**

  ```bash
  uv run pytest -q
  ```
  Expected: all 23 tests pass (15 original + 8 new).

- [ ] **Step 7: Commit**

  ```bash
  git add monarch_money_tools/profile.py tests/test_profile.py tests/fixtures/profile.yaml
  git commit -m "feat: add UserProfile Pydantic model, load_profile, find_profile, PROFILE_TEMPLATE"
  ```

---

## Task 3: retire.py — profile_to_html_defaults + _build_meta

**Files:**
- Create: `tests/test_retire.py` (partial — mapping tests only)
- Create: `monarch_money_tools/retire.py` (partial — no generate_retirement_html yet)

- [ ] **Step 1: Write failing tests for mapping functions**

  Create `tests/test_retire.py`:
  ```python
  from __future__ import annotations

  from pathlib import Path

  from monarch_money_tools.profile import UserProfile
  from monarch_money_tools.retire import _build_meta, generate_retirement_html, profile_to_html_defaults


  def _profile(**kwargs) -> UserProfile:
      return UserProfile.model_validate(kwargs)


  def test_profile_to_html_defaults_single_person():
      profile = _profile(
          people={"primary": {"name": "Alex", "current_age": 35, "retire_at": 55}},
          portfolio={"total": 600000},
          income={"primary_salary": 130000},
      )
      d = profile_to_html_defaults(profile)
      assert d["nathanAge"] == 35
      assert d["retireNathanAge"] == 55
      assert d["portfolioTotal"] == 600000
      assert d["nathanSalaryBase"] == 130000
      assert d["tanyaSalaryBase"] == 0
      assert d["tanyaRsuAnnual"] == 0
      assert d["ssTanyaAnnual"] == 0


  def test_profile_to_html_defaults_tanya_age_equals_primary_when_no_spouse():
      profile = _profile(
          people={"primary": {"name": "Alex", "current_age": 40, "retire_at": 60}},
      )
      d = profile_to_html_defaults(profile)
      assert d["tanyaAge"] == 40
      assert d["retireTanyaAge"] == 60


  def test_profile_to_html_defaults_couple():
      profile = _profile(
          people={
              "primary": {"name": "Alex", "current_age": 35, "retire_at": 55},
              "spouse": {"name": "Jordan", "current_age": 37, "retire_at": 57},
          },
          income={"spouse_salary": 95000, "spouse_rsus_annual": 30000},
          social_security={"spouse_annual": 18000},
      )
      d = profile_to_html_defaults(profile)
      assert d["tanyaAge"] == 37
      assert d["retireTanyaAge"] == 57
      assert d["tanyaSalaryBase"] == 95000
      assert d["tanyaRsuAnnual"] == 30000
      assert d["ssTanyaAnnual"] == 18000


  def test_profile_to_html_defaults_maps_simulation_fields():
      profile = _profile(
          simulation={"swr": 0.035, "years": 65, "mc_runs": 500,
                      "guardrails": {"upper": 0.06, "lower": 0.025, "cut": 0.12}},
      )
      d = profile_to_html_defaults(profile)
      assert d["swr"] == 0.035
      assert d["years"] == 65
      assert d["mcRuns"] == 500
      assert d["upperGuardrail"] == 0.06
      assert d["lowerGuardrail"] == 0.025
      assert d["guardrailCut"] == 0.12


  def test_build_meta_single_person():
      profile = _profile(
          people={"primary": {"name": "Alex", "current_age": 35, "retire_at": 55}},
      )
      meta = _build_meta(profile)
      assert meta["person1Name"] == "Alex"
      assert meta["hasSpouse"] is False
      assert meta["person2Name"] == ""
      assert meta["person1CurrentAge"] == 35
      assert meta["person2CurrentAge"] is None


  def test_build_meta_couple():
      profile = _profile(
          people={
              "primary": {"name": "Alex", "current_age": 35, "retire_at": 55},
              "spouse": {"name": "Jordan", "current_age": 37, "retire_at": 57},
          }
      )
      meta = _build_meta(profile)
      assert meta["hasSpouse"] is True
      assert meta["person2Name"] == "Jordan"
      assert meta["person1CurrentAge"] == 35
      assert meta["person2CurrentAge"] == 37


  def test_generate_retirement_html_replaces_sentinels(tmp_path):
      template = tmp_path / "retirement_simulator.html"
      template.write_text(
          "<html><script>\n"
          "const DEFAULT = /* __MONARCH_DEFAULT__ */ {};\n"
          "const MONARCH_META = /* __MONARCH_META__ */ {};\n"
          "</script></html>"
      )
      profile = _profile(
          people={"primary": {"name": "Alex", "current_age": 35, "retire_at": 55}},
          portfolio={"total": 123456},
      )
      html = generate_retirement_html(profile, template)
      assert "/* __MONARCH_DEFAULT__ */ {}" not in html
      assert "/* __MONARCH_META__ */ {}" not in html
      assert "123456" in html


  def test_generate_retirement_html_contains_person_name(tmp_path):
      template = tmp_path / "retirement_simulator.html"
      template.write_text(
          "<html><script>\n"
          "const DEFAULT = /* __MONARCH_DEFAULT__ */ {};\n"
          "const MONARCH_META = /* __MONARCH_META__ */ {};\n"
          "</script></html>"
      )
      profile = _profile(
          people={"primary": {"name": "Zara", "current_age": 40, "retire_at": 60}},
      )
      html = generate_retirement_html(profile, template)
      assert "Zara" in html
  ```

- [ ] **Step 2: Verify tests fail**

  ```bash
  uv run pytest tests/test_retire.py -v
  ```
  Expected: `ImportError` — `retire.py` does not exist yet.

- [ ] **Step 3: Implement `retire.py`**

  Create `monarch_money_tools/retire.py`:
  ```python
  from __future__ import annotations

  import json
  from pathlib import Path

  from .profile import UserProfile

  _DEFAULT_SENTINEL = "/* __MONARCH_DEFAULT__ */ {}"
  _META_SENTINEL = "/* __MONARCH_META__ */ {}"


  def profile_to_html_defaults(profile: UserProfile) -> dict:
      """Map UserProfile → flat dict matching the HTML DEFAULT config keys."""
      p = profile
      spouse = p.people.spouse
      return {
          "nathanAge": p.people.primary.current_age,
          "tanyaAge": spouse.current_age if spouse else p.people.primary.current_age,
          "retireNathanAge": p.people.primary.retire_at,
          "retireTanyaAge": spouse.retire_at if spouse else p.people.primary.retire_at,
          "portfolioTotal": p.portfolio.total,
          "nathanSalaryBase": p.income.primary_salary,
          "tanyaSalaryBase": p.income.spouse_salary if spouse else 0,
          "nathanRsuAnnual": p.income.primary_rsus_annual,
          "tanyaRsuAnnual": p.income.spouse_rsus_annual if spouse else 0,
          "rsuVestingYears": p.income.rsu_vesting_years,
          "incomeGrowthReal": p.income.income_growth_real,
          "effectiveIncomeTax": p.income.effective_income_tax,
          "baseSpending": p.spending.base_annual,
          "spendingGrowthReal": p.spending.growth_real,
          "retirementSpendingFraction": p.spending.retirement_fraction,
          "healthcareAnnual": p.spending.healthcare_annual,
          "medicareAge": p.spending.medicare_age,
          "numKids": p.kids.count,
          "firstKidYear": p.kids.first_kid_year,
          "childcareAnnual": p.kids.childcare_annual,
          "k12Annual": p.kids.k12_annual,
          "collegeContribution": p.kids.college_contribution,
          "upgradeHouse": p.house.upgrade,
          "upgradeYear": p.house.upgrade_year,
          "upgradeAdditionalCost": p.house.upgrade_additional_cost,
          "ssNathanAnnual": p.social_security.primary_annual,
          "ssTanyaAnnual": p.social_security.spouse_annual if spouse else 0,
          "ssClaimAge": p.social_security.claim_age,
          "ssReductionFactor": p.social_security.reduction_factor,
          "equityReturnNominal": p.market.equity_return_nominal,
          "equityStd": p.market.equity_std,
          "bondReturnNominal": p.market.bond_return_nominal,
          "inflation": p.market.inflation,
          "useHistoricalReturns": p.market.use_historical_returns,
          "equityFractionWorking": p.market.equity_fraction_working,
          "equityFractionRetired": p.market.equity_fraction_retired,
          "swr": p.simulation.swr,
          "years": p.simulation.years,
          "mcRuns": p.simulation.mc_runs,
          "flexibleSpending": p.spending.flexible,
          "upperGuardrail": p.simulation.guardrails.upper,
          "lowerGuardrail": p.simulation.guardrails.lower,
          "guardrailCut": p.simulation.guardrails.cut,
          "spendingFloor": p.spending.floor,
          "spendingCeiling": p.spending.ceiling,
      }


  def _build_meta(profile: UserProfile) -> dict:
      """Build the MONARCH_META object for HTML label personalization."""
      spouse = profile.people.spouse
      return {
          "person1Name": profile.people.primary.name,
          "person2Name": spouse.name if spouse else "",
          "hasSpouse": spouse is not None,
          "person1CurrentAge": profile.people.primary.current_age,
          "person2CurrentAge": spouse.current_age if spouse else None,
      }


  def generate_retirement_html(profile: UserProfile, template_path: Path | None = None) -> str:
      """Read template, inject DEFAULT + MONARCH_META, return complete HTML."""
      if template_path is None:
          template_path = Path(__file__).parent / "templates" / "retirement_simulator.html"
      html = template_path.read_text()
      defaults = profile_to_html_defaults(profile)
      meta = _build_meta(profile)
      html = html.replace(_DEFAULT_SENTINEL, f"/* __MONARCH_DEFAULT__ */ {json.dumps(defaults)}")
      html = html.replace(_META_SENTINEL, f"/* __MONARCH_META__ */ {json.dumps(meta)}")
      return html
  ```

- [ ] **Step 4: Verify all retire tests pass**

  ```bash
  uv run pytest tests/test_retire.py -v
  ```
  Expected: 9 tests pass.

- [ ] **Step 5: Run full suite**

  ```bash
  uv run pytest -q
  ```
  Expected: all 32 tests pass.

- [ ] **Step 6: Commit**

  ```bash
  git add monarch_money_tools/retire.py tests/test_retire.py
  git commit -m "feat: add retire.py with profile_to_html_defaults, _build_meta, generate_retirement_html"
  ```

---

## Task 4: HTML Template — Generalize the Source HTML

**Files:**
- Create: `monarch_money_tools/templates/retirement_simulator.html`

Copy the source HTML then apply the changes listed below. Each change is shown with its unique surrounding context so you can locate it precisely.

- [ ] **Step 1: Copy source HTML to package template**

  ```bash
  cp ~/Library/CloudStorage/Dropbox/Personal/Finance/monarch/retirement_simulator.html \
     monarch_money_tools/templates/retirement_simulator.html
  ```

- [ ] **Step 2: Change the page title (line ~6)**

  Find and replace:
  ```html
  <title>Retirement Simulator · Nathan &amp; Tanya</title>
  ```
  With:
  ```html
  <title>Retirement Simulator</title>
  ```

- [ ] **Step 3: Update header subtitle (line ~284)**

  Find and replace:
  ```html
  <div class="header-sub">Nathan &amp; Tanya · Boulder CO · Real (inflation-adjusted) 2026 dollars</div>
  ```
  With:
  ```html
  <div class="header-sub" id="header-sub">Person 1 · Real (inflation-adjusted) dollars</div>
  ```

- [ ] **Step 4: Update "retireNathanAge" slider label and min value (line ~317–318)**

  Find:
  ```html
          <div class="control-label"><span>Nathan retires at age</span><span class="control-val" id="v-retireNathanAge">50</span></div>
          <input type="range" id="retireNathanAge" min="31" max="65" step="1" value="50" />
  ```
  Replace with:
  ```html
          <div class="control-label"><span><span data-person1>Person 1</span> retires at age</span><span class="control-val" id="v-retireNathanAge">55</span></div>
          <input type="range" id="retireNathanAge" min="35" max="65" step="1" value="55" />
  ```

- [ ] **Step 5: Update "retireTanyaAge" slider label, min value, and add data-spouse-only (line ~320–323)**

  Find:
  ```html
      <div class="control-group">
          <div class="control-label"><span>Tanya retires at age</span><span class="control-val" id="v-retireTanyaAge">52</span></div>
          <input type="range" id="retireTanyaAge" min="33" max="65" step="1" value="52" />
        </div>
  ```
  Replace with:
  ```html
      <div class="control-group" data-spouse-only>
          <div class="control-label"><span><span data-person2>Person 2</span> retires at age</span><span class="control-val" id="v-retireTanyaAge">57</span></div>
          <input type="range" id="retireTanyaAge" min="35" max="65" step="1" value="57" />
        </div>
  ```

- [ ] **Step 6: Update portfolioTotal slider value (line ~338–339)**

  Find:
  ```html
          <input type="range" id="portfolioTotal" min="1000000" max="20000000" step="100000" value="10354863" />
  ```
  Replace with:
  ```html
          <input type="range" id="portfolioTotal" min="0" max="20000000" step="100000" value="500000" />
  ```

- [ ] **Step 7: Update nathanSalaryBase label and value (line ~358–359)**

  Find:
  ```html
          <div class="control-label"><span>Nathan base salary</span><span class="control-val" id="v-nathanSalaryBase">$250k</span></div>
          <input type="range" id="nathanSalaryBase" min="50000" max="600000" step="10000" value="250000" />
  ```
  Replace with:
  ```html
          <div class="control-label"><span><span data-person1>Person 1</span> base salary</span><span class="control-val" id="v-nathanSalaryBase">$120k</span></div>
          <input type="range" id="nathanSalaryBase" min="0" max="600000" step="10000" value="120000" />
  ```

- [ ] **Step 8: Update tanyaSalaryBase label, value, and add data-spouse-only (line ~361–363)**

  Find:
  ```html
      <div class="control-group">
          <div class="control-label"><span>Tanya base salary</span><span class="control-val" id="v-tanyaSalaryBase">$220k</span></div>
          <input type="range" id="tanyaSalaryBase" min="50000" max="600000" step="10000" value="220000" />
        </div>
  ```
  Replace with:
  ```html
      <div class="control-group" data-spouse-only>
          <div class="control-label"><span><span data-person2>Person 2</span> base salary</span><span class="control-val" id="v-tanyaSalaryBase">$0</span></div>
          <input type="range" id="tanyaSalaryBase" min="0" max="600000" step="10000" value="0" />
        </div>
  ```

- [ ] **Step 9: Update nathanRsuAnnual label and value (line ~365–367)**

  Find:
  ```html
          <div class="control-label"><span>Nathan RSUs / year</span><span class="control-val" id="v-nathanRsuAnnual">$150k</span></div>
          <input type="range" id="nathanRsuAnnual" min="0" max="600000" step="10000" value="150000" />
  ```
  Replace with:
  ```html
          <div class="control-label"><span><span data-person1>Person 1</span> RSUs / year</span><span class="control-val" id="v-nathanRsuAnnual">$0</span></div>
          <input type="range" id="nathanRsuAnnual" min="0" max="600000" step="10000" value="0" />
  ```

- [ ] **Step 10: Update tanyaRsuAnnual label, value, and add data-spouse-only (line ~369–371)**

  Find:
  ```html
      <div class="control-group">
          <div class="control-label"><span>Tanya RSUs / year</span><span class="control-val" id="v-tanyaRsuAnnual">$120k</span></div>
          <input type="range" id="tanyaRsuAnnual" min="0" max="600000" step="10000" value="120000" />
        </div>
  ```
  Replace with:
  ```html
      <div class="control-group" data-spouse-only>
          <div class="control-label"><span><span data-person2>Person 2</span> RSUs / year</span><span class="control-val" id="v-tanyaRsuAnnual">$0</span></div>
          <input type="range" id="tanyaRsuAnnual" min="0" max="600000" step="10000" value="0" />
        </div>
  ```

- [ ] **Step 11: Update ssNathanAnnual label and value (line ~458–459)**

  Find:
  ```html
          <div class="control-label"><span>Nathan SS benefit / year</span><span class="control-val" id="v-ssNathanAnnual">$42k</span></div>
          <input type="range" id="ssNathanAnnual" min="0" max="80000" step="1000" value="42000" />
  ```
  Replace with:
  ```html
          <div class="control-label"><span><span data-person1>Person 1</span> SS benefit / year</span><span class="control-val" id="v-ssNathanAnnual">$20k</span></div>
          <input type="range" id="ssNathanAnnual" min="0" max="80000" step="1000" value="20000" />
  ```

- [ ] **Step 12: Update ssTanyaAnnual label, value, and add data-spouse-only (line ~461–463)**

  Find:
  ```html
      <div class="control-group">
          <div class="control-label"><span>Tanya SS benefit / year</span><span class="control-val" id="v-ssTanyaAnnual">$36k</span></div>
          <input type="range" id="ssTanyaAnnual" min="0" max="80000" step="1000" value="36000" />
        </div>
  ```
  Replace with:
  ```html
      <div class="control-group" data-spouse-only>
          <div class="control-label"><span><span data-person2>Person 2</span> SS benefit / year</span><span class="control-val" id="v-ssTanyaAnnual">$0</span></div>
          <input type="range" id="ssTanyaAnnual" min="0" max="80000" step="1000" value="0" />
        </div>
  ```

- [ ] **Step 13: Update survival metric subtitle (line ~592)**

  Find:
  ```html
        <div class="metric-sub">to Nathan age 101</div>
  ```
  Replace with:
  ```html
        <div class="metric-sub" id="m-survival-sub">to Person 1 age 101</div>
  ```

- [ ] **Step 14: Update FIRE metric subtitle (line ~612)**

  Find:
  ```html
        <div class="metric-sub">Nathan's age when funded</div>
  ```
  Replace with:
  ```html
        <div class="metric-sub" id="m-fire-sub">Person 1's age when funded</div>
  ```

- [ ] **Step 15: Replace the DEFAULT block with the injection sentinel (lines ~751–782)**

  Find the entire block (from `const DEFAULT = {` to the closing `};`):
  ```javascript
  const DEFAULT = {
    nathanAge: 31, tanyaAge: 33,
    retireNathanAge: 50, retireTanyaAge: 52,
    portfolioTotal: 10354863,
    nathanSalaryBase: 250000, tanyaSalaryBase: 220000,
    nathanRsuAnnual: 150000,  tanyaRsuAnnual: 120000,
    rsuVestingYears: 4,
    incomeGrowthReal: 0.02,
    effectiveIncomeTax: 0.28,
    baseSpending: 150000,
    spendingGrowthReal: 0.005,
    retirementSpendingFraction: 0.85,
    healthcareAnnual: 24000, medicareAge: 65,
    numKids: 1, firstKidYear: 3,
    childcareAnnual: 25000, k12Annual: 5000, collegeContribution: 50000,
    upgradeHouse: false, upgradeYear: 5, upgradeAdditionalCost: 500000,
    ssNathanAnnual: 42000, ssTanyaAnnual: 36000, ssClaimAge: 67,
    ssReductionFactor: 1.0,
    equityReturnNominal: 0.09, equityStd: 0.17, bondReturnNominal: 0.04,
    inflation: 0.03,
    useHistoricalReturns: false,
    equityFractionWorking: 0.85, equityFractionRetired: 0.60,
    swr: 0.04,
    years: 70,
    mcRuns: 300,
    flexibleSpending: false,
    upperGuardrail: 0.05, lowerGuardrail: 0.03,
    guardrailCut: 0.10,
    spendingFloor: 0.75, spendingCeiling: 1.20,
  };
  ```
  Replace with:
  ```javascript
  const DEFAULT = /* __MONARCH_DEFAULT__ */ {};
  const MONARCH_META = /* __MONARCH_META__ */ {};
  ```

- [ ] **Step 16: Fix the PRESETS "Retire Now" hardcoded ages (line ~1215)**

  Find:
  ```javascript
    { label: 'Retire Now',    cfg: { retireNathanAge: 31, retireTanyaAge: 33, retirementSpendingFraction: 0.90 } },
  ```
  Replace with:
  ```javascript
    { label: 'Retire Now',    cfg: { retireNathanAge: DEFAULT.nathanAge, retireTanyaAge: DEFAULT.tanyaAge, retirementSpendingFraction: 0.90 } },
  ```

- [ ] **Step 17: Update portfolio chart tooltip title to use MONARCH_META (inside updatePortfolioChart)**

  Find:
  ```javascript
          title: items => `Nathan age ${labels[items[0].dataIndex]}`,
  ```
  Replace with:
  ```javascript
          title: items => `${MONARCH_META.person1Name} age ${labels[items[0].dataIndex]}`,
  ```

- [ ] **Step 18: Add the applyMeta() function before the existing boot section**

  Find the comment `// Boot` (near the end of the `<script>` block):
  ```javascript
  // ─────────────────────────────────────────────────────────────────────────────
  // Boot
  // ─────────────────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
  ```
  Replace with:
  ```javascript
  // ─────────────────────────────────────────────────────────────────────────────
  // Meta — apply person names and hide spouse controls from MONARCH_META
  // ─────────────────────────────────────────────────────────────────────────────
  function applyMeta() {
    const m = MONARCH_META;
    document.title = m.hasSpouse
      ? `Retirement Simulator · ${m.person1Name} & ${m.person2Name}`
      : `Retirement Simulator · ${m.person1Name}`;
    const sub = document.getElementById('header-sub');
    if (sub) sub.textContent = m.hasSpouse
      ? `${m.person1Name} & ${m.person2Name} · Real (inflation-adjusted) dollars`
      : `${m.person1Name} · Real (inflation-adjusted) dollars`;
    document.querySelectorAll('[data-person1]').forEach(el => { el.textContent = m.person1Name; });
    document.querySelectorAll('[data-person2]').forEach(el => { el.textContent = m.person2Name; });
    const survivalSub = document.getElementById('m-survival-sub');
    if (survivalSub) survivalSub.textContent = `to ${m.person1Name} age ${DEFAULT.nathanAge + DEFAULT.years}`;
    const fireSub = document.getElementById('m-fire-sub');
    if (fireSub) fireSub.textContent = `${m.person1Name}'s age when funded`;
    const retireN = document.getElementById('retireNathanAge');
    if (retireN) retireN.min = m.person1CurrentAge;
    const retireT = document.getElementById('retireTanyaAge');
    if (retireT) retireT.min = m.person2CurrentAge ?? m.person1CurrentAge;
    if (!m.hasSpouse) {
      document.querySelectorAll('[data-spouse-only]').forEach(el => { el.style.display = 'none'; });
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Boot
  // ─────────────────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
  ```

- [ ] **Step 19: Update the DOMContentLoaded boot sequence to call applyMeta() and syncUIFromCfg()**

  Find:
  ```javascript
  document.addEventListener('DOMContentLoaded', () => {
    renderPresets();
    bindInputs();
    scheduleRender();
  });
  ```
  Replace with:
  ```javascript
  document.addEventListener('DOMContentLoaded', () => {
    applyMeta();
    renderPresets();
    bindInputs();
    syncUIFromCfg();
    scheduleRender();
  });
  ```

- [ ] **Step 20: Verify the template opens in a browser with generic defaults**

  ```bash
  open monarch_money_tools/templates/retirement_simulator.html
  ```
  Expected: page loads, shows "Person 1" labels throughout, no "Nathan" or "Tanya" visible, sliders functional.

- [ ] **Step 21: Commit**

  ```bash
  git add monarch_money_tools/templates/retirement_simulator.html
  git commit -m "feat: add generic retirement simulator HTML template with injection sentinels"
  ```

---

## Task 5: CLI Commands — init-profile + retire

**Files:**
- Modify: `monarch_money_tools/cli.py`

- [ ] **Step 1: Add imports to cli.py**

  At the top of `cli.py`, the imports section ends with `from .rules import apply_rules_plan, build_rule_suggestions`. No changes needed there — the new commands will use inline imports.

- [ ] **Step 2: Add init-profile command to cli.py**

  Append before the final `run_async` function (before line ~904):
  ```python
  @app.command("init-profile")
  def init_profile_command(
      force: Annotated[
          bool,
          typer.Option("--force", help="Overwrite existing profile.yaml without prompting."),
      ] = False,
  ) -> None:
      """Generate a commented starter profile.yaml for retirement simulation."""
      from .profile import PROFILE_TEMPLATE

      dest = Path("profile.yaml")
      if dest.exists() and not force:
          confirmed = typer.confirm("profile.yaml already exists. Overwrite?")
          if not confirmed:
              raise typer.Abort()

      dest.write_text(PROFILE_TEMPLATE)
      console.print(f"[green]Created:[/] {dest}")
      console.print(
          "[cyan]Edit it with your details, then run `monarch retire` to generate your simulation.[/]"
      )


  @app.command("retire")
  def retire_command(
      profile_path: Annotated[
          Path | None,
          typer.Option("--profile", help="Path to profile.yaml (default: search cwd)."),
      ] = None,
      output: Annotated[
          Path | None,
          typer.Option("--output", help="Output HTML path (default: reports/retirement/simulation.html)."),
      ] = None,
      open_browser: Annotated[
          bool,
          typer.Option("--open", help="Open the generated HTML in your default browser."),
      ] = False,
  ) -> None:
      """Generate a personalized retirement simulation HTML from profile.yaml."""
      import webbrowser

      from .paths import retirement_dir
      from .profile import ProfileNotFoundError, load_profile
      from .retire import generate_retirement_html

      try:
          profile = load_profile(profile_path)
      except ProfileNotFoundError as e:
          console.print(f"[red]{e}[/]")
          raise typer.Exit(1) from e

      out_path = output or (retirement_dir() / "simulation.html")
      out_path.parent.mkdir(parents=True, exist_ok=True)
      html = generate_retirement_html(profile)
      out_path.write_text(html)
      console.print(f"[green]Retirement simulation written:[/] {out_path}")

      if open_browser:
          webbrowser.open(f"file://{out_path.absolute()}")
  ```

- [ ] **Step 3: Run full test suite**

  ```bash
  uv run pytest -q
  ```
  Expected: all 32 tests pass.

- [ ] **Step 4: Lint**

  ```bash
  uv run ruff check . && uv run ruff format --check .
  ```
  Fix any issues before committing.

- [ ] **Step 5: Manual smoke test — init-profile**

  ```bash
  cd /tmp && uv run --directory ~/src/monarch-money-tools monarch init-profile
  ```
  Expected: `Created: profile.yaml`. Open the file and verify it has commented YAML with generic defaults (no personal data).

- [ ] **Step 6: Manual smoke test — retire command**

  ```bash
  cd /tmp && uv run --directory ~/src/monarch-money-tools monarch retire --output /tmp/simulation.html --open
  ```
  Expected: `Retirement simulation written: /tmp/simulation.html`, browser opens. Verify:
  - Page title shows "Retirement Simulator · Alex"
  - Header subtitle shows "Alex · Real (inflation-adjusted) dollars"
  - Sidebar labels show "Person 1 retires at age", "Person 1 base salary", etc. → displays as "Alex retires at age"
  - No "Nathan" or "Tanya" visible anywhere
  - Sliders are functional, Monte Carlo runs

- [ ] **Step 7: Manual smoke test — couple profile**

  Edit `/tmp/profile.yaml` to uncomment the spouse section. Run `monarch retire --profile /tmp/profile.yaml --output /tmp/couple.html --open`. Verify spouse sliders appear and show "Jordan" labels.

- [ ] **Step 8: Commit**

  ```bash
  git add monarch_money_tools/cli.py
  git commit -m "feat: add monarch init-profile and monarch retire CLI commands"
  ```

---

## Task 6: Final Polish + Verification

- [ ] **Step 1: Verify full test suite**

  ```bash
  uv run pytest -v
  ```
  Expected: 32+ tests pass, none skipped.

- [ ] **Step 2: Verify monarch doctor still works**

  ```bash
  uv run monarch doctor
  ```
  Expected: no errors.

- [ ] **Step 3: Verify new commands appear in help**

  ```bash
  uv run monarch --help
  ```
  Expected: `init-profile` and `retire` listed with their docstrings.

- [ ] **Step 4: Final commit if anything was cleaned up**

  ```bash
  git add -p  # review any remaining changes
  git commit -m "chore: final polish on retirement simulator feature"
  ```

---

## Verification Checklist (Acceptance Criteria)

- [ ] `monarch init-profile` writes a valid commented `profile.yaml` with no personal data
- [ ] `monarch retire` finds `profile.yaml` in cwd and produces valid HTML
- [ ] Opening the HTML shows correct person names from profile
- [ ] No "Nathan", "Tanya", "Boulder CO", or personal financial figures in the template HTML
- [ ] `monarch retire` prints a clear error when `profile.yaml` is missing
- [ ] `--open` flag launches the browser
- [ ] `profile.yaml` is in `.gitignore`
- [ ] All 32+ tests pass with `uv run pytest`
- [ ] `uv run ruff check .` passes clean
