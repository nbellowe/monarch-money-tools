from __future__ import annotations

from monarch_money_tools.profile import UserProfile
from monarch_money_tools.retire import (
    _build_meta,
    generate_retirement_html,
    profile_to_html_defaults,
)


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
        simulation={
            "swr": 0.035,
            "years": 65,
            "mc_runs": 500,
            "guardrails": {"upper": 0.06, "lower": 0.025, "cut": 0.12},
        },
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
