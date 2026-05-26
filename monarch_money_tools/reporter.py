from __future__ import annotations

from typing import Any

from .paths import analysis_latest_dir, reports_latest_dir
from .storage import JsonObject, ensure_dir, read_json, write_csv, write_text


def run_report() -> None:
    analysis_path = analysis_latest_dir() / "analysis.json"
    if not analysis_path.exists():
        raise FileNotFoundError("No analysis found. Run `monarch analyze` first.")

    analysis = read_json(analysis_path)
    ensure_dir(reports_latest_dir())
    write_text(reports_latest_dir() / "summary.md", render_summary(analysis))
    write_text(reports_latest_dir() / "miscategorizations.md", render_miscategorizations(analysis))
    write_text(reports_latest_dir() / "rule-opportunities.md", render_rule_opportunities(analysis))
    write_text(reports_latest_dir() / "owner-review.md", render_owner_review(analysis))
    write_csv(reports_latest_dir() / "miscategorizations.csv", analysis["miscategorizations"])
    write_csv(reports_latest_dir() / "rule-opportunities.csv", analysis["ruleOpportunities"])
    write_csv(reports_latest_dir() / "owner-review.csv", analysis["ownerReviews"])


def render_summary(analysis: JsonObject) -> str:
    summary = analysis["summary"]
    rule_generation = analysis["ruleGeneration"]
    model = f" ({rule_generation['model']})" if rule_generation.get("model") else ""
    warning = f"- Warning: {rule_generation['warning']}\n" if rule_generation.get("warning") else ""
    return f"""# Monarch Review Summary

- Generated at: {analysis["generatedAt"]}
- Transactions analyzed: {summary["transactionCount"]}
- Recent transactions (45 days): {summary["recentTransactionCount"]}
- Unique merchant keys: {summary["uniqueMerchantCount"]}
- Miscategorization candidates: {summary["miscategorizationCount"]}
- Owner review candidates: {summary["ownerReviewCount"]}
- Rule opportunities: {summary["ruleOpportunityCount"]}
- Rule generation mode: {rule_generation["mode"]}{model}
- Rule candidate merchants reviewed: {rule_generation["candidateCount"]}
- AI batches used: {rule_generation["batchCount"]}

## Interpretation
- Use miscategorization findings to improve budget and expense tracking quality.
- Use owner review findings to tighten shared-expense settlement accuracy.
- Use rule opportunities only for repeated correction patterns, not for every merchant.
{warning}"""


def render_miscategorizations(analysis: JsonObject) -> str:
    rows = "\n".join(
        f"| {item['date']} | {item['merchantName']} | {item['currentCategory']} | "
        f"{item['suggestedCategory']} | {item['currentOwner'] or 'Unassigned'} | "
        f"{fixed(item['confidence'])} | {item['rationale']} |"
        for item in analysis["miscategorizations"][:100]
    )
    description = (
        "Top candidates for category cleanup. Confidence is heuristic and should be reviewed "
        "before any rule is created."
    )
    return f"""# Miscategorizations

{description}

| Date | Merchant | Current Category | Suggested Category | Current Owner | Confidence | Rationale |
| --- | --- | --- | --- | --- | --- | --- |
{rows or "| _No findings_ |  |  |  |  |  |  |"}
"""


def render_rule_opportunities(analysis: JsonObject) -> str:
    rows = "\n".join(
        f"| {item['exampleMerchant']} | {item['exampleCount']} | {item['dominantCategory']} | "
        f"{item['dominantOwner'] or 'None'} | {item['source']} | {fixed(item['confidence'])} | "
        f"{item['proposedCriteria']} | {item['proposedAction']} |"
        for item in analysis["ruleOpportunities"][:100]
    )
    header = (
        "| Merchant | Examples | Dominant Category | Dominant Owner | Source | Confidence | "
        "Proposed Criteria | Proposed Action |"
    )
    return f"""# Rule Opportunities

Stable merchant patterns worth considering as Monarch transaction rules.

{header}
| --- | --- | --- | --- | --- | --- | --- | --- |
{rows or "| _No findings_ |  |  |  |  |  |  |  |"}
"""


def render_owner_review(analysis: JsonObject) -> str:
    rows = "\n".join(
        f"| {item['date']} | {item['merchantName']} | {item['currentOwner']} | "
        f"{item['suggestedOwner'] or 'Review'} | {yes_no(item['currentNeedsReview'])} | "
        f"{yes_no(item['suggestedNeedsReview'])} | {item['categoryName']} | "
        f"{fixed(item['confidence'])} | {item['rationale']} |"
        for item in analysis["ownerReviews"][:100]
    )
    header = (
        "| Date | Merchant | Current Owner | Suggested Owner | Current Review | "
        "Suggested Review | Category | Confidence | Rationale |"
    )
    return f"""# Owner Review

Transactions whose Monarch `Owner` field looks inconsistent with prior merchant history.

{header}
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows or "| _No findings_ |  |  |  |  |  |  |  |  |"}
"""


def fixed(value: Any) -> str:
    return f"{float(value):.2f}"


def yes_no(value: object) -> str:
    return "Yes" if bool(value) else "No"
