#!/usr/bin/env python3
"""Generate docs/retirement-simulator/sample.html from the fictional sample profile."""
from __future__ import annotations

from pathlib import Path

from monarch_money_tools.profile import load_profile
from monarch_money_tools.retire import generate_retirement_html

REPO_ROOT = Path(__file__).parent.parent
SAMPLE_PROFILE = REPO_ROOT / "docs" / "retirement-simulator" / "sample-profile.yaml"
OUTPUT_HTML = REPO_ROOT / "docs" / "retirement-simulator" / "sample.html"


def main() -> None:
    profile = load_profile(SAMPLE_PROFILE)
    html = generate_retirement_html(profile)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Written: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
