from __future__ import annotations

from collections import Counter, defaultdict

from .monarch_api import apply_transaction_updates
from .paths import analysis_latest_dir, reports_latest_dir, review_latest_dir
from .storage import (
    JsonObject,
    load_bundle,
    now_iso,
    reset_dir,
    round2,
    write_csv,
    write_json,
    write_text,
)

EXCLUDED_AUTO_REVIEW_CATEGORY_GROUPS = {"Transfers", "Income", "Investments"}
EXCLUDED_AUTO_REVIEW_CATEGORY_NAMES = {"Uncategorized"}
DEFAULT_CLEAR_REVIEW_CATEGORIES = [
    "Transfer",
    "Credit Card Payment",
    "Buy Investment",
    "Sell Investment",
    "Interest",
    "Balance Adjustments",
    "True Up Tanya/Nathan",
]


def build_clear_review_plan(categories: list[str] | None = None) -> JsonObject:
    trusted_categories = categories or DEFAULT_CLEAR_REVIEW_CATEGORIES
    trusted = {category.strip() for category in trusted_categories if category.strip()}
    bundle = load_bundle()
    transactions = list(bundle.get("transactions") or [])

    updates: list[JsonObject] = []
    deferred: list[JsonObject] = []
    for transaction in transactions:
        if not bool(transaction.get("needsReview")):
            continue
        if bool(transaction.get("isPending")):
            deferred.append(deferred_item(transaction, "pending transaction"))
            continue
        current_category = str(transaction.get("categoryName") or "")
        if current_category not in trusted:
            deferred.append(deferred_item(transaction, "category is not trusted for review clear"))
            continue

        updates.append(
            {
                "transactionId": transaction["id"],
                "date": transaction["date"],
                "merchantName": transaction["merchantName"],
                "accountName": transaction["accountName"],
                "amount": transaction["signedAmount"],
                "currentCategory": current_category,
                "suggestedCategory": current_category,
                "categoryId": "",
                "currentNeedsReview": transaction["needsReview"],
                "setNeedsReview": False,
                "confidence": 0.99,
                "action": "clear_review",
                "rationale": (f"{current_category} is in the reviewed trusted-category allowlist."),
            }
        )

    plan = {
        "generatedAt": now_iso(),
        "summary": {
            "needsReviewCount": sum(1 for item in transactions if item.get("needsReview")),
            "plannedUpdateCount": len(updates),
            "deferredCount": len(deferred),
            "trustedCategories": sorted(trusted),
        },
        "updates": sorted(updates, key=lambda item: (item["currentCategory"], item["date"])),
        "deferred": sorted(deferred, key=lambda item: item["date"], reverse=True),
    }
    write_clear_review_plan(plan)
    return plan


async def apply_clear_review_plan(updates: list[JsonObject]) -> JsonObject:
    results = await apply_transaction_updates(updates)
    applied = {
        "appliedAt": now_iso(),
        "requestedCount": len(updates),
        "results": results,
    }
    write_json(review_latest_dir() / "clear-review-apply-results.json", applied)
    return applied


def write_clear_review_plan(plan: JsonObject) -> None:
    write_json(review_latest_dir() / "clear-review-plan.json", plan)
    write_csv(review_latest_dir() / "clear-review-plan.csv", plan["updates"])
    write_csv(review_latest_dir() / "clear-review-deferred.csv", plan["deferred"])
    markdown = render_clear_review_plan(plan)
    write_text(review_latest_dir() / "clear-review-plan.md", markdown)
    write_text(reports_latest_dir() / "clear-review-plan.md", markdown)


def render_clear_review_plan(plan: JsonObject) -> str:
    rows = "\n".join(
        f"| {item['date']} | {item['merchantName']} | {item['currentCategory']} | "
        f"{item['amount']} | {item['rationale']} |"
        for item in plan["updates"][:100]
    )
    trusted = ", ".join(plan["summary"]["trustedCategories"])
    return f"""# Clear Review Plan

- Generated at: {plan["generatedAt"]}
- Transactions needing review: {plan["summary"]["needsReviewCount"]}
- Planned review clears: {plan["summary"]["plannedUpdateCount"]}
- Deferred: {plan["summary"]["deferredCount"]}
- Trusted categories: {trusted}

| Date | Merchant | Category | Amount | Rationale |
| --- | --- | --- | --- | --- |
{rows or "| _No planned clears_ |  |  |  |  |"}
"""


def build_review_plan(
    min_confidence: float = 0.78,
    include_pending: bool = False,
    review_correct_categories: bool = True,
) -> JsonObject:
    bundle = load_bundle()
    transactions = list(bundle.get("transactions") or [])
    categories = list(bundle.get("categories") or [])
    category_id_by_name = {str(category["name"]): str(category["id"]) for category in categories}
    category_group_by_name = {
        str(category["name"]): str(category.get("groupName") or "") for category in categories
    }
    profiles = build_review_profiles(transactions)
    updates: list[JsonObject] = []
    deferred: list[JsonObject] = []

    for transaction in transactions:
        if not bool(transaction.get("needsReview")):
            continue
        if bool(transaction.get("isPending")) and not include_pending:
            deferred.append(deferred_item(transaction, "pending transaction"))
            continue

        profile = profiles.get(str(transaction.get("normalizedMerchant") or ""))
        if not profile or profile["count"] < 3:
            deferred.append(deferred_item(transaction, "not enough reviewed merchant history"))
            continue

        dominant_category, dominant_count = profile["categories"].most_common(1)[0]
        confidence = round2(0.55 + (dominant_count / profile["count"]) * 0.4)
        current_category = str(transaction.get("categoryName") or "")
        current_group = category_group_by_name.get(current_category, "")
        dominant_group = category_group_by_name.get(dominant_category, "")
        category_id = category_id_by_name.get(dominant_category)
        category_matches = dominant_category == current_category

        if is_excluded_auto_review_category(current_category, current_group):
            deferred.append(
                deferred_item(transaction, "current category excluded from auto review")
            )
            continue
        if is_excluded_auto_review_category(dominant_category, dominant_group):
            deferred.append(
                deferred_item(transaction, "suggested category excluded from auto review")
            )
            continue
        if confidence < min_confidence:
            deferred.append(deferred_item(transaction, "low confidence"))
            continue
        if not category_id:
            deferred.append(deferred_item(transaction, "suggested category id not found"))
            continue
        if category_matches and not review_correct_categories:
            deferred.append(deferred_item(transaction, "already in suggested category"))
            continue

        action = "review" if category_matches else "recategorize_and_review"
        updates.append(
            {
                "transactionId": transaction["id"],
                "date": transaction["date"],
                "merchantName": transaction["merchantName"],
                "accountName": transaction["accountName"],
                "amount": transaction["signedAmount"],
                "currentCategory": current_category,
                "suggestedCategory": dominant_category,
                "categoryId": "" if category_matches else category_id,
                "currentNeedsReview": transaction["needsReview"],
                "setNeedsReview": False,
                "confidence": confidence,
                "action": action,
                "rationale": (
                    f"{profile['count']} reviewed transactions for this merchant skew "
                    f"toward {dominant_category}."
                ),
            }
        )

    plan = {
        "generatedAt": now_iso(),
        "summary": {
            "reviewedHistoryCount": sum(1 for item in transactions if not item.get("needsReview")),
            "needsReviewCount": sum(1 for item in transactions if item.get("needsReview")),
            "plannedUpdateCount": len(updates),
            "deferredCount": len(deferred),
            "minConfidence": min_confidence,
        },
        "updates": sorted(updates, key=lambda item: (-float(item["confidence"]), item["date"])),
        "deferred": sorted(deferred, key=lambda item: item["date"], reverse=True),
    }
    write_review_plan(plan)
    return plan


async def apply_review_plan(updates: list[JsonObject]) -> JsonObject:
    from .paths import review_revert_dir
    from .revert import build_revert_receipt, snapshot_transaction_before, write_revert_receipt

    bundle = load_bundle()
    operations: list[JsonObject] = []
    for update in updates:
        before = snapshot_transaction_before(update["transactionId"], bundle)
        after: JsonObject = {
            "categoryId": update.get("categoryId"),
            "categoryName": update.get("suggestedCategory"),
            "needsReview": update.get("setNeedsReview"),
        }
        operations.append(
            {
                "type": "update_transaction",
                "entityId": update["transactionId"],
                "merchantName": update.get("merchantName", ""),
                "before": before,
                "after": after,
            }
        )

    results = await apply_transaction_updates(updates)
    applied: JsonObject = {
        "appliedAt": now_iso(),
        "requestedCount": len(updates),
        "results": results,
    }
    write_json(review_latest_dir() / "apply-results.json", applied)
    receipt = build_revert_receipt("monarch review apply", operations)
    write_revert_receipt(review_revert_dir(), receipt)
    return applied


def write_review_plan(plan: JsonObject) -> None:
    reset_dir(review_latest_dir())
    write_json(review_latest_dir() / "review-plan.json", plan)
    write_csv(review_latest_dir() / "review-plan.csv", plan["updates"])
    write_csv(review_latest_dir() / "review-deferred.csv", plan["deferred"])
    write_text(review_latest_dir() / "review-plan.md", render_review_plan(plan))
    write_text(reports_latest_dir() / "review-plan.md", render_review_plan(plan))
    write_json(analysis_latest_dir() / "review-plan-summary.json", plan["summary"])


def render_review_plan(plan: JsonObject) -> str:
    rows = "\n".join(
        f"| {item['date']} | {item['merchantName']} | {item['currentCategory']} | "
        f"{item['suggestedCategory']} | {item['amount']} | {item['action']} | "
        f"{item['confidence']:.2f} | {item['rationale']} |"
        for item in plan["updates"][:100]
    )
    table_header = (
        "| Date | Merchant | Current Category | Suggested Category | Amount | "
        "Action | Confidence | Rationale |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    return f"""# Review Plan

- Generated at: {plan["generatedAt"]}
- Transactions needing review: {plan["summary"]["needsReviewCount"]}
- Planned updates: {plan["summary"]["plannedUpdateCount"]}
- Deferred: {plan["summary"]["deferredCount"]}
- Minimum confidence: {plan["summary"]["minConfidence"]}

{table_header}
{rows or "| _No planned updates_ |  |  |  |  |  |  |  |"}
"""


def build_review_profiles(transactions: list[JsonObject]) -> dict[str, JsonObject]:
    profiles: dict[str, JsonObject] = defaultdict(lambda: {"count": 0, "categories": Counter()})
    for transaction in transactions:
        if bool(transaction.get("needsReview")):
            continue
        if bool(transaction.get("isPending")):
            continue
        key = str(transaction.get("normalizedMerchant") or "")
        category = str(transaction.get("categoryName") or "")
        if not key or not category:
            continue
        profiles[key]["count"] += 1
        profiles[key]["categories"][category] += 1
    return dict(profiles)


def deferred_item(transaction: JsonObject, reason: str) -> JsonObject:
    return {
        "transactionId": transaction.get("id", ""),
        "date": transaction.get("date", ""),
        "merchantName": transaction.get("merchantName", ""),
        "accountName": transaction.get("accountName", ""),
        "amount": transaction.get("signedAmount", 0),
        "currentCategory": transaction.get("categoryName", ""),
        "reason": reason,
    }


def is_excluded_auto_review_category(category_name: str, category_group: str) -> bool:
    return (
        category_group in EXCLUDED_AUTO_REVIEW_CATEGORY_GROUPS
        or category_name in EXCLUDED_AUTO_REVIEW_CATEGORY_NAMES
    )
