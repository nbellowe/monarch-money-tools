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
