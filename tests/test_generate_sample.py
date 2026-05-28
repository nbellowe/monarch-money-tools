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
    assert "js-yaml" in html.lower()

    # The generated UI exposes the full starter profile surface.
    assert 'id="simulationMethod"' in html
    assert 'id="withdrawalStrategy"' in html
    assert 'id="yamlSettings"' in html
    assert 'id="applyYaml"' in html
    assert "cfgToProfileYaml" in html
    assert "cfgFromProfileYaml" in html
    assert 'id="hasSpouse"' in html
    assert 'value="guyton_klinger"' in html
    assert 'id="gkCapitalPreservation"' in html
    assert "Return model" in html
    assert "Spending level" in html
    assert "Retirement age" in html
    assert 'id="spendingCeiling"' in html
    assert 'id="upgradeHouse"' in html
    assert 'id="sidebar-toggle"' in html
    assert "sidebar-collapsed" in html
    assert "const TOOLTIPS" in html
    assert "const SECTION_TOOLTIPS" in html
    assert "Composable shortcut groups" in html
    assert "Guyton-Klinger decision rules" in html
