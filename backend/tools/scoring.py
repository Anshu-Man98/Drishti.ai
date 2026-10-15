"""
Deterministic scoring and verdict calculation for FinShield findings.
LLMs never invent or alter risk scores.
Weights:
  - info: 0
  - low: 5
  - medium: 15
  - high: 30
  - critical: 50
Capped at 100.
Verdict:
  - approve: < 30
  - review: 30-69
  - reject: >= 70
"""

from typing import List, Tuple
from backend.app.schemas import Finding, Severity, Verdict

SEVERITY_WEIGHTS = {
    Severity.INFO: 0,
    Severity.LOW: 5,
    Severity.MEDIUM: 15,
    Severity.HIGH: 30,
    Severity.CRITICAL: 50
}


def score_findings(findings: List[Finding]) -> Tuple[int, Verdict]:
    """
    Computes deterministic risk score (0-100) and verdict based on finding severities.
    """
    raw_score = sum(SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings)
    risk_score = min(100, max(0, raw_score))

    if risk_score < 30:
        verdict = Verdict.APPROVE
    elif risk_score < 70:
        verdict = Verdict.REVIEW
    else:
        verdict = Verdict.REJECT

    return risk_score, verdict
