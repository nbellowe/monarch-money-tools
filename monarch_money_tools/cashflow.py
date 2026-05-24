from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .paths import cashflow_latest_dir, normalized_latest_dir
from .profile import UserProfile
from .storage import read_json, reset_dir, write_csv, write_json, write_text

JsonObject = dict[str, Any]

LABEL_SALARY = "salary"
LABEL_REIMBURSEMENT = "reimbursement"
LABEL_TRANSFER = "transfer"
LABEL_INVESTMENT = "investment_proceeds"
LABEL_SPENDING = "spending"

_SALARY_CATEGORIES = {"Paychecks"}
_INVESTMENT_CATEGORIES = {"Sell Investment"}
_TRANSFER_CATEGORIES = {"Transfer", "Credit Card Payment"}


def classify_transactions(
    transactions: list[JsonObject],
    profile: UserProfile | None,
    start: str | None = None,
    end: str | None = None,
) -> list[JsonObject]:
    filtered = [
        transaction
        for transaction in transactions
        if (start is None or str(transaction.get("date", "")) >= start)
        and (end is None or str(transaction.get("date", "")) <= end)
    ]
    return [_annotate(transaction, profile) for transaction in filtered]


def run_income_overlay(
    profile: UserProfile | None,
    start: str | None = None,
    end: str | None = None,
) -> JsonObject:
    bundle_path = normalized_latest_dir() / "bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(
            "No normalized bundle. Run `monarch pull` or `monarch import` first."
        )

    bundle = read_json(bundle_path)
    transactions = [t for t in (bundle.get("transactions") or []) if not t.get("isPending")]
    classified = classify_transactions(transactions, profile, start=start, end=end)

    counts: dict[str, int] = {}
    totals: dict[str, float] = {}
    manual_review_count = 0
    for transaction in classified:
        label = str(transaction["classification"])
        counts[label] = counts.get(label, 0) + 1
        totals[label] = totals.get(label, 0.0) + float(transaction.get("signedAmount") or 0)
        if transaction["manual_review"]:
            manual_review_count += 1

    label_order = [
        LABEL_SALARY,
        LABEL_REIMBURSEMENT,
        LABEL_TRANSFER,
        LABEL_INVESTMENT,
        LABEL_SPENDING,
    ]
    summary = {
        "transactionCount": len(classified),
        "manualReviewCount": manual_review_count,
        "byLabel": [
            {"label": label, "count": counts[label], "total": round(totals[label], 2)}
            for label in label_order
            if label in counts
        ],
    }
    result = {"summary": summary, "transactions": classified}

    out_dir = cashflow_latest_dir()
    reset_dir(out_dir)
    write_json(out_dir / "income-overlay.json", result)
    write_csv(out_dir / "income-overlay.csv", classified)
    _write_markdown(out_dir / "income-overlay.md", summary)
    return result


def _annotate(transaction: JsonObject, profile: UserProfile | None) -> JsonObject:
    label, manual_review = _classify_one(transaction, profile)
    return {**transaction, "classification": label, "manual_review": manual_review}


def _classify_one(transaction: JsonObject, profile: UserProfile | None) -> tuple[str, bool]:
    merchant = str(transaction.get("merchantName") or "")
    category = str(transaction.get("categoryName") or "")

    if profile is not None:
        cashflow = profile.cashflow
        if _matches_any(merchant, [pattern.pattern for pattern in cashflow.income_sources]):
            return LABEL_SALARY, False
        if _matches_any(merchant, [pattern.pattern for pattern in cashflow.reimbursement_patterns]):
            return LABEL_REIMBURSEMENT, False
        if _matches_any(merchant, [pattern.pattern for pattern in cashflow.transfer_patterns]):
            return LABEL_TRANSFER, False

    if category in _SALARY_CATEGORIES:
        return LABEL_SALARY, False
    if category in _INVESTMENT_CATEGORIES:
        return LABEL_INVESTMENT, False
    if category in _TRANSFER_CATEGORIES:
        return LABEL_TRANSFER, False

    return LABEL_SPENDING, False


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns)


def _write_markdown(path: Path, summary: JsonObject) -> None:
    lines = [
        "# Income Overlay\n",
        f"Total transactions: {summary['transactionCount']}\n",
    ]
    if summary["manualReviewCount"]:
        lines.append(f"**Manual review needed: {summary['manualReviewCount']}**\n")
    lines.append("\n| Classification | Count | Total |\n|---|---|---|\n")
    for row in summary["byLabel"]:
        lines.append(f"| {row['label']} | {row['count']} | ${row['total']:,.2f} |\n")
    write_text(path, "".join(lines))
