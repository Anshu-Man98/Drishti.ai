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

from typing import List, Tuple, Optional, Any, Union
from backend.app.schemas import Finding, Severity, Verdict, AgentName

SEVERITY_WEIGHTS = {
    Severity.INFO: 0,
    Severity.LOW: 5,
    Severity.MEDIUM: 15,
    Severity.HIGH: 30,
    Severity.CRITICAL: 50
}


def calculate_diminishing_score(weights: List[float]) -> float:
    """
    Combines finding weights using diminishing returns / decaying weights:
      w_1 + 0.8 * w_2 + 0.6 * w_3 + 0.4 * sum_{i >= 4} w_i
    where weights are sorted in descending order.
    """
    if not weights:
        return 0.0
    sorted_w = sorted(weights, reverse=True)
    total = 0.0
    for idx, w in enumerate(sorted_w):
        if idx == 0:
            total += w
        elif idx == 1:
            total += 0.8 * w
        elif idx == 2:
            total += 0.6 * w
        else:
            total += 0.4 * w
    return total


def is_incomplete_analysis_condition(f: Union[Finding, dict, Any]) -> bool:
    """
    Returns True if finding indicates document unreadability, extraction failure,
    hidden-text classification failure, non-medical bill, or pipeline agent failure/timeout.
    If any such condition exists, dossier status is 'incomplete' and the final verdict
    floor is REVIEW (never APPROVE), with risk score reflecting unanalysed risk (min 45).
    """
    if isinstance(f, dict):
        cid = (f.get("check_id") or "").lower()
        title = (f.get("title") or "").lower()
        exp = (f.get("explanation") or "").lower()
    else:
        cid = (getattr(f, "check_id", None) or "").lower()
        title = (getattr(f, "title", None) or "").lower()
        exp = (getattr(f, "explanation", None) or "").lower()

    # 1. Document unreadable / blurred / cropped / low-DPI / OCR confidence below threshold
    if (
        "unreadable" in cid or "unreadable" in title or "unreadable" in exp
        or "blurred" in cid or "blurred" in title or "blur" in cid
        or "cropped" in cid or "cropped" in title
        or "low_dpi" in cid or "low-dpi" in title or "low dpi" in title
        or ("ocr" in cid and "confidence" in cid)
        or ("ocr" in title and "confidence" in title)
        or "document_quality_failure" in cid
        or "document_corrupt" in cid
    ):
        return True

    # 2. Extraction incomplete / missing mandatory fields (total, hospital, diagnosis)
    if (
        "extraction_incomplete" in cid or "extraction incomplete" in title
        or "missing_mandatory" in cid or "missing mandatory" in title
        or "missing_field" in cid or "missing mandatory" in exp
    ):
        return True

    # 3. Hidden-text classification could not run
    if (
        "hidden_text_classification_unavailable" in cid
        or ("hidden_text" in cid and ("unavailable" in cid or "failed" in cid or "error" in cid))
        or ("hidden text" in title and ("could not run" in title or "unavailable" in title or "failed" in title))
    ):
        return True

    # 4. Agent failed or timed out during pipeline
    if (
        cid.startswith("agent_failed:")
        or cid.startswith("agent_timeout:")
        or cid == "bqml_service_failure"
        or "agent failed" in title
        or "agent timed out" in title
        or "pipeline_agent_error" in cid
        or "pipeline_timeout" in cid
        or "pipeline timeout" in title
    ):
        return True

    # 5. Non-medical document submitted (e.g. dining / restaurant receipt)
    if (
        "not_a_medical_bill" in cid
        or "not a medical bill" in title
        or "non-medical" in title
        or "non_medical" in cid
    ):
        return True

    # 6. LLM Token budget exceeded
    if (
        "token_budget_exceeded" in cid
        or "token budget exceeded" in title
        or "token budget exceeded" in exp
    ):
        return True

    return False


def score_findings(findings: List[Finding], ml_probability: Optional[float] = None) -> Tuple[int, Verdict]:
    """
    Computes deterministic risk score (0-100) and verdict based on finding severities and ML probability.
    Hybrid formula:
      final_risk_score = round(0.6 * agent_score + 40 * ml_probability)
    """
    # Guardrail A4: A finding whose only evidence is a general retrieved pattern is capped at severity "low"
    # and cannot by itself move a verdict from approve to reject.
    # Active learned evasion patterns from the adversarial arena are exempt from this cap.
    for f in findings:
        is_learned = (
            (f.computed_details and f.computed_details.get("is_learned_evasion")) or
            (f.evidence and any("PAT-LEARNED-" in str(ev.doc_id) for ev in f.evidence)) or
            "learned" in f.title.lower() or
            f.check_id == "learned_evasion_match"
        )
        is_rag_pattern = ((f.agent == AgentName.RAG) or (
            f.evidence and all(ev.layer == "retrieved" for ev in f.evidence)
        )) and not is_learned

        if is_rag_pattern:
            if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL):
                f.severity = Severity.LOW

    # Calculate baseline non-RAG score
    non_rag_findings = [
        f for f in findings
        if f.agent not in (AgentName.ML, AgentName.RAG)
    ]
    non_rag_weights = [SEVERITY_WEIGHTS.get(f.severity, 0) for f in non_rag_findings]
    raw_non_rag_score = calculate_diminishing_score(non_rag_weights)
    baseline_agent_score = min(100, max(0, round(raw_non_rag_score)))

    # Compute specialist agent score excluding ML finding to prevent double-counting
    agent_weights = [
        SEVERITY_WEIGHTS.get(f.severity, 0)
        for f in findings
        if f.agent != AgentName.ML
    ]
    raw_agent_score = calculate_diminishing_score(agent_weights)
    agent_score = min(100, max(0, round(raw_agent_score)))

    if ml_probability is not None:
        risk_score = min(100, max(0, round(0.6 * agent_score + 40 * float(ml_probability))))
    else:
        all_weights = [SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings]
        total_score = calculate_diminishing_score(all_weights)
        risk_score = min(100, max(0, round(total_score)))

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
            f.check_id in ("SUBTOTAL_SUM_MISMATCH", "TOTAL_PAYABLE_MISMATCH", "LINE_ITEM_ARITHMETIC_MISMATCH", "LINE_ITEM_MATH_MISMATCH")
            or (f.agent == AgentName.POLICY and "ARITHMETIC" in f.check_id)
        )
        for f in findings
    )
    has_high_arithmetic = any(
        f.severity == Severity.HIGH and f.check_id in (
            "SUBTOTAL_SUM_MISMATCH",
            "TOTAL_PAYABLE_MISMATCH",
            "LINE_ITEM_ARITHMETIC_MISMATCH",
            "LINE_ITEM_MATH_MISMATCH"
        )
        for f in findings
    )
    has_medium_arithmetic = any(
        f.severity in (Severity.LOW, Severity.MEDIUM) and f.check_id in (
            "SUBTOTAL_SUM_MISMATCH",
            "TOTAL_PAYABLE_MISMATCH",
            "LINE_ITEM_ARITHMETIC_MISMATCH",
            "LINE_ITEM_MATH_MISMATCH"
        )
        for f in findings
    )

    has_suspicious_producer = any(
        f.check_id == "SUSPICIOUS_PRODUCER_METADATA" for f in findings
    )
    has_producer_corroboration = any(
        f.severity in (Severity.HIGH, Severity.CRITICAL) and f.check_id in (
            "FONT_INCONSISTENCY_TAMPERING",
            "issued_doc_tampered",
            "REVERSED_HOSPITALIZATION_DATES",
            "FUTURE_OR_IMPLAUSIBLE_DATE",
            "EXACT_DUPLICATE_BILL",
            "CROSS_INSURER_DUPLICATE_CLAIM",
            "DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL",
            "IMPOSSIBLE_TRAVEL_VELOCITY",
            "SUBTOTAL_SUM_MISMATCH",
            "TOTAL_PAYABLE_MISMATCH",
            "LINE_ITEM_ARITHMETIC_MISMATCH",
            "LINE_ITEM_MATH_MISMATCH"
        )
        for f in findings
    )
    has_producer_deception = has_suspicious_producer and has_producer_corroboration

    has_incomplete_condition = any(
        is_incomplete_analysis_condition(f) for f in findings
    )
    has_failed_agent = has_incomplete_condition

    has_critical_inflation = any(
        f.severity == Severity.CRITICAL and f.check_id in (
            "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
            "LINE_ITEM_PRICE_ABOVE_BENCHMARK",
            "UNBUNDLED_OR_PADDED_ANCILLARY"
        )
        for f in findings
    )
    benchmark_inflation_count = sum(
        1 for f in findings
        if f.check_id in ("TOTAL_ABOVE_DIAGNOSIS_BENCHMARK", "LINE_ITEM_PRICE_ABOVE_BENCHMARK", "UNBUNDLED_OR_PADDED_ANCILLARY")
    )
    has_high_inflation = (
        any(
            f.severity in (Severity.HIGH, Severity.CRITICAL) and f.check_id in (
                "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
                "LINE_ITEM_PRICE_ABOVE_BENCHMARK",
                "UNBUNDLED_OR_PADDED_ANCILLARY"
            )
            for f in findings
        ) or benchmark_inflation_count >= 2
    )
    has_benchmark_inflation = any(
        f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL) and f.check_id in (
            "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
            "LINE_ITEM_PRICE_ABOVE_BENCHMARK",
            "UNBUNDLED_OR_PADDED_ANCILLARY"
        )
        for f in findings
    )
    has_learned_pattern_match = any(
        f.agent == AgentName.RAG and
        f.check_id in ("matches_known_pattern", "learned_evasion_match") and
        f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        for f in findings
    )
    has_billing_irregularity = any(
        f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL) and f.check_id in (
            "DUPLICATE_LINE_ITEM",
            "ROOM_DAYS_EXCEED_STAY",
            "TAX_RATE_MISMATCH"
        )
        for f in findings
    )

    has_deception_fraud = (
        has_critical_injection or
        has_critical_tampering or
        has_critical_duplicate or
        has_impossible_travel or
        has_critical_arithmetic or
        has_producer_deception or
        any(
            f.severity in (Severity.HIGH, Severity.CRITICAL) and f.check_id in (
                "EXACT_DUPLICATE_BILL",
                "CROSS_INSURER_DUPLICATE_CLAIM",
                "issued_doc_tampered",
                "FONT_INCONSISTENCY_TAMPERING",
                "DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL",
                "IMPOSSIBLE_TRAVEL_VELOCITY",
                "REVERSED_HOSPITALIZATION_DATES",
                "FUTURE_OR_IMPLAUSIBLE_DATE"
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

    if has_deception_fraud:
        risk_score = max(risk_score, 85)
        verdict = Verdict.REJECT
    elif risk_score < 30:
        if has_failed_agent:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 30)
        elif has_learned_pattern_match:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 65)
        elif has_high_inflation:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 45)
        elif has_benchmark_inflation:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 40)
        elif has_billing_irregularity:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 40)
        elif has_high_arithmetic:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 55)
        elif has_medium_arithmetic:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 35)
        elif has_suspicious_producer:
            verdict = Verdict.REVIEW
            risk_score = max(risk_score, 45)
        else:
            verdict = Verdict.APPROVE
    elif risk_score < 70:
        verdict = Verdict.REVIEW
        if has_learned_pattern_match:
            risk_score = max(risk_score, 65)
    else:
        # If the claim is purely a policy clause tariff cap overrun (e.g. room rent cap breach)
        # without deceptive fraud, route to adjuster REVIEW for line-item deduction.
        if has_policy_clause_only:
            verdict = Verdict.REVIEW
            risk_score = min(risk_score, 65)
        elif has_suspicious_producer and not has_producer_corroboration:
            verdict = Verdict.REVIEW
            risk_score = min(risk_score, 65)
        else:
            verdict = Verdict.REJECT

    # Guardrail: two or more high/critical findings cannot end at APPROVE or low REVIEW (< 65)
    high_or_critical_count = sum(
        1 for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)
    )
    if high_or_critical_count >= 2:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 65)

    # Learned pattern guardrail: active learned evasion match cannot leave claim at APPROVE
    if has_learned_pattern_match:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 65)

    # Inflation guardrail: benchmark inflation findings floor risk score appropriately
    if has_high_inflation:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 45)
    elif has_benchmark_inflation:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 40)
    elif has_billing_irregularity:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 40)

    # Arithmetic discrepancy guardrails (scale with problem severity)
    if has_high_arithmetic:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 55)
    elif has_medium_arithmetic:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 35)

    # Suspicious producer metadata alone guardrail:
    # verdict floor REVIEW, risk score <= 65
    if has_suspicious_producer and not has_producer_corroboration and not has_deception_fraud:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 45)
        risk_score = min(risk_score, 65)

    # Incomplete analysis guardrail:
    # If any unreadable document, extraction incomplete, hidden-text unavailable,
    # non-medical document, or agent failure/timeout condition exists, the verdict CANNOT be APPROVE —
    # the floor is REVIEW (with risk score reflecting unanalysed risk, minimum 45).
    if has_incomplete_condition:
        if verdict == Verdict.APPROVE:
            verdict = Verdict.REVIEW
        risk_score = max(risk_score, 45)

    return risk_score, verdict

