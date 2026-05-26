from __future__ import annotations

from pathlib import Path

from .csv_adapter import import_transactions_from_csv
from .env import get_config
from .normalizer import (
    normalize_accounts,
    normalize_categories,
    normalize_transaction_rules,
    normalize_transactions,
)
from .paths import (
    exported_dir,
    normalized_latest_dir,
    private_exports_dir,
    raw_history_dir,
    raw_latest_dir,
)
from .storage import (
    iso_date,
    latest_csv_path,
    now_iso,
    reset_dir,
    timestamp_slug,
    write_csv,
    write_json,
)


def run_export(csv_path: Path | None = None) -> Path:
    config = get_config()
    resolved_csv = csv_path or resolve_csv_path(config.monarch_csv_path)
    if resolved_csv is None:
        raise FileNotFoundError(
            "No Monarch CSV found. Pass a CSV path or place one in exported/ "
            "or private/monarch/exports/."
        )

    imported = import_transactions_from_csv(resolved_csv)
    exported_at = now_iso()
    raw_bundle = {
        "exportedAt": exported_at,
        "dateRange": {"startDate": config.monarch_start_date, "endDate": iso_date()},
        "source": {"type": "csv", "path": str(resolved_csv)},
        "transactions": imported.transactions,
        "transactionRules": [],
        "accounts": imported.accounts,
        "categories": imported.categories,
        "budgets": None,
        "cashflowSummary": None,
        "netWorthHistory": None,
    }
    normalized_bundle = {
        "exportedAt": exported_at,
        "dateRange": raw_bundle["dateRange"],
        "transactions": normalize_transactions(
            raw_bundle["transactions"], raw_bundle["accounts"], raw_bundle["categories"]
        ),
        "transactionRules": normalize_transaction_rules(raw_bundle["transactionRules"]),
        "accounts": normalize_accounts(raw_bundle["accounts"]),
        "categories": normalize_categories(raw_bundle["categories"]),
        "budgets": None,
        "cashflowSummary": None,
        "netWorthHistory": None,
    }

    raw_history = raw_history_dir() / timestamp_slug()
    reset_dir(raw_latest_dir())
    reset_dir(normalized_latest_dir())
    raw_history.mkdir(parents=True, exist_ok=True)

    write_json(raw_history / "bundle.json", raw_bundle)
    write_json(raw_latest_dir() / "bundle.json", raw_bundle)
    write_json(normalized_latest_dir() / "bundle.json", normalized_bundle)
    write_json(normalized_latest_dir() / "transactions.json", normalized_bundle["transactions"])
    write_json(
        normalized_latest_dir() / "transaction-rules.json", normalized_bundle["transactionRules"]
    )
    write_json(normalized_latest_dir() / "accounts.json", normalized_bundle["accounts"])
    write_json(normalized_latest_dir() / "categories.json", normalized_bundle["categories"])
    write_csv(normalized_latest_dir() / "transactions.csv", normalized_bundle["transactions"])
    write_csv(
        normalized_latest_dir() / "transaction-rules.csv", normalized_bundle["transactionRules"]
    )
    write_csv(normalized_latest_dir() / "accounts.csv", normalized_bundle["accounts"])
    write_csv(normalized_latest_dir() / "categories.csv", normalized_bundle["categories"])

    return normalized_latest_dir() / "bundle.json"


def resolve_csv_path(configured_path: str | None) -> Path | None:
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return latest_csv_path([private_exports_dir(), exported_dir()])


