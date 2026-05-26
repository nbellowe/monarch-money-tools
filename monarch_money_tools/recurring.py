from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from statistics import median, pstdev
from typing import cast

from .paths import normalized_latest_dir, reports_latest_dir
from .storage import JsonObject, now_iso, read_json, write_csv, write_text

DEFAULT_MIN_OCCURRENCES = 2
PRICE_DRIFT_THRESHOLD = 0.05
NEW_PATTERN_DAYS = 120
RECENT_DAYS = 45


@dataclass(frozen=True)
class RecurringTransaction:
    id: str
    date: date
    merchant_key: str
    merchant_name: str
    amount: float
    category_name: str
    account_name: str


def run_recurring(
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
    price_drift_threshold: float = PRICE_DRIFT_THRESHOLD,
) -> JsonObject:
    bundle_path = normalized_latest_dir() / "bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(
            "No normalized bundle found. Run `monarch pull` or `monarch import` first."
        )

    report = analyze_recurring(
        read_json(bundle_path),
        min_occurrences=min_occurrences,
        price_drift_threshold=price_drift_threshold,
    )
    write_csv(reports_latest_dir() / "recurring.csv", report["patterns"])
    write_text(reports_latest_dir() / "recurring.md", render_recurring_report(report))
    return report


def analyze_recurring(
    bundle: JsonObject,
    min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
    price_drift_threshold: float = PRICE_DRIFT_THRESHOLD,
) -> JsonObject:
    if min_occurrences < 2:
        raise ValueError("min_occurrences must be at least 2")

    transactions = _normalized_transactions(bundle)
    as_of = max(
        (transaction.date for transaction in transactions),
        default=datetime.now(UTC).date(),
    )
    groups: dict[str, list[RecurringTransaction]] = defaultdict(list)
    for transaction in transactions:
        groups[transaction.merchant_key].append(transaction)

    patterns: list[JsonObject] = []
    for merchant_transactions in groups.values():
        pattern = _analyze_group(
            merchant_transactions,
            as_of=as_of,
            min_occurrences=min_occurrences,
            price_drift_threshold=price_drift_threshold,
        )
        if pattern is not None:
            patterns.append(pattern)

    patterns = sorted(
        patterns,
        key=lambda item: (
            _status_sort_key(str(item["status"])),
            -float(item["annualizedAmount"]),
            str(item["merchantName"]),
        ),
    )
    summary = _build_summary(patterns, as_of, min_occurrences, price_drift_threshold)
    return {
        "generatedAt": now_iso(),
        "summary": summary,
        "patterns": patterns,
    }


def _normalized_transactions(bundle: JsonObject) -> list[RecurringTransaction]:
    transactions: list[RecurringTransaction] = []
    for raw in bundle.get("transactions") or []:
        if raw.get("isPending"):
            continue
        transaction_date = _parse_date(str(raw.get("date") or ""))
        if transaction_date is None:
            continue
        amount = _read_float(raw.get("signedAmount"))
        merchant_name = str(raw.get("merchantName") or "").strip()
        merchant_key = str(raw.get("normalizedMerchant") or merchant_name).strip().lower()
        if not merchant_key:
            continue
        transactions.append(
            RecurringTransaction(
                id=str(raw.get("id") or ""),
                date=transaction_date,
                merchant_key=merchant_key,
                merchant_name=merchant_name or merchant_key,
                amount=amount,
                category_name=str(raw.get("categoryName") or ""),
                account_name=str(raw.get("accountName") or ""),
            )
        )
    return transactions


def _analyze_group(
    transactions: list[RecurringTransaction],
    *,
    as_of: date,
    min_occurrences: int,
    price_drift_threshold: float,
) -> JsonObject | None:
    scoped = _dominant_direction_transactions(transactions)
    if len(scoped) < min_occurrences:
        return None
    if not any(abs(transaction.amount) > 0.01 for transaction in scoped):
        return None

    scoped = sorted(scoped, key=lambda transaction: transaction.date)
    intervals = _date_intervals(scoped)
    if not intervals:
        return None

    cadence = _classify_cadence(intervals)
    if cadence is None:
        return None

    nonzero_amounts = [
        abs(transaction.amount) for transaction in scoped if abs(transaction.amount) > 0.01
    ]
    if not nonzero_amounts:
        return None

    latest = scoped[-1]
    previous_nonzero = [
        abs(transaction.amount) for transaction in scoped[:-1] if abs(transaction.amount) > 0.01
    ]
    typical_amount = float(median(nonzero_amounts))
    previous_typical = float(median(previous_nonzero)) if previous_nonzero else typical_amount
    latest_amount = abs(latest.amount)
    drift_pct = (
        (latest_amount - previous_typical) / previous_typical
        if previous_typical > 0 and latest_amount > 0.01
        else 0.0
    )

    trial_conversion = _is_trial_conversion(scoped)
    cancelled = _is_cancelled(latest.date, cadence["cadenceDays"], as_of)
    price_drift = abs(drift_pct) >= price_drift_threshold
    new_pattern = _is_new_pattern(scoped, as_of, min_occurrences)
    status = _select_status(
        cancelled=cancelled,
        price_drift=price_drift,
        trial_conversion=trial_conversion,
        new_pattern=new_pattern,
    )
    flags = [
        flag
        for flag, enabled in [
            ("cancelled", cancelled),
            ("price_drift", price_drift),
            ("trial_conversion", trial_conversion),
            ("new", new_pattern),
        ]
        if enabled
    ] or ["stable"]

    merchant_name = Counter(transaction.merchant_name for transaction in scoped).most_common(1)[0][
        0
    ]
    category_name = Counter(transaction.category_name for transaction in scoped).most_common(1)[0][
        0
    ]
    signed_direction = "income" if latest.amount > 0 else "expense" if latest.amount < 0 else "zero"
    annualized_amount = _annualized_amount(typical_amount, cadence["cadenceDays"])

    return {
        "merchantKey": scoped[-1].merchant_key,
        "merchantName": merchant_name,
        "status": status,
        "flags": flags,
        "cadence": cadence["cadence"],
        "cadenceType": cadence["cadenceType"],
        "cadenceDays": cadence["cadenceDays"],
        "occurrenceCount": len(scoped),
        "firstDate": scoped[0].date.isoformat(),
        "lastDate": latest.date.isoformat(),
        "lastAmount": round(latest.amount, 2),
        "typicalAmount": round(typical_amount, 2),
        "previousTypicalAmount": round(previous_typical, 2),
        "priceDriftPct": round(drift_pct, 4),
        "annualizedAmount": round(annualized_amount, 2),
        "categoryName": category_name,
        "direction": signed_direction,
        "amountHistory": " | ".join(
            f"{transaction.date.isoformat()}:{transaction.amount:.2f}"
            for transaction in scoped[-8:]
        ),
    }


def _dominant_direction_transactions(
    transactions: list[RecurringTransaction],
) -> list[RecurringTransaction]:
    signs = Counter(
        _sign(transaction.amount) for transaction in transactions if _sign(transaction.amount)
    )
    if not signs:
        return transactions
    dominant_sign = signs.most_common(1)[0][0]
    return [
        transaction
        for transaction in transactions
        if _sign(transaction.amount) in {dominant_sign, 0}
    ]


def _date_intervals(transactions: list[RecurringTransaction]) -> list[int]:
    dates = sorted({transaction.date for transaction in transactions})
    return [
        (right - left).days
        for left, right in zip(dates, dates[1:], strict=False)
        if (right - left).days > 0
    ]


def _classify_cadence(intervals: list[int]) -> JsonObject | None:
    cadence_days = int(round(float(median(intervals))))
    max_delta = max(abs(interval - cadence_days) for interval in intervals)
    interval_cv = _coefficient_of_variation(intervals)

    if 5 <= cadence_days <= 9 and max_delta <= 2:
        return {"cadence": "weekly", "cadenceType": "weekly", "cadenceDays": cadence_days}
    if 25 <= cadence_days <= 35 and max_delta <= 7:
        return {"cadence": "monthly", "cadenceType": "monthly", "cadenceDays": cadence_days}
    if 330 <= cadence_days <= 400 and max_delta <= 45:
        return {"cadence": "annual", "cadenceType": "annual", "cadenceDays": cadence_days}
    if len(intervals) >= 2 and interval_cv <= 0.15:
        return {
            "cadence": f"every {cadence_days} days",
            "cadenceType": "irregular",
            "cadenceDays": cadence_days,
        }
    return None


def _coefficient_of_variation(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    average = sum(values) / len(values)
    return pstdev(values) / average if average else 0.0


def _is_trial_conversion(transactions: list[RecurringTransaction]) -> bool:
    first_paid_index = next(
        (index for index, transaction in enumerate(transactions) if abs(transaction.amount) > 0.01),
        None,
    )
    return first_paid_index is not None and any(
        abs(transaction.amount) <= 0.01 for transaction in transactions[:first_paid_index]
    )


def _is_cancelled(last_date: date, cadence_days: int, as_of: date) -> bool:
    expected_next = last_date + timedelta(days=cadence_days)
    overdue_days = (as_of - expected_next).days
    return overdue_days > max(14, int(cadence_days * 0.5))


def _is_new_pattern(
    transactions: list[RecurringTransaction],
    as_of: date,
    min_occurrences: int,
) -> bool:
    first_date = transactions[0].date
    last_date = transactions[-1].date
    return (
        len(transactions) <= max(3, min_occurrences)
        and first_date >= as_of - timedelta(days=NEW_PATTERN_DAYS)
        and last_date >= as_of - timedelta(days=RECENT_DAYS)
    )


def _select_status(
    *,
    cancelled: bool,
    price_drift: bool,
    trial_conversion: bool,
    new_pattern: bool,
) -> str:
    if cancelled:
        return "cancelled"
    if price_drift:
        return "price_drift"
    if trial_conversion:
        return "trial_conversion"
    if new_pattern:
        return "new"
    return "stable"


def _annualized_amount(typical_amount: float, cadence_days: int) -> float:
    if cadence_days <= 0:
        return 0
    return typical_amount * (365.25 / cadence_days)


def _build_summary(
    patterns: list[JsonObject],
    as_of: date,
    min_occurrences: int,
    price_drift_threshold: float,
) -> JsonObject:
    statuses = Counter(str(pattern["status"]) for pattern in patterns)
    return {
        "asOfDate": as_of.isoformat(),
        "minOccurrences": min_occurrences,
        "priceDriftThreshold": price_drift_threshold,
        "patternCount": len(patterns),
        "stableCount": statuses["stable"],
        "newCount": statuses["new"],
        "cancelledCount": statuses["cancelled"],
        "priceDriftCount": statuses["price_drift"],
        "trialConversionCount": statuses["trial_conversion"],
    }


def render_recurring_report(report: JsonObject) -> str:
    summary = report["summary"]
    lines = [
        "# Recurring Transactions",
        "",
        f"- Generated at: {report['generatedAt']}",
        f"- As of: {summary['asOfDate']}",
        f"- Minimum occurrences: {summary['minOccurrences']}",
        f"- Patterns detected: {summary['patternCount']}",
        f"- New: {summary['newCount']}",
        f"- Cancelled or quiet: {summary['cancelledCount']}",
        f"- Price drift: {summary['priceDriftCount']}",
        f"- Trial conversions: {summary['trialConversionCount']}",
        f"- Stable: {summary['stableCount']}",
        "",
    ]
    sections = [
        ("price_drift", "Price Drift"),
        ("new", "New Recurrences"),
        ("cancelled", "Cancelled or Quiet"),
        ("trial_conversion", "Trial Conversions"),
        ("stable", "Stable Patterns"),
    ]
    for status, title in sections:
        rows = [pattern for pattern in report["patterns"] if pattern["status"] == status]
        lines.extend(_render_section(title, rows))
    return "\n".join(lines).rstrip() + "\n"


def _render_section(title: str, rows: list[JsonObject]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Merchant | Cadence | Count | Last Date | Last Amount | Typical | Annualized | Flags |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    if rows:
        for row in rows:
            lines.append(
                f"| {row['merchantName']} | {row['cadence']} | {row['occurrenceCount']} | "
                f"{row['lastDate']} | {_money(row['lastAmount'])} | "
                f"{_money(row['typicalAmount'])} | {_money(row['annualizedAmount'])} | "
                f"{', '.join(row['flags'])} |"
            )
    else:
        lines.append("| _None_ |  |  |  |  |  |  |  |")
    lines.append("")
    return lines


def _status_sort_key(status: str) -> int:
    order = {
        "price_drift": 0,
        "new": 1,
        "cancelled": 2,
        "trial_conversion": 3,
        "stable": 4,
    }
    return order.get(status, 99)


def _money(value: object) -> str:
    return f"${float(cast(float | int | str, value)):,.2f}"


def _parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _read_float(value: object) -> float:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace("$", "").replace(",", "").strip())
        except ValueError:
            return 0
    return 0


def _sign(value: float) -> int:
    if value > 0.01:
        return 1
    if value < -0.01:
        return -1
    return 0


