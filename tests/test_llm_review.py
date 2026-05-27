from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from monarch_money_tools.llm_review import _parse_response


def test_parse_response_accepts_fenced_json() -> None:
    parsed = _parse_response(
        """```json
[
  {"merchant_key": "mystery", "category": "Miscellaneous", "confidence": 0.7}
]
```"""
    )

    assert parsed == [{"merchant_key": "mystery", "category": "Miscellaneous", "confidence": 0.7}]


def test_apply_llm_review_plan_emits_receipt(tmp_path, monkeypatch) -> None:
    from monarch_money_tools.llm_review import apply_llm_review_plan

    monkeypatch.chdir(tmp_path)
    mini_bundle = {
        "transactions": [{"id": "t3", "categoryName": "Uncategorized", "needsReview": True}],
        "categories": [
            {"id": "c0", "name": "Uncategorized"},
            {"id": "c3", "name": "Groceries"},
        ],
    }
    updates = [
        {
            "transactionId": "t3",
            "merchantName": "Trader Joes",
            "suggestedCategory": "Groceries",
            "categoryId": "c3",
            "confidence": 0.95,
        }
    ]
    with (
        patch(
            "monarch_money_tools.llm_review.apply_transaction_updates", new_callable=AsyncMock
        ) as mock_apply,
        patch("monarch_money_tools.llm_review.load_bundle", return_value=mini_bundle),
    ):
        mock_apply.return_value = [{"id": "t3"}]
        result = asyncio.run(apply_llm_review_plan(updates))

    assert result["appliedCount"] == 1
    receipts = list((tmp_path / "data" / "review" / "revert").glob("revert-*.json"))
    assert len(receipts) == 1
