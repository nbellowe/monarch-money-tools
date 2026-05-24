from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from monarch_money_tools.csv_adapter import import_transactions_from_csv
from monarch_money_tools.normalizer import (
    normalize_accounts,
    normalize_categories,
    normalize_transactions,
)
from monarch_money_tools.storage import write_json

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "monarch_transactions.csv"


def _write_normalized_bundle(root: Path) -> dict[str, Any]:
    imported = import_transactions_from_csv(FIXTURE_CSV)
    bundle: dict[str, Any] = {
        "transactions": normalize_transactions(
            imported.transactions, imported.accounts, imported.categories
        ),
        "accounts": normalize_accounts(imported.accounts),
        "categories": normalize_categories(imported.categories),
        "transactionRules": [],
    }
    write_json(root / "data/normalized/latest/bundle.json", bundle)
    return bundle


@pytest.fixture
def normalized_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Write a normalized fixture bundle under the temp repo root."""
    monkeypatch.chdir(tmp_path)
    return _write_normalized_bundle(tmp_path)


@pytest.fixture
def monarch_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a temp repo root populated with the fixture bundle."""
    monkeypatch.chdir(tmp_path)
    _write_normalized_bundle(tmp_path)
    return tmp_path
