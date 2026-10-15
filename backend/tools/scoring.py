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

from typing import List, Tuple, Optional
from backend.app.schemas import Finding, Severity, Verdict, AgentName

SEVERITY_WEIGHTS = {
    Severity.INFO: 0,
    Severity.LOW: 5,
    Severity.MEDIUM: 15,
    Severity.HIGH: 30,
    Severity.CRITICAL: 50
}


def score_findings(findings: List[Finding], ml_probability: Optional[float] = None) -> Tuple[int, Verdict]:
    """
    Computes deterministic risk score (0-100) and verdict based on finding severities and ML probability.
    Hybrid formula:
      final_risk_score = round(0.6 * agent_score + 40 * ml_probability)
    """
    # Compute specialist agent score excluding ML finding to prevent double-counting
    raw_agent_score = sum(
        SEVERITY_WEIGHTS.get(f.severity, 0)
        for f in findings
        if f.agent != AgentName.ML
    )
    agent_score = min(100, max(0, raw_agent_score))

    if ml_probability is not None:
        risk_score = min(100, max(0, round(0.6 * agent_score + 40 * float(ml_probability))))
    else:
        # When ML probability is not passed directly, sum all findings
        total_score = sum(SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings)
        risk_score = min(100, max(0, total_score))

    if risk_score < 30:
        verdict = Verdict.APPROVE
    elif risk_score < 70:
        verdict = Verdict.REVIEW
    else:
        verdict = Verdict.REJECT

    return risk_score, verdict

