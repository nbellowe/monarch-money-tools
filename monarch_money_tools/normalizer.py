from __future__ import annotations

import re
from typing import Any

JsonObject = dict[str, Any]


def normalize_transactions(
    transactions: list[JsonObject],
    accounts: list[JsonObject],
    categories: list[JsonObject],
) -> list[JsonObject]:
    account_name_by_id = {
        account["id"]: account["displayName"] for account in normalize_accounts(accounts)
    }
    category_by_id = {category["id"]: category for category in normalize_categories(categories)}

    normalized: list[JsonObject] = []
    for index, record in enumerate(transactions, start=1):
        category_record = as_record(record.get("category"))
        category_id = read_string(category_record.get("id")) or read_string(
            record.get("categoryId")
        )
        category = category_by_id.get(category_id)
        merchant_record = as_record(record.get("merchant"))
        merchant_name = (
            read_string(merchant_record.get("name"))
            or read_string(record.get("merchantName"))
            or read_string(record.get("originalName"))
            or f"Unknown Merchant {index}"
        )
        account_record = as_record(record.get("account"))
        account_id = read_string(account_record.get("id")) or read_string(record.get("accountId"))
        signed_amount = read_signed_amount(record)

        normalized.append(
            {
                "id": read_string(record.get("id")) or f"transaction-{index}",
                "date": read_string(record.get("date"))
                or read_string(record.get("transactionDate")),
                "amount": abs(signed_amount),
                "signedAmount": signed_amount,
                "merchantName": merchant_name,
                "originalMerchantName": read_string(record.get("originalName")) or merchant_name,
                "normalizedMerchant": normalize_merchant_name(merchant_name),
                "categoryId": category["id"] if category else category_id,
                "categoryName": (
                    category["name"]
                    if category
                    else read_string(category_record.get("name")) or "Uncategorized"
                ),
                "groupName": (
                    category["groupName"]
                    if category
                    else read_string(as_record(category_record.get("group")).get("name"))
                ),
                "accountId": account_id,
                "accountName": account_name_by_id.get(
                    account_id, read_string(account_record.get("displayName")) or "Unknown Account"
                ),
                "owner": read_owner(record),
                "reviewStatus": read_string(record.get("reviewStatus")),
                "needsReview": bool(record.get("needsReview") or False),
                "isReviewed": bool(record.get("isReviewed") or False),
                "notes": read_string(record.get("notes")),
                "isPending": bool(record.get("isPending") or record.get("pending") or False),
                "tags": read_tags(record.get("tags")),
            }
        )

    return normalized


def normalize_accounts(accounts: list[JsonObject]) -> list[JsonObject]:
    normalized: list[JsonObject] = []
    for index, record in enumerate(accounts, start=1):
        institution = as_record(record.get("institution"))
        normalized.append(
            {
                "id": read_string(record.get("id")) or f"account-{index}",
                "displayName": read_string(record.get("displayName"))
                or read_string(record.get("name"))
                or f"Account {index}",
                "institutionName": read_string(institution.get("name"))
                or read_string(record.get("institutionName")),
                "type": read_string(record.get("type")),
                "subtype": read_string(record.get("subtype")),
                "isHidden": bool(record.get("isHidden") or False),
            }
        )
    return normalized


def normalize_categories(categories: list[JsonObject]) -> list[JsonObject]:
    normalized: list[JsonObject] = []
    for index, record in enumerate(categories, start=1):
        group = as_record(record.get("group"))
        normalized.append(
            {
                "id": read_string(record.get("id")) or f"category-{index}",
                "name": read_string(record.get("name")) or f"Category {index}",
                "groupName": read_string(group.get("name")) or read_string(record.get("groupName")),
            }
        )
    return normalized


def normalize_transaction_rules(rules: list[JsonObject]) -> list[JsonObject]:
    normalized: list[JsonObject] = []
    for index, record in enumerate(rules, start=1):
        normalized.append(
            {
                "id": read_string(record.get("id")) or f"rule-{index}",
                "name": read_string(record.get("name")) or f"Rule {index}",
                "isEnabled": bool(record.get("isEnabled") or False),
                "priority": read_number(record.get("priority")) or 0,
                "conditions": [
                    {
                        "field": read_string(as_record(condition).get("field")),
                        "operator": read_string(as_record(condition).get("operator")),
                        "value": read_string(as_record(condition).get("value")),
                    }
                    for condition in read_list(record.get("conditions"))
                ],
                "actions": [
                    {
                        "type": read_string(as_record(action).get("type")),
                        "value": read_string(as_record(action).get("value")),
                    }
                    for action in read_list(record.get("actions"))
                ],
                "createdAt": read_string(record.get("createdAt")),
                "updatedAt": read_string(record.get("updatedAt")),
            }
        )
    return normalized


def normalize_merchant_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\d+", " ", value)
    value = re.sub(r"[^a-z\s&]", " ", value)
    value = re.sub(
        r"\b(inc|llc|co|store|debit|card|pos|purchase|withdrawal|online|payment)\b",
        " ",
        value,
    )
    return re.sub(r"\s+", " ", value).strip()


def read_signed_amount(record: JsonObject) -> float:
    for key in ("signedAmount", "amount", "displayAmount", "summaryAmount"):
        parsed = read_number(record.get(key))
        if parsed is not None:
            return parsed
    return 0.0


def read_owner(record: JsonObject) -> str:
    owner = as_record(record.get("owner"))
    return (
        read_string(owner.get("name"))
        or read_string(owner.get("displayName"))
        or read_string(record.get("owner"))
        or read_string(record.get("reviewedBy"))
    )


def read_tags(value: object | None) -> list[str]:
    return [
        read_string(as_record(item).get("name")) or read_string(item)
        for item in read_list(value)
        if read_string(as_record(item).get("name")) or read_string(item)
    ]


def as_record(value: object | None) -> JsonObject:
    return value if isinstance(value, dict) else {}


def read_list(value: object | None) -> list[object]:
    return value if isinstance(value, list) else []


def read_string(value: object | None) -> str:
    return value if isinstance(value, str) else ""


def read_number(value: object | None) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = f"-{cleaned[1:-1]}"
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None
