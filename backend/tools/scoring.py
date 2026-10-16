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

    def _calc_score(items: List[Finding]) -> int:
        low_count = 0
        tot = 0
        for f in items:
            if f.severity == Severity.LOW:
                low_count += 1
                if low_count == 1:
                    tot += 5
                elif low_count == 2:
                    tot += 3
                elif low_count == 3:
                    tot += 2
                # 4th and subsequent low findings contribute 0 (diminishing returns, cap at 10)
            else:
                tot += SEVERITY_WEIGHTS.get(f.severity, 0)
        return tot

    # Calculate baseline non-RAG score
    non_rag_findings = [
        f for f in findings
        if f.agent not in (AgentName.ML, AgentName.RAG)
    ]
    raw_non_rag_score = _calc_score(non_rag_findings)
    baseline_agent_score = min(100, max(0, raw_non_rag_score))

    # Compute specialist agent score excluding ML finding to prevent double-counting
    specialist_findings = [
        f for f in findings
        if f.agent != AgentName.ML
    ]
    raw_agent_score = _calc_score(specialist_findings)
    agent_score = min(100, max(0, raw_agent_score))

    if ml_probability is not None:
        risk_score = min(100, max(0, round(0.6 * agent_score + 40 * float(ml_probability))))
    else:
        total_score = _calc_score(findings)
        risk_score = min(100, max(0, total_score))

    # Intent to deceive: prompt injection, provenance tampering, duplicate claim, or impossible travel triggers REJECT
    has_critical_injection = any(
        f.agent == AgentName.INJECTION and f.severity == Severity.CRITICAL
        for f in findings
    )
    has_critical_tampering = any(
        (f.agent == AgentName.PROVENANCE and f.severity == Severity.CRITICAL) or
        (f.check_id == "issued_doc_tampered")
        for f in findings
    )
    has_critical_duplicate = any(
        (f.agent == AgentName.CROSSREF and f.severity == Severity.CRITICAL) or
        (f.check_id in ("CROSS_INSURER_DUPLICATE_CLAIM", "EXACT_DUPLICATE_BILL"))
        for f in findings
    )
    has_impossible_travel = any(
        f.severity == Severity.CRITICAL and (
            f.check_id in ("DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL", "IMPOSSIBLE_TRAVEL_VELOCITY")
            or f.agent == AgentName.SPACETIME
        )
        for f in findings
    )
    has_critical_arithmetic = any(
        f.severity == Severity.CRITICAL and (
            f.check_id in ("SUBTOTAL_SUM_MISMATCH", "TOTAL_PAYABLE_MISMATCH", "LINE_ITEM_ARITHMETIC_MISMATCH")
            or (f.agent == AgentName.POLICY and "ARITHMETIC" in f.check_id)
        )
        for f in findings
    )

    has_failed_agent = any(
        f.check_id.startswith("AGENT_FAILED:") for f in findings
    )

    has_critical_inflation = any(
        f.severity == Severity.CRITICAL and f.check_id in (
            "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
            "LINE_ITEM_PRICE_ABOVE_BENCHMARK",
            "UNBUNDLED_OR_PADDED_ANCILLARY"
        )
        for f in findings
    )
    has_high_inflation = any(
        f.severity in (Severity.HIGH, Severity.CRITICAL) and f.check_id in (
            "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
            "LINE_ITEM_PRICE_ABOVE_BENCHMARK",
            "UNBUNDLED_OR_PADDED_ANCILLARY"
        )
        for f in findings
    )
    has_benchmark_inflation = any(
        f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL) and f.check_id in (
            "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
            "LINE_ITEM_PRICE_ABOVE_BENCHMARK",
            "UNBUNDLED_OR_PADDED_ANCILLARY"
        )
        for f in findings
    )

    has_deception_fraud = (
        has_critical_injection or
        has_critical_tampering or
        has_critical_duplicate or
        has_impossible_travel or
        has_critical_arithmetic or
        any(
            f.severity in (Severity.HIGH, Severity.CRITICAL) and f.check_id in (
                "EXACT_DUPLICATE_BILL",
                "CROSS_INSURER_DUPLICATE_CLAIM",
                "issued_doc_tampered",
                "FONT_INCONSISTENCY_TAMPERING",
                "SUSPICIOUS_PRODUCER_METADATA",
                "DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL",
                "IMPOSSIBLE_TRAVEL_VELOCITY",
                "SUBTOTAL_SUM_MISMATCH",
                "TOTAL_PAYABLE_MISMATCH",
                "LINE_ITEM_ARITHMETIC_MISMATCH"
            )
            for f in findings
        )
    )

    has_procedure_inflation = any(
        f.check_id == "LINE_ITEM_PRICE_ABOVE_BENCHMARK" and
        f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL) and
        f.computed_details and f.computed_details.get("category") != "room_rent"
        for f in findings
    )

    has_policy_clause_only = (
        len(findings) > 0 and any(
            f.check_id in ("POLICY_ROOM_RENT_CAP_EXCEEDED", "POLICY_COPAY_MISCALCULATION")
            for f in findings
        ) and all(
            f.agent in (AgentName.POLICY, AgentName.ML, AgentName.RAG) or
            f.check_id in (
                "POLICY_ROOM_RENT_CAP_EXCEEDED",
                "POLICY_COPAY_MISCALCULATION",
                "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
                "LINE_ITEM_PRICE_ABOVE_BENCHMARK",
                "UNBUNDLED_OR_PADDED_ANCILLARY",
                "BQML_HIGH_RISK_ANOMALY",
                "matches_known_pattern",
                "ungrounded_number"
            )
            for f in findings
        ) and not has_deception_fraud and not has_procedure_inflation
    )

    if has_deception_fraud or (has_critical_inflation and not has_policy_clause_only):
        risk_score = max(risk_score, 85)
        verdict = Verdict.REJECT
    elif risk_score < 30:
        if has_failed_agent:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 30)
        elif has_high_inflation:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 45)
        elif has_benchmark_inflation:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 40)
        else:
            verdict = Verdict.APPROVE
    elif risk_score < 70:
        verdict = Verdict.REVIEW
    else:
        # If the claim is purely a policy clause tariff cap overrun (e.g. room rent cap breach)
        # without deceptive fraud, route to adjuster REVIEW for line-item deduction.
        if has_policy_clause_only:
            verdict = Verdict.REVIEW
            risk_score = min(risk_score, 65)
        else:
            verdict = Verdict.REJECT

    # A claim with only "low" findings and no deception/tampering should remain APPROVE unless ML probability is high
    has_higher_severity = any(
        f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        for f in findings
        if f.agent != AgentName.ML
    )
    if not has_higher_severity and not has_deception_fraud and (ml_probability is None or ml_probability < 0.70):
        risk_score = min(28, risk_score)
        verdict = Verdict.APPROVE

    # Guardrail: two or more high/critical findings cannot end at APPROVE or low REVIEW (< 65)
    high_or_critical_count = sum(
        1 for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)
    )
    if high_or_critical_count >= 2:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 65)

    # Inflation guardrail: benchmark inflation findings cannot leave a claim at APPROVE
    if has_high_inflation and verdict == Verdict.APPROVE:
        verdict = Verdict.REVIEW
        risk_score = max(risk_score, 45)
    elif has_benchmark_inflation and verdict == Verdict.APPROVE:
        verdict = Verdict.REVIEW
        risk_score = max(risk_score, 40)

    # Incomplete dossier guardrail: never allow APPROVE if an agent failed
    if has_failed_agent and verdict == Verdict.APPROVE:
        verdict = Verdict.REVIEW
        risk_score = max(risk_score, 30)

    return risk_score, verdict

