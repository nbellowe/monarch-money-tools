from __future__ import annotations

from pathlib import Path

SAMPLE_PROFILE = (
    Path(__file__).parent.parent / "docs" / "retirement-simulator" / "sample-profile.yaml"
)
SAMPLE_HTML_OUT = Path(__file__).parent.parent / "docs" / "retirement-simulator" / "sample.html"
GENERATE_SCRIPT = Path(__file__).parent.parent / "scripts" / "generate_sample_html.py"


def test_sample_profile_exists():
    assert SAMPLE_PROFILE.exists(), f"Missing: {SAMPLE_PROFILE}"


def test_generate_script_exists():
    assert GENERATE_SCRIPT.exists(), f"Missing: {GENERATE_SCRIPT}"


def test_generate_sample_html_produces_valid_output():
    """Running the generator against the sample profile produces HTML
    with no unreplaced sentinels and correct name injection."""
    from monarch_money_tools.profile import load_profile
    from monarch_money_tools.retire import generate_retirement_html

    profile = load_profile(SAMPLE_PROFILE)
    html = generate_retirement_html(profile)

    # Sentinels must be replaced
    assert "/* __MONARCH_DEFAULT__ */ {}" not in html
    assert "/* __MONARCH_META__ */ {}" not in html

    # Names appear in the injected JSON
    assert '"Alex"' in html
    assert '"Jordan"' in html

    # Chart.js CDN script tag present
    assert "chart.js" in html.lower()
