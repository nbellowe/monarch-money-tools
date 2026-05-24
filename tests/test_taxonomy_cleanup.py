from __future__ import annotations

from pathlib import Path

from monarch_money_tools.storage import write_json
from monarch_money_tools.taxonomy_cleanup import build_taxonomy_cleanup_plan


def test_taxonomy_cleanup_builds_ready_migration_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    taxonomy = tmp_path / "data/taxonomy/canonical-taxonomy.yaml"
    taxonomy.parent.mkdir(parents=True)
    taxonomy.write_text(
        """
categories:
  - name: Auto Maintenance & Fees
    group: Auto & Transport
    analysis_treatment: spending
retirements:
  - name: Auto Maintenance
    group: Other
    action: remap_then_delete
    remap_to: Auto & Transport/Auto Maintenance & Fees
""",
        encoding="utf-8",
    )
    write_json(
        tmp_path / "data/normalized/latest/bundle.json",
        {
            "transactions": [
                {
                    "id": "txn-1",
                    "date": "2026-01-01",
                    "merchantName": "Mechanic",
                    "accountName": "Card",
                    "signedAmount": -100,
                    "categoryName": "Auto Maintenance",
                    "groupName": "Other",
                    "needsReview": False,
                    "isPending": False,
                }
            ],
            "categories": [
                {
                    "id": "cat-auto",
                    "name": "Auto Maintenance & Fees",
                    "groupName": "Auto & Transport",
                }
            ],
        },
    )

    plan = build_taxonomy_cleanup_plan()

    assert plan["summary"]["readyCount"] == 1
    assert plan["candidates"][0]["categoryId"] == "cat-auto"
    assert plan["candidates"][0]["requiresNewCategory"] is False
