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
    # Guardrail A4: A finding whose only evidence is a retrieved pattern is capped at severity "low"
    # and cannot by itself move a verdict from approve to reject.
    for f in findings:
        is_rag_pattern = (f.agent == AgentName.RAG) or (
            f.evidence and all(ev.layer == "retrieved" for ev in f.evidence)
        )
        if is_rag_pattern:
            if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL):
                f.severity = Severity.LOW

    # Calculate baseline non-RAG score
    non_rag_findings = [
        f for f in findings
        if f.agent not in (AgentName.ML, AgentName.RAG)
    ]
    raw_non_rag_score = sum(SEVERITY_WEIGHTS.get(f.severity, 0) for f in non_rag_findings)
    baseline_agent_score = min(100, max(0, raw_non_rag_score))

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
        total_score = sum(SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings)
        risk_score = min(100, max(0, total_score))

    # Intent to deceive: prompt injection attack or issued document tampering triggers REJECT
    has_critical_injection = any(
        f.agent == AgentName.INJECTION and f.severity == Severity.CRITICAL
        for f in findings
    )
    has_critical_tampering = any(
        (f.agent == AgentName.PROVENANCE and f.severity == Severity.CRITICAL) or
        (f.check_id == "issued_doc_tampered")
        for f in findings
    )

    if has_critical_injection or has_critical_tampering:
        risk_score = max(risk_score, 85)
        verdict = Verdict.REJECT
    elif risk_score < 30:
        verdict = Verdict.APPROVE
    elif risk_score < 70:
        verdict = Verdict.REVIEW
    else:
        # A retrieved pattern cannot by itself move a verdict from approve to reject
        if baseline_agent_score < 30 and not has_critical_injection:
            verdict = Verdict.REVIEW
            risk_score = min(risk_score, 65)
        else:
            verdict = Verdict.REJECT

    return risk_score, verdict

