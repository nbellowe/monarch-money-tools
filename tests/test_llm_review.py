from __future__ import annotations

from monarch_money_tools.llm_review import _parse_response


def test_parse_response_accepts_fenced_json() -> None:
    parsed = _parse_response(
        """```json
[
  {"merchant_key": "mystery", "category": "Miscellaneous", "confidence": 0.7}
]
```"""
    )

    assert parsed == [
        {"merchant_key": "mystery", "category": "Miscellaneous", "confidence": 0.7}
    ]
