from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from monarch_money_tools.cmd.cleanup import cleanup_app
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


def test_apply_cleanup_plan_emits_receipt(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.taxonomy_cleanup import apply_cleanup_plan

    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t4", "categoryName": "Misc Shopping", "needsReview": False}],
        "categories": [
            {"id": "c4", "name": "Misc Shopping"},
            {"id": "c5", "name": "Shopping"},
        ],
    }
    candidates = [
        {
            "transactionId": "t4",
            "merchantName": "Target",
            "suggestedCategory": "Shopping",
            "categoryId": "c5",
            "setNeedsReview": False,
        }
    ]
    with (
        patch(
            "monarch_money_tools.taxonomy_cleanup.apply_transaction_updates",
            new_callable=AsyncMock,
        ) as mock_apply,
        patch("monarch_money_tools.taxonomy_cleanup.load_bundle", return_value=mini_bundle),
    ):
        mock_apply.return_value = [{"id": "t4"}]
        result = asyncio.run(apply_cleanup_plan(candidates))

    assert result["appliedCount"] == 1
    receipts = list((tmp_path / "data" / "cleanup" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1


def test_cleanup_revert_no_receipt_exits_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cleanup_app, ["revert"])
    assert result.exit_code == 1
    assert "No revert receipt found" in result.output


def test_cleanup_revert_dry_run_shows_table(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.paths import cleanup_revert_dir
    from monarch_money_tools.revert import build_revert_receipt, write_revert_receipt

    monkeypatch.chdir(tmp_path)
    receipt = build_revert_receipt(
        "monarch cleanup apply",
        [
            {
                "type": "update_transaction",
                "entityId": "txn-2",
                "merchantName": "Target",
                "before": {
                    "categoryId": "cat-4",
                    "categoryName": "Misc Shopping",
                    "needsReview": False,
                },
                "after": {
                    "categoryId": "cat-5",
                    "categoryName": "Shopping",
                    "needsReview": False,
                },
            }
        ],
    )
    write_revert_receipt(cleanup_revert_dir(), receipt)

    runner = CliRunner()
    result = runner.invoke(cleanup_app, ["revert", "--dry-run"])
    assert result.exit_code == 0
    assert "Target" in result.output
