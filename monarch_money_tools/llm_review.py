"""
LLM-assisted review pass — Step 3 of the historic cleanup plan.

Focuses on transactions where merchant history has no signal:
  - Uncategorized: need a category assigned
  - Misc Travel Expenses: catch-all that often hides specific categories
  - Paychecks: verify nothing non-payroll slipped through

Strategy: group by normalized merchant, send batches to an LLM, generate
an apply-ready plan at data/review/latest/llm-review-plan.{json,csv,md}.

Backends:
  cli  — pipes through `claude -p` (uses Claude Code auth, no API key needed)
  api  — calls Anthropic API directly (requires ANTHROPIC_API_KEY in .env)

Each batch contains up to MERCHANTS_PER_BATCH merchants. The full canonical
category list (~71 names) is included in every batch prompt as context.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import yaml

from .env import get_config
from .paths import canonical_taxonomy_file, normalized_latest_dir, review_latest_dir
from .storage import read_json, write_csv, write_json, write_text

JsonObject = dict[str, Any]

FOCUS_CATEGORIES = {"Uncategorized", "Misc Travel Expenses", "Paychecks"}
EXCLUDE_SUGGESTIONS = {"Uncategorized"}

MERCHANTS_PER_BATCH = 30
HIGH_CONFIDENCE_THRESHOLD = 0.85

DEFAULT_CLI_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_API_MODEL = "claude-haiku-4-5-20251001"

# Accounts where transactions represent person-to-person payments (Venmo, Zelle,
# Cash App, etc.). These require manual context the LLM can't infer from name+amount
# alone, so they're skipped by default.
P2P_ACCOUNT_PATTERNS = {"personal profile", "venmo", "zelle", "cash app", "splitwise"}


def build_llm_review_plan(
    focus_categories: set[str] | None = None,
    dry_run: bool = False,
    backend: str = "cli",
    model: str | None = None,
    skip_p2p: bool = True,
) -> JsonObject:
    if focus_categories is None:
        focus_categories = FOCUS_CATEGORIES

    config = get_config()
    bundle = read_json(normalized_latest_dir() / "bundle.json")

    taxonomy_path = canonical_taxonomy_file()
    with open(taxonomy_path, encoding="utf-8") as f:
        taxonomy: JsonObject = yaml.safe_load(f)

    def _is_p2p(t: JsonObject) -> bool:
        acct = (t.get("accountName") or "").lower()
        return any(p in acct for p in P2P_ACCOUNT_PATTERNS)

    transactions: list[JsonObject] = [
        t
        for t in (bundle.get("transactions") or [])
        if not t.get("isPending")
        and t.get("needsReview")
        and (t.get("categoryName") or "Uncategorized") in focus_categories
        and not (skip_p2p and _is_p2p(t))
    ]
    categories: list[JsonObject] = list(bundle.get("categories") or [])
    category_id_by_name = {str(c["name"]): str(c["id"]) for c in categories}
    canonical_names = sorted(c["name"] for c in taxonomy["categories"])

    merchant_groups = _group_by_merchant(transactions)
    merchant_list = sorted(merchant_groups.items(), key=lambda kv: -len(kv[1]))
    batches = [
        merchant_list[i : i + MERCHANTS_PER_BATCH]
        for i in range(0, len(merchant_list), MERCHANTS_PER_BATCH)
    ]

    if dry_run:
        return {
            "dryRun": True,
            "transactionCount": len(transactions),
            "merchantCount": len(merchant_groups),
            "batchCount": len(batches),
            "focusCategories": sorted(focus_categories),
            "backend": backend,
            "skipP2P": skip_p2p,
            "model": model or (DEFAULT_CLI_MODEL if backend == "cli" else DEFAULT_API_MODEL),
        }

    if backend == "api" and not config.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to .env, or use --backend cli.")

    resolved_model = model or (DEFAULT_CLI_MODEL if backend == "cli" else config.anthropic_model)

    all_suggestions: list[JsonObject] = []
    for batch_idx, batch in enumerate(batches):
        txn_count = sum(len(merchant_groups[k]) for k, _ in batch)
        print(
            f"  Batch {batch_idx + 1}/{len(batches)}: "
            f"{len(batch)} merchants, {txn_count} transactions"
        )
        prompt = _build_prompt(batch, canonical_names)
        if backend == "cli":
            raw = _call_cli(prompt, resolved_model)
        else:
            raw = _call_api(prompt, resolved_model, config.anthropic_api_key)  # type: ignore[arg-type]
        all_suggestions.extend(_parse_response(raw))

    updates = _build_updates(all_suggestions, transactions, category_id_by_name)
    plan = _assemble_plan(updates, transactions, focus_categories, backend, resolved_model)
    _write_plan(plan)
    return plan


# ── Grouping ──────────────────────────────────────────────────────────────────


def _group_by_merchant(transactions: list[JsonObject]) -> dict[str, list[JsonObject]]:
    groups: dict[str, list[JsonObject]] = defaultdict(list)
    for t in transactions:
        key = str(t.get("normalizedMerchant") or t.get("merchantName") or "Unknown")
        groups[key].append(t)
    return dict(groups)


# ── Prompt ────────────────────────────────────────────────────────────────────


def _build_prompt(
    batch: list[tuple[str, list[JsonObject]]],
    canonical_names: list[str],
) -> str:
    merchant_lines = []
    for merchant_key, txns in batch:
        amounts = [float(t.get("signedAmount") or 0) for t in txns]
        current_cats = sorted({t.get("categoryName") or "Uncategorized" for t in txns})
        accounts = sorted({t.get("accountName") or "" for t in txns})
        dates = sorted(t["date"] for t in txns)
        sample_names = sorted({t.get("merchantName") or "" for t in txns})[:3]
        merchant_lines.append(
            f"- merchant_key: {json.dumps(merchant_key)}\n"
            f"  display_names: {json.dumps(sample_names)}\n"
            f"  count: {len(txns)}\n"
            f"  amount_range: [{min(amounts):.2f}, {max(amounts):.2f}]\n"
            f"  date_range: [{dates[0]}, {dates[-1]}]\n"
            f"  current_categories: {json.dumps(current_cats)}\n"
            f"  accounts: {json.dumps(accounts[:3])}"
        )

    categories_block = "\n".join(f"  - {name}" for name in canonical_names)
    merchants_block = "\n".join(merchant_lines)

    return textwrap.dedent(f"""
        You are helping categorize personal finance transactions for a Monarch Money account.

        Canonical categories (use ONLY these exact names):
        {categories_block}

        For each merchant below, suggest the single best category and a confidence (0.0–1.0).
        Consider: merchant name, amount sign (positive=income/refund, negative=expense),
        accounts involved, and date patterns.

        Special rules:
        - "Transfer" = money moving between own accounts (checking↔savings, brokerage deposits)
        - "Credit Card Payment" = paying off a credit card from a checking account
        - "Paychecks" = only direct employer payroll deposits (not reimbursements)
        - "Buy Investment" / "Sell Investment" = brokerage trades
        - Negative amounts in income categories are almost always wrong
        - If genuinely ambiguous, use confidence < 0.7

        Merchants to classify:
        {merchants_block}

        Respond with a JSON array, one object per merchant, in the same order:
        [
          {{
            "merchant_key": "...",
            "category": "exact canonical name",
            "confidence": 0.0,
            "reason": "one sentence"
          }}
        ]
        Respond with ONLY the JSON array, no other text.
    """).strip()


# ── Backends ──────────────────────────────────────────────────────────────────


def _call_cli(prompt: str, model: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", model],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "no output")[:600]
        raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {detail}")
    return result.stdout.strip()


def _call_api(prompt: str, model: str, api_key: str) -> str:
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("Install LLM support with `uv sync --extra llm`.") from e

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = getattr(message.content[0], "text", None)
    if not isinstance(text, str):
        raise RuntimeError("Anthropic response did not include a text block.")
    return text.strip()


def _parse_response(raw: str) -> list[JsonObject]:
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


# ── Plan assembly ─────────────────────────────────────────────────────────────


def _build_updates(
    suggestions: list[JsonObject],
    transactions: list[JsonObject],
    category_id_by_name: dict[str, str],
) -> list[JsonObject]:
    suggestion_map = {s["merchant_key"]: s for s in suggestions}
    txn_by_merchant: dict[str, list[JsonObject]] = defaultdict(list)
    for t in transactions:
        key = str(t.get("normalizedMerchant") or t.get("merchantName") or "Unknown")
        txn_by_merchant[key].append(t)

    updates: list[JsonObject] = []
    for merchant_key, suggestion in suggestion_map.items():
        suggested_cat = suggestion.get("category", "")
        confidence = float(suggestion.get("confidence", 0))
        reason = suggestion.get("reason", "")

        if suggested_cat in EXCLUDE_SUGGESTIONS:
            continue

        category_id = category_id_by_name.get(suggested_cat, "")
        if not category_id:
            continue

        for t in txn_by_merchant.get(merchant_key, []):
            if t.get("categoryName") == suggested_cat:
                continue
            updates.append(
                {
                    "transactionId": str(t["id"]),
                    "date": t["date"],
                    "merchantName": t.get("merchantName") or "",
                    "accountName": t.get("accountName") or "",
                    "amount": float(t.get("signedAmount") or 0),
                    "currentCategory": t.get("categoryName") or "Uncategorized",
                    "suggestedCategory": suggested_cat,
                    "categoryId": category_id,
                    "confidence": round(confidence * 100) / 100,
                    "source": "llm_review",
                    "reason": reason,
                    "setNeedsReview": False,
                }
            )

    return sorted(updates, key=lambda u: (-u["confidence"], -abs(u["amount"])))


def _assemble_plan(
    updates: list[JsonObject],
    transactions: list[JsonObject],
    focus_categories: set[str],
    backend: str,
    model: str,
) -> JsonObject:
    high = [u for u in updates if u["confidence"] >= HIGH_CONFIDENCE_THRESHOLD]
    low = [u for u in updates if u["confidence"] < HIGH_CONFIDENCE_THRESHOLD]
    return {
        "generatedAt": _now_iso(),
        "summary": {
            "focusCategories": sorted(focus_categories),
            "inputTransactionCount": len(transactions),
            "updateCount": len(updates),
            "highConfidenceCount": len(high),
            "lowConfidenceCount": len(low),
            "backend": backend,
            "model": model,
        },
        "updates": updates,
    }


# ── Output ────────────────────────────────────────────────────────────────────


def _write_plan(plan: JsonObject) -> None:
    out = review_latest_dir()
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "llm-review-plan.json", plan)
    write_csv(out / "llm-review-plan.csv", plan["updates"])
    write_text(out / "llm-review-plan.md", _render_plan(plan))


def _render_plan(plan: JsonObject) -> str:
    s = plan["summary"]
    updates = plan["updates"]
    high = [u for u in updates if u["confidence"] >= HIGH_CONFIDENCE_THRESHOLD]
    low = [u for u in updates if u["confidence"] < HIGH_CONFIDENCE_THRESHOLD]
    update_summary = (
        f"{s['updateCount']} ({s['highConfidenceCount']} high-confidence "
        f"≥{HIGH_CONFIDENCE_THRESHOLD}, {s['lowConfidenceCount']} low)"
    )

    def rows(items: list[JsonObject], limit: int = 300) -> str:
        return "\n".join(
            f"| {u['date']} | {u['merchantName'][:35]} | {u['currentCategory']} "
            f"| {u['suggestedCategory']} | {u['confidence']:.2f} | {u['reason'][:60]} |"
            for u in items[:limit]
        )

    return f"""# LLM Review Plan

- Generated: {plan["generatedAt"]}
- Backend: {s["backend"]} / {s["model"]}
- Focus categories: {", ".join(s["focusCategories"])}
- Input transactions: {s["inputTransactionCount"]}
- Updates proposed: {update_summary}

## High Confidence ({s["highConfidenceCount"]})

| Date | Merchant | Current | Suggested | Conf | Reason |
| --- | --- | --- | --- | --- | --- |
{rows(high) or "| _None_ | | | | | |"}

## Low Confidence ({s["lowConfidenceCount"]})

| Date | Merchant | Current | Suggested | Conf | Reason |
| --- | --- | --- | --- | --- | --- |
{rows(low) or "| _None_ | | | | | |"}
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
