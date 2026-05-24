from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ProfileNotFoundError(Exception):
    pass


class ProfileBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PersonConfig(ProfileBaseModel):
    name: str = "Person 1"
    current_age: int = 35
    retire_at: int = 55


class PeopleConfig(ProfileBaseModel):
    primary: PersonConfig = Field(default_factory=PersonConfig)
    spouse: PersonConfig | None = None


class PortfolioConfig(ProfileBaseModel):
    total: float = 500_000


class IncomeConfig(ProfileBaseModel):
    primary_salary: float = 120_000
    primary_rsus_annual: float = 0
    spouse_salary: float = 0
    spouse_rsus_annual: float = 0
    rsu_vesting_years: int = 4
    income_growth_real: float = 0.02
    effective_income_tax: float = 0.28


class SpendingConfig(ProfileBaseModel):
    base_annual: float = 80_000
    retirement_fraction: float = 0.85
    growth_real: float = 0.005
    healthcare_annual: float = 15_000
    medicare_age: int = 65
    flexible: bool = False
    floor: float = 0.75
    ceiling: float = 1.20


class KidsConfig(ProfileBaseModel):
    count: int = 0
    first_kid_year: int = 0
    childcare_annual: float = 25_000
    k12_annual: float = 5_000
    college_contribution: float = 50_000


class SocialSecurityConfig(ProfileBaseModel):
    primary_annual: float = 20_000
    spouse_annual: float = 0
    claim_age: int = 67
    reduction_factor: float = 1.0


class HouseConfig(ProfileBaseModel):
    upgrade: bool = False
    upgrade_year: int = 5
    upgrade_additional_cost: float = 0


class GuardrailsConfig(ProfileBaseModel):
    upper: float = 0.05
    lower: float = 0.03
    cut: float = 0.10


class MarketConfig(ProfileBaseModel):
    equity_return_nominal: float = 0.09
    equity_std: float = 0.17
    bond_return_nominal: float = 0.04
    inflation: float = 0.03
    equity_fraction_working: float = 0.85
    equity_fraction_retired: float = 0.60
    use_historical_returns: bool = False


class SimulationConfig(ProfileBaseModel):
    swr: float = 0.04
    years: int = 70
    mc_runs: int = 300
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)


class UserProfile(ProfileBaseModel):
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
    """Search start/profile.yaml, then the user config profile path."""
    base = start or Path(".")
    candidates = [
        base / "profile.yaml",
        Path.home() / ".config" / "monarch-money-tools" / "profile.yaml",
    ]
    return next((path for path in candidates if path.exists()), None)


def load_profile(path: Path | None = None) -> UserProfile:
    """Load and validate profile.yaml."""
    resolved = path if path is not None else find_profile()
    if resolved is None or not resolved.exists():
        raise ProfileNotFoundError(
            "No profile.yaml found. Run `monarch init-profile` to create one."
        )

    raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    return UserProfile.model_validate(raw)


PROFILE_TEMPLATE = """\
# profile.yaml - Monarch Money Tools retirement profile
# Run `monarch retire` to generate a simulation HTML from this config.
# All monetary values are in today's dollars, before future inflation.

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
  effective_income_tax: 0.28  # Effective combined income tax rate (0-1)

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
  childcare_annual: 25000   # Childcare cost per child per year (ages 0-5)
  k12_annual: 5000          # Incremental K-12 cost per child per year
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
    upper: 0.05   # Withdraw rate above this can increase spend
    lower: 0.03   # Withdraw rate below this cuts spend by `cut`
    cut: 0.10     # Spending cut when lower guardrail triggers
"""


__all__ = [
    "HouseConfig",
    "IncomeConfig",
    "KidsConfig",
    "MarketConfig",
    "PeopleConfig",
    "PersonConfig",
    "PortfolioConfig",
    "PROFILE_TEMPLATE",
    "ProfileNotFoundError",
    "SimulationConfig",
    "SocialSecurityConfig",
    "SpendingConfig",
    "UserProfile",
    "find_profile",
    "load_profile",
]
