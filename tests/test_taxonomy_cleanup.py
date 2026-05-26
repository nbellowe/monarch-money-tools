from __future__ import annotations

from pathlib import Path

from monarch_money_tools.paths import canonical_taxonomy_file
from monarch_money_tools.storage import write_json
from monarch_money_tools.taxonomy_cleanup import (
    build_taxonomy_cleanup_plan,
    filter_cleanup_candidates,
)


def test_taxonomy_cleanup_builds_ready_migration_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    taxonomy = tmp_path / "taxonomy" / "canonical-taxonomy.yaml"
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


def test_canonical_taxonomy_falls_back_to_packaged_file(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)

    path = canonical_taxonomy_file()

    assert path.exists()
    assert "monarch_money_tools" in str(path)


def test_filter_cleanup_candidates_skips_blocked_by_default() -> None:
    plan = {
        "candidates": [
            {"transactionId": "t1", "requiresNewCategory": False, "source": "taxonomy_migration"},
            {"transactionId": "t2", "requiresNewCategory": True, "source": "taxonomy_migration"},
        ]
    }
    result = filter_cleanup_candidates(
        plan, decisions={}, skip_blocked=True, source=None, limit=None
    )
    assert len(result) == 1
    assert result[0]["transactionId"] == "t1"


def test_filter_cleanup_candidates_applies_decisions() -> None:
    plan = {
        "candidates": [
            {"transactionId": "t1", "requiresNewCategory": False, "source": "taxonomy_migration"},
            {"transactionId": "t2", "requiresNewCategory": False, "source": "taxonomy_migration"},
        ]
    }
    decisions = {"t1": "accepted", "t2": "rejected"}
    result = filter_cleanup_candidates(
        plan, decisions=decisions, skip_blocked=False, source=None, limit=None
    )
    assert len(result) == 1
    assert result[0]["transactionId"] == "t1"


def test_filter_cleanup_candidates_filters_by_source() -> None:
    plan = {
        "candidates": [
            {"transactionId": "t1", "requiresNewCategory": False, "source": "taxonomy_migration"},
            {"transactionId": "t2", "requiresNewCategory": False, "source": "merchant_history"},
        ]
    }
    result = filter_cleanup_candidates(
        plan, decisions={}, skip_blocked=False, source="taxonomy_migration", limit=None
    )
    assert len(result) == 1
    assert result[0]["transactionId"] == "t1"


def test_filter_cleanup_candidates_respects_limit() -> None:
    plan = {
        "candidates": [
            {"transactionId": f"t{i}", "requiresNewCategory": False, "source": "taxonomy_migration"}
            for i in range(5)
        ]
    }
    result = filter_cleanup_candidates(plan, decisions={}, skip_blocked=False, source=None, limit=2)
    assert len(result) == 2
