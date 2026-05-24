"""
Rules engine for Monarch transaction management.

Flow:
  1. `suggest-rules`  — analyze transaction history, write rule-suggestions.json
  2. User reviews / edits the file (set enabled=false, or remove merchants from
     the match.merchantNames list to exclude individuals)
  3. `apply-rules`    — match rules against normalized bundle, call Monarch API

Rule match criteria:
  merchantName      exact match on one merchant (case-insensitive)
  merchantNames     list of exact merchant names (OR logic, case-insensitive)
  merchantPattern   substring match (case-insensitive, applied to all merchants)
  categoryNames     list of category names the transaction must currently be in
  accountNames      list of account displayNames to restrict to
  needsReview       if true, only match needs-review transactions
  amountMin/Max     signed amount filter

Rule actions:
  setCategory / setCategoryId   recategorize
  clearNeedsReview              mark as reviewed (needsReview=false)
  addTag                        tag name to attach
"""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from .paths import normalized_latest_dir, rules_latest_dir
from .storage import read_json, reset_dir, write_csv, write_json, write_text

JsonObject = dict[str, Any]

MIN_MERCHANT_TRANSACTIONS = 4
MIN_CATEGORY_CONSISTENCY = 0.90
MAX_CONFIDENCE = 0.98
NR_CONSISTENT_MAX_CONFIDENCE = 0.95
SKIP_CATEGORIES = {"Uncategorized"}


# ---------------------------------------------------------------------------
# Suggestion builder
# ---------------------------------------------------------------------------


def build_rule_suggestions() -> JsonObject:
    bundle_path = normalized_latest_dir() / "bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(
            "No normalized bundle found. Run `monarch pull` or `monarch import` first."
        )

    bundle = read_json(bundle_path)
    transactions: list[JsonObject] = [
        t for t in (bundle.get("transactions") or []) if not t.get("isPending")
    ]
    categories: list[JsonObject] = list(bundle.get("categories") or [])
    category_id_by_name = {str(c["name"]): str(c["id"]) for c in categories}

    merchant_profiles = _build_merchant_profiles(transactions, category_id_by_name)
    nr_profiles = _build_nr_consistent_profiles(
        transactions, category_id_by_name, merchant_profiles
    )
    rules = _consolidate_rules(merchant_profiles, nr_profiles)

    reset_dir(rules_latest_dir())
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    output: JsonObject = {
        "generatedAt": generated_at,
        "transactionCount": len(transactions),
        "rules": rules,
        "summary": {
            "totalRules": len(rules),
            "totalMerchants": sum(
                len((r.get("match") or {}).get("merchantNames") or []) for r in rules
            ),
            "pendingTotal": sum(
                r.get("pendingMatchCount", 0) for r in rules if r.get("enabled", True)
            ),
        },
    }

    write_json(rules_latest_dir() / "rule-suggestions.json", output)
    write_csv(rules_latest_dir() / "rule-suggestions.csv", _rules_to_csv_rows(rules))
    write_text(rules_latest_dir() / "rule-suggestions.md", _rules_to_markdown(output))

    return output


# ---------------------------------------------------------------------------
# Profile builders
# ---------------------------------------------------------------------------


def _build_merchant_profiles(
    transactions: list[JsonObject],
    category_id_by_name: dict[str, str],
) -> dict[str, JsonObject]:
    """Per-merchant profiles from reviewed (non-needs-review) transactions."""
    reviewed = [t for t in transactions if not t.get("needsReview") and t.get("categoryName")]
    needs_review = [t for t in transactions if t.get("needsReview")]

    reviewed_by_merchant: dict[str, list[JsonObject]] = defaultdict(list)
    for t in reviewed:
        key = (t.get("merchantName") or "").strip()
        if key:
            reviewed_by_merchant[key].append(t)

    needs_review_by_merchant: dict[str, list[JsonObject]] = defaultdict(list)
    for t in needs_review:
        key = (t.get("merchantName") or "").strip()
        if key:
            needs_review_by_merchant[key].append(t)

    profiles: dict[str, JsonObject] = {}
    for merchant, txns in reviewed_by_merchant.items():
        if len(txns) < MIN_MERCHANT_TRANSACTIONS:
            continue
        cats = Counter(str(t["categoryName"]) for t in txns)
        top_cat, top_count = cats.most_common(1)[0]
        consistency = top_count / len(txns)
        if consistency < MIN_CATEGORY_CONSISTENCY:
            continue
        cat_id = category_id_by_name.get(top_cat)
        if not cat_id:
            continue
        pending = needs_review_by_merchant.get(merchant, [])
        profiles[merchant] = {
            "merchantName": merchant,
            "category": top_cat,
            "categoryId": cat_id,
            "consistency": round(consistency, 4),
            "confidence": round(min(MAX_CONFIDENCE, 0.55 + consistency * 0.45), 4),
            "evidence": len(txns),
            "pending": len(pending),
            "source": "merchant_history",
        }

    return profiles


def _build_nr_consistent_profiles(
    transactions: list[JsonObject],
    category_id_by_name: dict[str, str],
    already_covered: dict[str, JsonObject],
) -> dict[str, JsonObject]:
    """Merchants with no reviewed history but consistent NR auto-categorization."""
    needs_review = [t for t in transactions if t.get("needsReview")]

    nr_by_merchant: dict[str, list[JsonObject]] = defaultdict(list)
    for t in needs_review:
        key = (t.get("merchantName") or "").strip()
        if key:
            nr_by_merchant[key].append(t)

    profiles: dict[str, JsonObject] = {}
    for merchant, ts in nr_by_merchant.items():
        if merchant in already_covered or len(ts) < MIN_MERCHANT_TRANSACTIONS:
            continue
        cats = Counter(str(t["categoryName"]) for t in ts if t.get("categoryName"))
        if not cats:
            continue
        top_cat, top_count = cats.most_common(1)[0]
        if top_cat in SKIP_CATEGORIES:
            continue
        consistency = top_count / len(ts)
        if consistency < MIN_CATEGORY_CONSISTENCY:
            continue
        cat_id = category_id_by_name.get(top_cat)
        if not cat_id:
            continue
        profiles[merchant] = {
            "merchantName": merchant,
            "category": top_cat,
            "categoryId": cat_id,
            "consistency": round(consistency, 4),
            "confidence": round(min(NR_CONSISTENT_MAX_CONFIDENCE, 0.65 + consistency * 0.30), 4),
            "evidence": 0,
            "pending": len(ts),
            "source": "nr_consistent",
        }

    return profiles


# ---------------------------------------------------------------------------
# Rule consolidation
# ---------------------------------------------------------------------------


def _consolidate_rules(
    merchant_profiles: dict[str, JsonObject],
    nr_profiles: dict[str, JsonObject],
) -> list[JsonObject]:
    """Group profiles by target category → one rule per category with a merchantNames list."""
    all_profiles = list(merchant_profiles.values()) + list(nr_profiles.values())

    groups: dict[str, list[JsonObject]] = defaultdict(list)
    cat_id_map: dict[str, str] = {}
    for p in all_profiles:
        groups[p["category"]].append(p)
        cat_id_map[p["category"]] = p["categoryId"]

    rules: list[JsonObject] = []
    for category, members in sorted(
        groups.items(), key=lambda kv: -sum(m["pending"] for m in kv[1])
    ):
        members = sorted(members, key=lambda m: (-m["pending"], -m["confidence"]))
        merchant_names = [m["merchantName"] for m in members]
        total_pending = sum(m["pending"] for m in members)
        confidences = [m["confidence"] for m in members]
        avg_conf = sum(confidences) / len(confidences)
        min_conf = min(confidences)
        max_conf = max(confidences)
        n = len(members)

        rules.append(
            {
                "id": str(uuid.uuid4())[:8],
                "name": f"{category} — auto-clear",
                "description": (
                    f"{n} merchants → {category}. "
                    f"{total_pending} needs-review transactions. "
                    f"Confidence {min_conf:.2f}–{max_conf:.2f} (avg {avg_conf:.2f}). "
                    f"Remove individual merchants from match.merchantNames to exclude them."
                ),
                "match": {
                    "merchantNames": merchant_names,
                    "needsReview": True,
                },
                "action": {
                    "setCategory": category,
                    "setCategoryId": cat_id_map[category],
                    "clearNeedsReview": True,
                    "addTag": None,
                    "hideFromReports": None,
                },
                "confidence": round(avg_conf, 4),
                "source": "consolidated",
                "evidenceCount": sum(m["evidence"] for m in members),
                "pendingMatchCount": total_pending,
                "merchants": members,
                "enabled": True,
            }
        )

    return sorted(rules, key=lambda r: -r["pendingMatchCount"])


# ---------------------------------------------------------------------------
# Rule application
# ---------------------------------------------------------------------------


def match_transactions(rule: JsonObject, transactions: list[JsonObject]) -> list[JsonObject]:
    match = rule.get("match") or {}
    merchant_name = (match.get("merchantName") or "").strip().lower()
    merchant_names = {n.lower() for n in (match.get("merchantNames") or [])}
    merchant_pattern = (match.get("merchantPattern") or "").strip()
    category_names = {c.lower() for c in (match.get("categoryNames") or [])}
    account_names = {a.lower() for a in (match.get("accountNames") or [])}
    needs_review_filter = match.get("needsReview")
    amount_min = match.get("amountMin")
    amount_max = match.get("amountMax")

    pattern_re = (
        re.compile(re.escape(merchant_pattern), re.IGNORECASE) if merchant_pattern else None
    )
    matched: list[JsonObject] = []

    for t in transactions:
        if t.get("isPending"):
            continue

        txn_merchant = (t.get("merchantName") or "").strip().lower()
        txn_category = (t.get("categoryName") or "").strip().lower()
        txn_account = (t.get("accountName") or t.get("accountDisplayName") or "").strip().lower()
        txn_amount = float(t.get("signedAmount") or 0)
        txn_needs_review = bool(t.get("needsReview"))

        if merchant_name and txn_merchant != merchant_name:
            continue
        if merchant_names and txn_merchant not in merchant_names:
            continue
        if pattern_re and not pattern_re.search(txn_merchant):
            continue
        if category_names and txn_category not in category_names:
            continue
        if account_names and txn_account not in account_names:
            continue
        if needs_review_filter is not None and txn_needs_review != bool(needs_review_filter):
            continue
        if amount_min is not None and txn_amount < float(amount_min):
            continue
        if amount_max is not None and txn_amount > float(amount_max):
            continue

        matched.append(t)

    return matched


def load_rule_suggestions(rules_path: str | None = None) -> list[JsonObject]:
    from pathlib import Path as _Path

    path = _Path(rules_path) if rules_path else rules_latest_dir() / "rule-suggestions.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No rule suggestions found at {path}. Run `monarch suggest-rules` first."
        )
    data = read_json(path)
    return list(data.get("rules") or [])


def build_apply_plan(
    rules_path: str | None = None,
    rules_filter: list[str] | None = None,
) -> JsonObject:
    from pathlib import Path as _Path

    path = _Path(rules_path) if rules_path else rules_latest_dir() / "rule-suggestions.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No rule suggestions found at {path}. Run `monarch suggest-rules` first."
        )

    bundle_path = normalized_latest_dir() / "bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(
            "No normalized bundle found. Run `monarch pull` or `monarch import` first."
        )

    rule_set = read_json(path)
    bundle = read_json(bundle_path)
    transactions: list[JsonObject] = [
        t for t in (bundle.get("transactions") or []) if not t.get("isPending")
    ]
    categories: list[JsonObject] = list(bundle.get("categories") or [])
    category_id_by_name = {str(c["name"]): str(c["id"]) for c in categories}

    rules = [r for r in (rule_set.get("rules") or []) if r.get("enabled", True)]
    if rules_filter:
        rules = [rule for rule in rules if _rule_matches_filter(rule, rules_filter)]
    updates: list[JsonObject] = []
    seen_txn_ids: set[str] = set()

    for rule in rules:
        action = rule.get("action") or {}
        for txn in match_transactions(rule, transactions):
            txn_id = str(txn["id"])
            if txn_id in seen_txn_ids:
                continue
            seen_txn_ids.add(txn_id)

            set_category = action.get("setCategory")
            category_id = action.get("setCategoryId") or (
                category_id_by_name.get(set_category) if set_category else None
            )
            updates.append(
                {
                    "transactionId": txn_id,
                    "merchantName": txn.get("merchantName") or "",
                    "currentCategory": txn.get("categoryName") or "",
                    "suggestedCategory": set_category or "",
                    "categoryId": category_id or "",
                    "clearNeedsReview": bool(action.get("clearNeedsReview", False)),
                    "addTag": action.get("addTag") or None,
                    "ruleId": rule.get("id", ""),
                    "ruleName": rule.get("name", ""),
                }
            )

    return {
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "enabledRules": len(rules),
        "updates": updates,
        "summary": {"updateCount": len(updates)},
    }


async def apply_rules_plan(
    rules_path: str | None = None,
    limit: int | None = None,
    rules_filter: list[str] | None = None,
) -> JsonObject:
    from .monarch_api import apply_transaction_updates, tag_transactions

    plan = build_apply_plan(rules_path, rules_filter)
    updates = plan["updates"]

    if limit is not None:
        updates = updates[:limit]

    api_updates = [
        {
            "transactionId": u["transactionId"],
            "merchantName": u["merchantName"],
            "suggestedCategory": u["suggestedCategory"],
            "categoryId": u["categoryId"] or None,
            "setNeedsReview": False if u["clearNeedsReview"] else None,
        }
        for u in updates
        if u.get("categoryId") or u.get("clearNeedsReview")
    ]

    tag_updates: dict[str, list[str]] = defaultdict(list)
    for u in updates:
        if u.get("addTag"):
            tag_updates[u["addTag"]].append(u["transactionId"])

    results = await apply_transaction_updates(api_updates) if api_updates else []
    for tag_name, txn_ids in tag_updates.items():
        await tag_transactions(txn_ids, tag_name)

    return {
        "appliedCount": len(results),
        "taggedGroups": len(tag_updates),
        "updates": updates,
    }


def _rule_matches_filter(rule: JsonObject, rules_filter: list[str]) -> bool:
    needles = {item.strip().lower() for item in rules_filter if item.strip()}
    if not needles:
        return True
    rule_id = str(rule.get("id") or "").lower()
    rule_name = str(rule.get("name") or "").lower()
    return rule_id in needles or rule_name in needles


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _rules_to_csv_rows(rules: list[JsonObject]) -> list[JsonObject]:
    rows = []
    for r in rules:
        match = r.get("match") or {}
        action = r.get("action") or {}
        merchant_names = match.get("merchantNames") or []
        rows.append(
            {
                "id": r.get("id", ""),
                "enabled": r.get("enabled", True),
                "name": r.get("name", ""),
                "source": r.get("source", ""),
                "confidence": r.get("confidence", ""),
                "pendingMatchCount": r.get("pendingMatchCount", 0),
                "merchantCount": len(merchant_names),
                "matchMerchantName": match.get("merchantName", ""),
                "matchMerchantPattern": match.get("merchantPattern", ""),
                "matchMerchantNames": " | ".join(merchant_names[:5])
                + (" …" if len(merchant_names) > 5 else ""),
                "matchNeedsReview": match.get("needsReview", ""),
                "actionSetCategory": action.get("setCategory", ""),
                "actionClearNeedsReview": action.get("clearNeedsReview", ""),
                "actionAddTag": action.get("addTag", ""),
                "description": r.get("description", ""),
            }
        )
    return rows


def _rules_to_markdown(output: JsonObject) -> str:
    rules = output.get("rules") or []
    s = output.get("summary") or {}
    lines = [
        "# Monarch Rule Suggestions",
        "",
        f"Generated: {output.get('generatedAt', '')}  ",
        f"Transactions analyzed: {output.get('transactionCount', 0)}  ",
        f"Rules: {s.get('totalRules', 0)} (covering {s.get('totalMerchants', 0)} merchants)  ",
        f"Pending needs-review transactions covered: {s.get('pendingTotal', 0)}",
        "",
        "To exclude a merchant from a rule, remove it from `match.merchantNames` in the JSON.",
        "To skip an entire rule, set `enabled: false`.",
        "",
        "---",
        "",
    ]

    with_pending = [r for r in rules if r.get("pendingMatchCount", 0) > 0]
    no_pending = [r for r in rules if not r.get("pendingMatchCount", 0)]

    if with_pending:
        lines += ["## Rules with pending needs-review matches", ""]
        for r in with_pending:
            lines += _rule_md_block(r)

    if no_pending:
        lines += ["## Rules with no current pending matches (future use)", ""]
        for r in no_pending:
            lines += _rule_md_block(r)

    return "\n".join(lines)


def _rule_md_block(r: JsonObject) -> list[str]:
    action = r.get("action") or {}
    match = r.get("match") or {}
    enabled = r.get("enabled", True)
    status = "enabled" if enabled else "**disabled**"
    merchant_names: list[str] = match.get("merchantNames") or []
    single_merchant = match.get("merchantName") or match.get("merchantPattern") or ""

    lines = [
        f"### {r.get('name', '')} `[{status}]`",
        "",
        r.get("description", ""),
        "",
    ]

    if merchant_names:
        lines.append(f"**Merchants ({len(merchant_names)}):**")
        merchants_meta: list[JsonObject] = r.get("merchants") or []
        meta_by_name = {m["merchantName"]: m for m in merchants_meta}
        for name in merchant_names:
            m = meta_by_name.get(name, {})
            parts = [f"`{name}`"]
            if m.get("pending"):
                parts.append(f"{m['pending']} pending")
            if m.get("evidence"):
                parts.append(f"{m['evidence']} reviewed")
            parts.append(f"conf {m.get('confidence', r.get('confidence', '?')):.2f}")
            parts.append(m.get("source", ""))
            lines.append(f"- {' | '.join(parts)}")
        lines.append("")
    else:
        lines.append(f"- Match: `{single_merchant}`, needsReview={match.get('needsReview', '')}")
        lines.append("")

    lines += [
        f"- Action: category=`{action.get('setCategory', '')}`, "
        f"clearNeedsReview={action.get('clearNeedsReview', False)}"
        + (f", tag=`{action['addTag']}`" if action.get("addTag") else ""),
        f"- Confidence: {r.get('confidence', '')} | "
        f"Evidence: {r.get('evidenceCount', '')} txns reviewed | "
        f"Pending: {r.get('pendingMatchCount', 0)}",
        f"- Rule ID: `{r.get('id', '')}`",
        "",
    ]
    return lines
