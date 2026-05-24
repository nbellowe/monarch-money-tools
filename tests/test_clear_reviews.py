from __future__ import annotations

from pathlib import Path

from monarch_money_tools.review import build_clear_review_plan
from monarch_money_tools.storage import write_json


def test_build_clear_review_plan_only_trusts_allowlisted_categories(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_json(
        tmp_path / "data/normalized/latest/bundle.json",
        {
            "transactions": [
                {
                    "id": "trusted",
                    "date": "2026-05-01",
                    "merchantName": "Checking Transfer",
                    "accountName": "Checking",
                    "signedAmount": 100.0,
                    "categoryName": "Transfer",
                    "needsReview": True,
                    "isPending": False,
                },
                {
                    "id": "untrusted",
                    "date": "2026-05-02",
                    "merchantName": "Mystery",
                    "accountName": "Checking",
                    "signedAmount": -50.0,
                    "categoryName": "Shopping",
                    "needsReview": True,
                    "isPending": False,
                },
            ],
            "categories": [],
            "accounts": [],
        },
    )

    plan = build_clear_review_plan(["Transfer"])

    assert plan["summary"]["plannedUpdateCount"] == 1
    assert plan["updates"][0]["transactionId"] == "trusted"
    assert plan["updates"][0]["setNeedsReview"] is False
    assert (tmp_path / "data/review/latest/clear-review-plan.json").exists()
    assert (tmp_path / "reports/latest/clear-review-plan.md").exists()
