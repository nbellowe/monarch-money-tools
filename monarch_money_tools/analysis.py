from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

JsonObject = dict[str, Any]

RECENT_DAYS = 45
IGNORED_CATEGORY_WORDS = {"transfer", "credit card payment"}


@dataclass
class MerchantProfile:
    key: str
    transactions: list[JsonObject] = field(default_factory=list)
    category_counts: Counter[str] = field(default_factory=Counter)
    owner_counts: Counter[str] = field(default_factory=Counter)
    merchant_variants: set[str] = field(default_factory=set)
    total_spend: float = 0.0


def prepare_analysis(bundle: JsonObject) -> JsonObject:
    transactions = list(bundle.get("transactions") or [])
    categories = list(bundle.get("categories") or [])
    shared_start_date = find_first_shared_date(transactions)
    merchant_profiles = build_merchant_profiles(transactions, categories)
    owner_profiles = build_owner_profiles(transactions, shared_start_date)
    miscategorizations = find_miscategorizations(transactions, merchant_profiles)
    owner_reviews = find_owner_reviews(transactions, owner_profiles, shared_start_date)
    implicated_merchants: dict[str, set[str]] = defaultdict(set)

    for item in miscategorizations:
        implicated_merchants[item["merchantKey"]].add("category_correction")

    for item in owner_reviews:
        implicated_merchants[item["merchantKey"]].add("owner_correction")
        if item["suggestedNeedsReview"]:
            implicated_merchants[item["merchantKey"]].add("needs_review")

    rule_candidates = find_rule_candidates(merchant_profiles, owner_profiles, implicated_merchants)
    heuristic_rule_opportunities = build_heuristic_rule_opportunities(rule_candidates)

    return {
        "generatedAt": now_iso(),
        "summary": {
            "transactionCount": len(transactions),
            "recentTransactionCount": sum(
                1 for item in transactions if is_recent(str(item.get("date")))
            ),
            "uniqueMerchantCount": len(merchant_profiles),
            "miscategorizationCount": len(miscategorizations),
            "ownerReviewCount": len(owner_reviews),
        },
        "miscategorizations": strip_internal_keys(miscategorizations),
        "ownerReviews": strip_internal_keys(owner_reviews),
        "ruleCandidates": rule_candidates,
        "heuristicRuleOpportunities": heuristic_rule_opportunities,
    }


def build_merchant_profiles(
    transactions: list[JsonObject], categories: list[JsonObject]
) -> dict[str, MerchantProfile]:
    category_name_by_id = {
        str(category.get("id")): str(category.get("name")) for category in categories
    }
    profiles: dict[str, MerchantProfile] = {}

    for transaction in transactions:
        key = str(transaction.get("normalizedMerchant") or "")
        if not key:
            continue
        profile = profiles.setdefault(key, MerchantProfile(key))
        profile.transactions.append(transaction)
        profile.merchant_variants.add(str(transaction.get("merchantName") or ""))
        profile.total_spend += abs(float(transaction.get("signedAmount") or 0))
        category_name = str(transaction.get("categoryName") or "")
        if category_name:
            profile.category_counts[
                category_name_by_id.get(str(transaction.get("categoryId")), category_name)
            ] += 1
        owner = str(transaction.get("owner") or "")
        if owner:
            profile.owner_counts[owner] += 1

    return profiles


def build_owner_profiles(
    transactions: list[JsonObject], shared_start_date: str | None
) -> dict[str, MerchantProfile]:
    relevant = [
        transaction
        for transaction in transactions
        if shared_start_date is None or str(transaction.get("date") or "") >= shared_start_date
    ]
    profiles: dict[str, MerchantProfile] = {}

    for transaction in relevant:
        key = str(transaction.get("normalizedMerchant") or "")
        if not key:
            continue
        profile = profiles.setdefault(key, MerchantProfile(key))
        profile.transactions.append(transaction)
        profile.merchant_variants.add(str(transaction.get("merchantName") or ""))
        profile.total_spend += abs(float(transaction.get("signedAmount") or 0))
        owner = str(transaction.get("owner") or "")
        if owner:
            profile.owner_counts[owner] += 1

    return profiles


def find_first_shared_date(transactions: list[JsonObject]) -> str | None:
    shared_dates = [
        str(transaction.get("date") or "")
        for transaction in transactions
        if transaction.get("owner") == "Shared" and transaction.get("date")
    ]
    return min(shared_dates) if shared_dates else None


def find_miscategorizations(
    transactions: list[JsonObject], profiles: dict[str, MerchantProfile]
) -> list[JsonObject]:
    suggestions: list[JsonObject] = []

    for transaction in transactions:
        profile = profiles.get(str(transaction.get("normalizedMerchant") or ""))
        if profile is None or len(profile.transactions) < 4:
            continue
        dominant_category = dominant_entry(profile.category_counts)
        if dominant_category is None or dominant_category[1] < 3:
            continue

        dominant_name, dominant_count = dominant_category
        dominant_share = dominant_count / len(profile.transactions)
        current_category = str(transaction.get("categoryName") or "")
        if (
            dominant_name == current_category
            or dominant_share < 0.72
            or current_category.lower() in IGNORED_CATEGORY_WORDS
        ):
            continue

        recent_boost = 0.08 if is_recent(str(transaction.get("date") or "")) else 0
        confidence = clamp(0.56 + dominant_share * 0.28 + recent_boost, 0, 0.98)
        dominant_owner = (dominant_entry(profile.owner_counts) or ("", 0))[0]
        suggestion = {
            "merchantKey": profile.key,
            "transactionId": transaction.get("id") or "",
            "date": transaction.get("date") or "",
            "merchantName": transaction.get("merchantName") or "",
            "accountName": transaction.get("accountName") or "",
            "currentCategory": current_category,
            "suggestedCategory": dominant_name,
            "confidence": confidence,
            "rationale": (
                f"{len(profile.transactions)} historical transactions for this merchant "
                f"skew toward {dominant_name}."
            ),
            "currentOwner": transaction.get("owner") or "",
            "suggestedOwner": dominant_owner,
            "amount": transaction.get("signedAmount") or 0,
            "isRecent": is_recent(str(transaction.get("date") or "")),
        }
        if confidence >= 0.75:
            suggestions.append(suggestion)

    return sorted(
        suggestions,
        key=lambda item: (-float(item["confidence"]), -abs(float(item["amount"]))),
    )


def find_owner_reviews(
    transactions: list[JsonObject],
    profiles: dict[str, MerchantProfile],
    shared_start_date: str | None,
) -> list[JsonObject]:
    items: list[JsonObject] = []

    for transaction in transactions:
        if shared_start_date and str(transaction.get("date") or "") < shared_start_date:
            continue
        profile = profiles.get(str(transaction.get("normalizedMerchant") or ""))
        if profile is None or len(profile.transactions) < 3:
            continue
        dominant_owner = dominant_entry(profile.owner_counts)
        if dominant_owner is None or dominant_owner[1] < 2:
            continue

        dominant_name, dominant_count = dominant_owner
        owner_share = dominant_count / len(profile.transactions)
        second_share = second_entry_share(profile.owner_counts, len(profile.transactions))
        current_owner = str(transaction.get("owner") or "Unassigned")
        ambiguous_history = owner_share < 0.85 or second_share >= 0.2
        owner_mismatch = current_owner != dominant_name
        missing_owner = current_owner == "Unassigned"
        should_recommend_review = missing_owner and ambiguous_history

        if not owner_mismatch and not should_recommend_review:
            continue

        suggested_owner = "" if ambiguous_history and missing_owner else dominant_name
        confidence = clamp(
            0.5
            + owner_share * 0.3
            + (0.08 if is_recent(str(transaction.get("date") or "")) else 0),
            0,
            0.97,
        )
        if should_recommend_review:
            rationale = (
                "Since shared tracking began, owner history is mixed for this merchant, so leaving "
                "owner unset and marking for review is safer."
            )
        else:
            owner_percent = round(owner_share * 100)
            rationale = (
                "Since shared tracking began, owner history for this merchant is "
                f"{owner_percent}% {dominant_name}."
            )
        item = {
            "merchantKey": profile.key,
            "transactionId": transaction.get("id") or "",
            "date": transaction.get("date") or "",
            "merchantName": transaction.get("merchantName") or "",
            "accountName": transaction.get("accountName") or "",
            "currentOwner": current_owner,
            "suggestedOwner": suggested_owner,
            "currentNeedsReview": bool(transaction.get("needsReview")),
            "suggestedNeedsReview": should_recommend_review,
            "confidence": confidence,
            "rationale": rationale,
            "amount": transaction.get("signedAmount") or 0,
            "categoryName": transaction.get("categoryName") or "",
        }
        if confidence >= 0.68 or should_recommend_review:
            items.append(item)

    return sorted(
        items,
        key=lambda item: (
            -int(bool(item["suggestedNeedsReview"])),
            -float(item["confidence"]),
            -abs(float(item["amount"])),
        ),
    )


def find_rule_candidates(
    category_profiles: dict[str, MerchantProfile],
    owner_profiles: dict[str, MerchantProfile],
    implicated_merchants: dict[str, set[str]],
) -> list[JsonObject]:
    candidates: list[JsonObject] = []

    for merchant_key, issue_types in implicated_merchants.items():
        category_profile = category_profiles.get(merchant_key)
        owner_profile = owner_profiles.get(merchant_key)
        if category_profile is None or len(category_profile.transactions) < 4:
            continue
        dominant_category = dominant_entry(category_profile.category_counts)
        if dominant_category is None:
            continue

        dominant_owner = dominant_entry(owner_profile.owner_counts) if owner_profile else None
        dominant_category_share = dominant_category[1] / len(category_profile.transactions)
        dominant_owner_share = (
            dominant_owner[1] / len(owner_profile.transactions)
            if owner_profile and dominant_owner
            else 0
        )
        merchant_variants = sorted(category_profile.merchant_variants)
        sample_transactions = [
            {
                "date": transaction.get("date") or "",
                "merchantName": transaction.get("merchantName") or "",
                "amount": transaction.get("signedAmount") or 0,
                "categoryName": transaction.get("categoryName") or "",
                "owner": transaction.get("owner") or "",
                "needsReview": bool(transaction.get("needsReview")),
                "accountName": transaction.get("accountName") or "",
            }
            for transaction in sorted(
                category_profile.transactions,
                key=lambda item: str(item.get("date") or ""),
                reverse=True,
            )[:6]
        ]

        candidates.append(
            {
                "merchantKey": merchant_key,
                "exampleMerchant": merchant_variants[0] if merchant_variants else merchant_key,
                "merchantVariants": merchant_variants,
                "exampleCount": len(category_profile.transactions),
                "totalSpend": round2(category_profile.total_spend),
                "dominantCategory": dominant_category[0],
                "dominantCategoryShare": round2(dominant_category_share),
                "dominantOwner": dominant_owner[0] if dominant_owner else "",
                "dominantOwnerShare": round2(dominant_owner_share),
                "issueTypes": sorted(issue_types),
                "sampleTransactions": sample_transactions,
            }
        )

    return sorted(
        candidates,
        key=lambda item: (-int(item["exampleCount"]), -float(item["totalSpend"])),
    )


def build_heuristic_rule_opportunities(candidates: list[JsonObject]) -> list[JsonObject]:
    opportunities: list[JsonObject] = []

    for candidate in candidates:
        if int(candidate["exampleCount"]) < 5:
            continue
        issue_types = set(candidate["issueTypes"])
        actions: list[str] = []
        if (
            "category_correction" in issue_types
            and float(candidate["dominantCategoryShare"]) >= 0.8
        ):
            actions.append(f"Set category to {candidate['dominantCategory']}")
        if (
            "owner_correction" in issue_types
            and candidate["dominantOwner"]
            and float(candidate["dominantOwnerShare"]) >= 0.85
        ):
            actions.append(f"Set Owner to {candidate['dominantOwner']}")
        if "needs_review" in issue_types and float(candidate["dominantOwnerShare"]) < 0.85:
            actions.append("Set Needs Review when owner is unclear")
        if not actions:
            continue

        opportunities.append(
            {
                "merchantKey": candidate["merchantKey"],
                "exampleMerchant": candidate["exampleMerchant"],
                "proposedCriteria": f'Merchant contains "{candidate["merchantKey"]}"',
                "proposedAction": "; ".join(actions),
                "confidence": clamp(
                    0.58
                    + float(candidate["dominantCategoryShare"]) * 0.2
                    + float(candidate["dominantOwnerShare"]) * 0.12,
                    0,
                    0.97,
                ),
                "rationale": "Recurring correction pattern for "
                f"{', '.join(candidate['issueTypes'])} across "
                f"{candidate['exampleCount']} transactions.",
                "exampleCount": candidate["exampleCount"],
                "totalSpend": candidate["totalSpend"],
                "dominantCategory": candidate["dominantCategory"],
                "dominantOwner": candidate["dominantOwner"],
                "merchantVariants": candidate["merchantVariants"],
                "source": "heuristic",
                "reviewNotes": "Fallback correction rule generated without AI.",
            }
        )

    return sorted(
        opportunities,
        key=lambda item: (-float(item["confidence"]), -int(item["exampleCount"])),
    )


def dominant_entry(counter: Counter[str]) -> tuple[str, int] | None:
    return counter.most_common(1)[0] if counter else None


def second_entry_share(counter: Counter[str], total: int) -> float:
    counts = [value for _, value in counter.most_common()]
    second = counts[1] if len(counts) > 1 else 0
    return second / total if total > 0 else 0


def is_recent(date_string: str) -> bool:
    try:
        value = datetime.fromisoformat(date_string)
    except ValueError:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return (datetime.now(UTC) - value).days <= RECENT_DAYS


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, round2(value)))


def round2(value: float) -> float:
    return round(value * 100) / 100


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def strip_internal_keys(rows: list[JsonObject]) -> list[JsonObject]:
    return [{key: value for key, value in row.items() if key != "merchantKey"} for row in rows]
