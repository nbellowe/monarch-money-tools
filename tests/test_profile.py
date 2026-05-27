from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from monarch_money_tools.profile import ProfileNotFoundError, find_profile, load_profile

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_single_person_profile() -> None:
    profile = load_profile(FIXTURES / "profile.yaml")
    assert profile.people.primary.name == "Alex"
    assert profile.people.primary.current_age == 35
    assert profile.people.primary.retire_at == 55
    assert profile.portfolio.total == 600000
    assert profile.income.primary_salary == 130000
    assert profile.people.spouse is None


def test_load_profile_spouse_is_none_when_omitted() -> None:
    profile = load_profile(FIXTURES / "profile.yaml")
    assert profile.people.spouse is None


def test_load_couple_profile(tmp_path: Path) -> None:
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
        "    retire_at: 57\n",
        encoding="utf-8",
    )
    profile = load_profile(p)
    assert profile.people.spouse is not None
    assert profile.people.spouse.name == "Jordan"
    assert profile.people.spouse.current_age == 37
    assert profile.people.spouse.retire_at == 57


def test_load_profile_uses_defaults_for_missing_sections() -> None:
    profile = load_profile(FIXTURES / "profile.yaml")
    assert profile.income.effective_income_tax == 0.28
    assert profile.market.inflation == 0.03
    assert profile.simulation.method == "monte_carlo"
    assert profile.simulation.withdrawal_strategy == "constant_dollar"
    assert profile.simulation.withdrawal_rate == 0.04
    assert profile.simulation.swr == 0.04
    assert profile.simulation.dynamic_spending.floor == -0.025
    assert profile.simulation.dynamic_spending.ceiling == 0.05
    assert profile.simulation.guyton_klinger.capital_preservation == 1.20
    assert profile.simulation.guyton_klinger.prosperity == 0.80
    assert profile.simulation.guyton_klinger.adjustment == 0.10
    assert profile.simulation.guyton_klinger.sunset_years == 15
    assert profile.kids.count == 0
    assert profile.house.upgrade is False


def test_find_profile_returns_none_when_missing(tmp_path: Path) -> None:
    result = find_profile(tmp_path)
    assert result is None


def test_find_profile_returns_path_when_present(tmp_path: Path) -> None:
    p = tmp_path / "profile.yaml"
    p.write_text("people:\n  primary:\n    name: Test\n", encoding="utf-8")
    result = find_profile(tmp_path)
    assert result == p


def test_load_profile_raises_profile_not_found_error(tmp_path: Path) -> None:
    with pytest.raises(ProfileNotFoundError, match="monarch init-profile"):
        load_profile(tmp_path / "nonexistent.yaml")


def test_load_profile_raises_validation_error_on_bad_type(tmp_path: Path) -> None:
    p = tmp_path / "profile.yaml"
    p.write_text("people:\n  primary:\n    current_age: not_a_number\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_profile(p)
