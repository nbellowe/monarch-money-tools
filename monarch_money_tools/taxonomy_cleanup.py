"""
Deterministic taxonomy cleanup pass — Step 2 of the historic cleanup plan.

Two evidence sources, applied in priority order:

  1. taxonomy_migration (confidence 1.0)
     Every transaction whose current category appears in the taxonomy's
     `retirements` list is remapped to its canonical replacement.  These
     are mechanical — no judgment required.

  2. merchant_history (confidence 0.75–0.95)
     Merchant profiles built from *reviewed* transactions in canonical
     categories.  Any needs-review transaction whose merchant profile
     points ≥ 80 % of the time to a *different* canonical category is
     flagged as a recategorization candidate.

Output: data/cleanup/latest/{cleanup-plan.json, cleanup-plan.csv,
        cleanup-plan.md, cleanup-blocked.csv}
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from .paths import canonical_taxonomy_file, cleanup_latest_dir
from .storage import (
    JsonObject,
    load_bundle,
    now_iso,
    read_json,
    reset_dir,
    write_csv,
    write_json,
    write_text,
)

MIGRATION_CONFIDENCE = 1.0
MIN_PROFILE_TRANSACTIONS = 4
MIN_CONSISTENCY_SHARE = 0.80
MAX_CONSISTENCY_CONFIDENCE = 0.95


def load_decisions() -> dict[str, str]:
    """Load cleanup review decisions from the latest cleanup output directory."""
    path = cleanup_latest_dir() / "decisions.json"
    if not path.exists():
        return {}
    raw = read_json(path)
    return {str(key): str(value) for key, value in dict(raw).items()}


def save_decision(transaction_id: str, decision: str) -> None:
    """Persist one cleanup review decision immediately."""
    if decision not in {"accepted", "rejected", "skipped"}:
        raise ValueError("decision must be accepted, rejected, or skipped")
    decisions = load_decisions()
    decisions[transaction_id] = decision
    write_json(cleanup_latest_dir() / "decisions.json", decisions)


def filter_cleanup_candidates(
    plan: JsonObject,
    decisions: dict[str, str],
    skip_blocked: bool,
    source: str | None,
    limit: int | None,
) -> list[JsonObject]:
    candidates = list(plan.get("candidates") or [])
    if decisions:
        candidates = [c for c in candidates if decisions.get(c["transactionId"]) == "accepted"]
    if skip_blocked:
        candidates = [c for c in candidates if not c.get("requiresNewCategory")]
    if source:
        candidates = [c for c in candidates if c.get("source") == source]
    if limit is not None:
        candidates = candidates[:limit]
    return candidates


def build_taxonomy_cleanup_plan(taxonomy_path: Path | None = None) -> JsonObject:
    if taxonomy_path is None:
        taxonomy_path = canonical_taxonomy_file()
    if not taxonomy_path.exists():
        raise FileNotFoundError(f"Taxonomy not found: {taxonomy_path}")

    with open(taxonomy_path, encoding="utf-8") as f:
        taxonomy: JsonObject = yaml.safe_load(f)

    bundle = load_bundle()
    transactions: list[JsonObject] = [
        t for t in (bundle.get("transactions") or []) if not t.get("isPending")
    ]
    categories: list[JsonObject] = list(bundle.get("categories") or [])
    # Keyed by (name, group) — used by migration pass to verify target group exists.
    category_id_by_name_group = {
        (str(c["name"]), str(c.get("groupName") or "")): str(c["id"]) for c in categories
    }
    # Keyed by name only — used by consistency pass (targets are canonical, one per name).
    category_id_by_name = {str(c["name"]): str(c["id"]) for c in categories}
    canonical_group_by_name = {c["name"]: c["group"] for c in taxonomy["categories"]}

    migration_candidates = _build_migration_candidates(
        transactions, taxonomy, category_id_by_name_group, canonical_group_by_name
    )
    migration_ids = {c["transactionId"] for c in migration_candidates}

    consistency_candidates = _build_merchant_consistency_candidates(
        transactions, taxonomy, category_id_by_name, canonical_group_by_name, migration_ids
    )

    all_candidates = migration_candidates + consistency_candidates
    ready = [c for c in all_candidates if not c.get("requiresNewCategory")]
    blocked = [c for c in all_candidates if c.get("requiresNewCategory")]
    categories_to_create = _identify_required_new_categories(taxonomy, category_id_by_name_group)

    plan: JsonObject = {
        "generatedAt": now_iso(),
        "summary": {
            "taxonomyMigrationCount": len(migration_candidates),
            "merchantConsistencyCount": len(consistency_candidates),
            "totalCandidateCount": len(all_candidates),
            "readyCount": len(ready),
            "blockedCount": len(blocked),
            "categoriesToCreateCount": len(categories_to_create),
        },
        "categoriesToCreate": categories_to_create,
        "candidates": sorted(
            all_candidates,
            key=lambda c: (
                0 if c["source"] == "taxonomy_migration" else 1,
                -float(c["confidence"]),
                -abs(float(c["amount"])),
            ),
        ),
    }

    _write_cleanup_plan(plan)
    return plan


# ── Evidence builders ────────────────────────────────────────────────────────


def _build_migration_candidates(
    transactions: list[JsonObject],
    taxonomy: JsonObject,
    category_id_by_name_group: dict[tuple[str, str], str],
    canonical_group_by_name: dict[str, str],
) -> list[JsonObject]:
    retirement_map = _build_retirement_map(taxonomy)
    candidates: list[JsonObject] = []

    for txn in transactions:
        key = (str(txn.get("categoryName") or ""), str(txn.get("groupName") or ""))
        remap = retirement_map.get(key)
        if remap is None:
            continue

        target_name = remap["targetCategory"]
        target_group = remap["targetGroup"]
        # Only mark ready when the target category exists in the correct target group.
        category_id = category_id_by_name_group.get((target_name, target_group), "")

        candidates.append(
            {
                "transactionId": txn["id"],
                "date": txn["date"],
                "merchantName": txn["merchantName"],
                "accountName": txn["accountName"],
                "amount": txn["signedAmount"],
                "currentCategory": txn["categoryName"],
                "currentGroup": txn["groupName"],
                "suggestedCategory": target_name,
                "suggestedGroup": target_group,
                "categoryId": category_id,
                "confidence": MIGRATION_CONFIDENCE,
                "source": "taxonomy_migration",
                "reason": (
                    f"Taxonomy retirement: {txn['groupName']}/{txn['categoryName']}"
                    f" → {target_group}/{target_name}"
                ),
                "requiresNewCategory": not bool(category_id),
                "note": remap.get("note") or "",
                "setNeedsReview": False,
            }
        )

    return sorted(candidates, key=lambda c: (c["suggestedCategory"], c["date"]))


def _build_merchant_consistency_candidates(
    transactions: list[JsonObject],
    taxonomy: JsonObject,
    category_id_by_name: dict[str, str],
    canonical_group_by_name: dict[str, str],
    exclude_ids: set[str],
) -> list[JsonObject]:
    canonical_names = set(canonical_group_by_name.keys())
    # Virtual remap: retired category → canonical target
    virtual_remap = _build_virtual_remap(taxonomy)

    # Build profiles from reviewed, canonical-category transactions (post-virtual-remap).
    profiles: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "categories": Counter()})
    for txn in transactions:
        if txn.get("needsReview"):
            continue
        cat = str(txn.get("categoryName") or "")
        canonical_cat = virtual_remap.get(cat, cat)
        if canonical_cat not in canonical_names:
            continue
        merchant_key = str(txn.get("normalizedMerchant") or "")
        if not merchant_key:
            continue
        profiles[merchant_key]["count"] += 1
        profiles[merchant_key]["categories"][canonical_cat] += 1

    candidates: list[JsonObject] = []
    for txn in transactions:
        tid = str(txn.get("id") or "")
        if tid in exclude_ids:
            continue
        if not txn.get("needsReview"):
            continue

        current_cat = str(txn.get("categoryName") or "")
        # Already in a canonical category — only suggest a change if merchant history disagrees.
        canonical_current = virtual_remap.get(current_cat, current_cat)

        merchant_key = str(txn.get("normalizedMerchant") or "")
        profile = profiles.get(merchant_key)
        if not profile or profile["count"] < MIN_PROFILE_TRANSACTIONS:
            continue

        dominant_cat, dominant_count = profile["categories"].most_common(1)[0]
        dominant_share = dominant_count / profile["count"]

        if dominant_share < MIN_CONSISTENCY_SHARE:
            continue
        if dominant_cat == canonical_current:
            continue  # already consistent — review pass handles these
        if dominant_cat not in canonical_names:
            continue

        category_id = category_id_by_name.get(dominant_cat, "")
        confidence = min(0.55 + dominant_share * 0.40, MAX_CONSISTENCY_CONFIDENCE)
        dominant_group = canonical_group_by_name.get(dominant_cat, "")

        candidates.append(
            {
                "transactionId": tid,
                "date": txn["date"],
                "merchantName": txn["merchantName"],
                "accountName": txn["accountName"],
                "amount": txn["signedAmount"],
                "currentCategory": current_cat,
                "currentGroup": str(txn.get("groupName") or ""),
                "suggestedCategory": dominant_cat,
                "suggestedGroup": dominant_group,
                "categoryId": category_id,
                "confidence": round(confidence * 100) / 100,
                "source": "merchant_history",
                "reason": (
                    f"{profile['count']} reviewed transactions for this merchant are "
                    f"{round(dominant_share * 100)}% {dominant_cat}."
                ),
                "requiresNewCategory": False,
                "note": "",
                "setNeedsReview": False,
            }
        )

    return sorted(candidates, key=lambda c: (-float(c["confidence"]), -abs(float(c["amount"]))))


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_retirement_map(taxonomy: JsonObject) -> dict[tuple[str, str], dict]:
    """Returns {(category_name, group_name) → {targetCategory, targetGroup, note}}."""
    result: dict[tuple[str, str], dict] = {}
    for r in taxonomy.get("retirements") or []:
        if r.get("action") in {"delete", "keep_as_canonical"}:
            continue
        remap_to = r.get("remap_to")
        if not remap_to:
            continue
        slash = remap_to.index("/")
        target_group = remap_to[:slash]
        target_name = remap_to[slash + 1 :]
        result[(r["name"], r["group"])] = {
            "targetCategory": target_name,
            "targetGroup": target_group,
            "note": r.get("note"),
        }
    return result


def _build_virtual_remap(taxonomy: JsonObject) -> dict[str, str]:
    """Returns {retired_category_name → canonical_category_name}."""
    result: dict[str, str] = {}
    for r in taxonomy.get("retirements") or []:
        remap_to = r.get("remap_to")
        if not remap_to:
            continue
        slash = remap_to.index("/")
        target_name = remap_to[slash + 1 :]
        result[r["name"]] = target_name
    return result


def _identify_required_new_categories(
    taxonomy: JsonObject, category_id_by_name_group: dict[tuple[str, str], str]
) -> list[JsonObject]:
    """Categories that appear as migration targets but don't yet exist in the correct group."""
    needed: dict[str, str] = {}  # name → group
    for r in taxonomy.get("retirements") or []:
        remap_to = r.get("remap_to")
        if not remap_to:
            continue
        slash = remap_to.index("/")
        target_group = remap_to[:slash]
        target_name = remap_to[slash + 1 :]
        if (target_name, target_group) not in category_id_by_name_group:
            needed[target_name] = target_group

    return [{"name": name, "group": group} for name, group in sorted(needed.items())]


# ── Output ───────────────────────────────────────────────────────────────────


def _write_cleanup_plan(plan: JsonObject) -> None:
    existing_decisions = load_decisions()
    reset_dir(cleanup_latest_dir())
    write_json(cleanup_latest_dir() / "cleanup-plan.json", plan)
    if existing_decisions:
        write_json(cleanup_latest_dir() / "decisions.json", existing_decisions)

    all_candidates = plan["candidates"]
    ready = [c for c in all_candidates if not c.get("requiresNewCategory")]
    blocked = [c for c in all_candidates if c.get("requiresNewCategory")]

    write_csv(cleanup_latest_dir() / "cleanup-plan.csv", ready)
    write_csv(cleanup_latest_dir() / "cleanup-blocked.csv", blocked)
    write_text(cleanup_latest_dir() / "cleanup-plan.md", _render_cleanup_plan(plan))


def _render_cleanup_plan(plan: JsonObject) -> str:
    s = plan["summary"]
    cats_to_create = plan.get("categoriesToCreate") or []
    all_candidates = plan["candidates"]
    ready = [c for c in all_candidates if not c.get("requiresNewCategory")]
    blocked = [c for c in all_candidates if c.get("requiresNewCategory")]

    create_block = ""
    if cats_to_create:
        rows = "\n".join(f"- {c['group']}/{c['name']}" for c in cats_to_create)
        create_block = (
            "\n## Categories to Create First\n\n"
            "Create these in Monarch before applying blocked candidates:\n\n"
            f"{rows}\n"
        )

    def candidate_rows(items: list[JsonObject], limit: int = 100) -> str:
        return "\n".join(
            f"| {c['date']} | {c['merchantName']} | {c['currentCategory']} "
            f"| {c['suggestedCategory']} | {c['amount']} | {c['source']} | "
            f"{c['confidence']:.2f} | {c['reason'][:60]} |"
            for c in items[:limit]
        )

    ready_rows = candidate_rows(ready)
    blocked_rows = candidate_rows(blocked)

    return f"""# Taxonomy Cleanup Plan

- Generated at: {plan["generatedAt"]}
- Taxonomy migration candidates: {s["taxonomyMigrationCount"]}
- Merchant consistency candidates: {s["merchantConsistencyCount"]}
- Total: {s["totalCandidateCount"]} ({s["readyCount"]} ready, {s["blockedCount"]} blocked)
- Categories to create in Monarch: {s["categoriesToCreateCount"]}
{create_block}
## Ready to Apply ({s["readyCount"]})

| Date | Merchant | Current | Suggested | Amount | Source | Confidence | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
{ready_rows or "| _None_ |  |  |  |  |  |  |  |"}

## Blocked — Requires New Category ({s["blockedCount"]})

| Date | Merchant | Current | Suggested | Amount | Source | Confidence | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
{blocked_rows or "| _None_ |  |  |  |  |  |  |  |"}
"""
