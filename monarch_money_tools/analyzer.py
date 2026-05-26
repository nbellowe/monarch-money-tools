from __future__ import annotations

from typing import Any

from .analysis import prepare_analysis
from .paths import analysis_latest_dir
from .storage import load_bundle, reset_dir, write_json


def run_analyze() -> dict[str, Any]:
    prepared = prepare_analysis(load_bundle())
    rule_opportunities = prepared["heuristicRuleOpportunities"]
    analysis = {
        "generatedAt": prepared["generatedAt"],
        "summary": {
            **prepared["summary"],
            "ruleOpportunityCount": len(rule_opportunities),
        },
        "ruleGeneration": {
            "mode": "heuristic",
            "candidateCount": len(prepared["ruleCandidates"]),
            "batchCount": 0,
            "warning": "AI rule generation has not been ported to the Python CLI yet.",
        },
        "miscategorizations": prepared["miscategorizations"],
        "ownerReviews": prepared["ownerReviews"],
        "ruleOpportunities": rule_opportunities,
    }

    reset_dir(analysis_latest_dir())
    write_json(analysis_latest_dir() / "analysis.json", analysis)
    write_json(analysis_latest_dir() / "summary.json", analysis["summary"])
    write_json(analysis_latest_dir() / "rule-candidates.json", prepared["ruleCandidates"])
    return analysis
