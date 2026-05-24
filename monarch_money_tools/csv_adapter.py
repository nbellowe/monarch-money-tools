from __future__ import annotations

import csv
import re
from pathlib import Path

from .models import ImportResult


def import_transactions_from_csv(csv_path: Path) -> ImportResult:
    accounts: dict[str, dict[str, object]] = {}
    categories: dict[str, dict[str, object]] = {}
    transactions: list[dict[str, object]] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for index, record in enumerate(reader, start=1):
            if not record or not any((value or "").strip() for value in record.values()):
                continue

            account_name = clean(record.get("Account"))
            category_name = clean(record.get("Category"))
            merchant_name = clean(record.get("Merchant"))
            original_name = clean(record.get("Original Statement")) or merchant_name
            account_id = slugify(account_name, "account")
            category_id = slugify(category_name, "category")

            if account_name and account_id not in accounts:
                accounts[account_id] = {
                    "id": account_id,
                    "displayName": account_name,
                    "institutionName": "",
                    "type": "",
                    "subtype": "",
                    "isHidden": False,
                }

            if category_name and category_id not in categories:
                categories[category_id] = {
                    "id": category_id,
                    "name": category_name,
                    "groupName": infer_category_group(category_name),
                }

            transactions.append(
                {
                    "id": f"csv-{index}",
                    "date": clean(record.get("Date")),
                    "amount": clean(record.get("Amount")),
                    "merchantName": merchant_name,
                    "originalName": original_name,
                    "categoryId": category_id,
                    "category": {
                        "id": category_id,
                        "name": category_name,
                        "group": {"name": infer_category_group(category_name)},
                    },
                    "accountId": account_id,
                    "account": {"id": account_id, "displayName": account_name},
                    "owner": clean(record.get("Owner")),
                    "notes": clean(record.get("Notes")),
                    "tags": [{"name": tag} for tag in split_tags(clean(record.get("Tags")))],
                    "needsReview": False,
                    "reviewStatus": "",
                    "isReviewed": False,
                    "isPending": False,
                }
            )

    return ImportResult(
        transactions=transactions,
        accounts=list(accounts.values()),
        categories=list(categories.values()),
    )


def clean(value: object | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def split_tags(value: str) -> list[str]:
    if not value.strip():
        return []
    return [tag.strip() for tag in re.split(r"[|,;]", value) if tag.strip()]


def slugify(value: str, fallback_prefix: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or f"{fallback_prefix}-unknown"


def infer_category_group(category_name: str) -> str:
    normalized = category_name.lower()
    if "transfer" in normalized or "payment" in normalized:
        return "Transfers"
    if "buy" in normalized or "sell" in normalized or "investment" in normalized:
        return "Investments"
    if "income" in normalized or "paycheck" in normalized:
        return "Income"
    return "Imported"
