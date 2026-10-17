"""
Synthesizer Agent for FinShield.
Aggregates specialist findings, calculates risk score and verdict deterministically,
and generates an adjuster-ready executive summary referencing finding IDs.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from google.adk.agents import LlmAgent

from backend.app.schemas import Dossier, Finding, Verdict, Claim, TimelineEvent, AgentName, Severity, RetrievedContext, Provenance
from backend.app.config import settings
from backend.tools.registry import call_tool, get_all_computed_values, score_findings
from backend.tools.grounding import assert_numbers_grounded, sanitize_text_grounding

SYNTHESIZER_SYSTEM_PROMPT = """You write the final risk dossier for an insurance adjuster. Use only the findings provided.
Do not add new accusations. Call score_findings for the score. Be specific, neutral, and concise."""


def synthesize_dossier(
    claim: Claim,
    all_findings: List[Finding],
    ml_score: Optional[float] = None,
    top_ml_features: Optional[List[Any]] = None,
    timeline: Optional[List[TimelineEvent]] = None,
    retrieved_context: Optional[List[RetrievedContext]] = None,
    provenance: Optional[Provenance] = None,
    baseline_ml_score: Optional[float] = None
) -> Dossier:
    """
    Synthesizes all specialist agent findings and BigQuery ML probability into a final Dossier.
    Deterministic score and verdict via score_findings.
    Enforces Numeric Grounding Guard on summary and finding explanations.
    """
    score_res = call_tool(
        "score_findings",
        {"findings": all_findings, "ml_probability": ml_score},
        claim_id=claim.claim_id,
        agent_name="synthesizer"
    )
    risk_score = score_res["score"]
    verdict = score_res["verdict"]

    # Generate grounded summary referencing finding_ids and ML features
    if not all_findings:
        summary = (
            f"Audit completed for Claim {claim.claim_id} (₹{claim.total_claimed:,.2f}) at {claim.provider.name}. "
            "Forensic metadata, mathematical reconciliation, policy cap checks, and claims warehouse cross-referencing "
            "revealed no irregularities or duplicate submissions."
        )
        if ml_score is not None:
            summary += f" BigQuery ML model predicts low fraud probability ({(ml_score*100):.1f}%). Recommended for automated approval."
        else:
            summary += " Recommended for automated approval."
    else:
        critical_or_high = [f for f in all_findings if f.severity in ["critical", "high"]]
        finding_refs = ", ".join(f"[{f.finding_id}: {f.title}]" for f in all_findings[:4])
        
        summary = (
            f"Audit completed for Claim {claim.claim_id} with combined risk score {risk_score}/100 ({verdict.value.upper()}). "
            f"The multi-agent pipeline identified {len(all_findings)} anomaly flags: {finding_refs}. "
        )
        
        # ML Explanation sentence (F3 requirement)
        if ml_score is not None and top_ml_features:
            ml_pct = ml_score * 100
            top_exps = []
            room_cap_finding = next(
                (f for f in all_findings if f.check_id in ("POLICY_ROOM_RENT_CAP_EXCEEDED", "ROOM_RENT_CAP_EXCEEDED", "POLICY_ICU_CAP_EXCEEDED")),
                None
            )
            for feat_item in top_ml_features[:3]:
                fname = feat_item.feature if hasattr(feat_item, "feature") else feat_item.get("feature", "")
                attr = feat_item.attribution if hasattr(feat_item, "attribution") else feat_item.get("attribution", 0.0)
                if fname == "amount_vs_diagnosis_median_ratio":
                    if attr > 0:
                        top_exps.append(f"elevated amount vs diagnosis median ratio (impact: {attr:+.2f})")
                    else:
                        top_exps.append(f"claim amount aligned with diagnosis benchmark (impact: {attr:+.2f})")
                elif fname == "room_rent_vs_cap_ratio":
                    if room_cap_finding:
                        top_exps.append(f"room rent rate exceeds eligible policy ceiling (impact: {attr:+.2f})")
                    elif attr > 0:
                        top_exps.append(f"elevated room rent ratio (impact: {attr:+.2f})")
                    else:
                        top_exps.append(f"room rent rate is within eligible policy ceiling (reassuring factor: {attr:+.2f})")
                elif fname == "doctor_distinct_cities_24h":
                    if attr > 0:
                        top_exps.append(f"attending doctor active across multiple distinct cities (impact: {attr:+.2f})")
                    else:
                        top_exps.append(f"doctor city presence normal (impact: {attr:+.2f})")
                elif fname == "claimant_prior_claims_90d":
                    if attr > 0:
                        top_exps.append(f"elevated claimant prior claim frequency (impact: {attr:+.2f})")
                    else:
                        top_exps.append(f"claimant claim frequency normal (impact: {attr:+.2f})")
                elif fname == "shared_bank_account_count":
                    if attr > 0:
                        top_exps.append(f"settlement bank account is shared across multiple claimants (impact: {attr:+.2f})")
                    else:
                        top_exps.append(f"bank account unshared (impact: {attr:+.2f})")
                else:
                    clean_name = fname.replace("_24h", "").replace("_90d", "").replace("_", " ")
                    top_exps.append(f"{clean_name} (impact: {attr:+.2f})")
            
            summary += f"BigQuery ML predicts {ml_pct:.1f}% fraud probability, driven by: {'; '.join(top_exps)}. "

        # Spacetime impossible travel check
        geo_f = next((f for f in all_findings if f.agent == AgentName.SPACETIME), None)
        if geo_f:
            summary += f" CRITICAL GEOSPATIAL ALERT: {geo_f.explanation} "

        if verdict == Verdict.REJECT:
            summary += (
                f"Severe integrity violations were detected ({len(critical_or_high)} critical/high flags). "
                "Immediate claim rejection and referral to Special Investigation Unit (SIU) recommended."
            )
        elif verdict == Verdict.REVIEW:
            has_policy_finding = any(f.agent == AgentName.POLICY for f in all_findings)
            has_math_finding = any(
                f.check_id in ("SUBTOTAL_SUM_MISMATCH", "TOTAL_PAYABLE_MISMATCH", "LINE_ITEM_ARITHMETIC_MISMATCH")
                for f in all_findings
            )
            if has_policy_finding and has_math_finding:
                summary += "Policy ceiling limits and calculation variances require manual adjuster verification prior to settlement."
            elif has_policy_finding:
                summary += "Policy ceiling limits require manual adjuster verification prior to settlement."
            elif has_math_finding:
                summary += "Calculation variances require manual adjuster verification prior to settlement."
            else:
                summary += "Specialist review is required prior to settlement based on the flagged anomalies."
        else:
            summary += "Minor observations noted; overall claim within acceptable risk thresholds."

        # Provenance Tampering or Stripping Alert (Feature A2)
        if provenance and provenance.status == "tampered":
            summary += f" CRITICAL PROVENANCE ALERT: {provenance.detail} "
        elif provenance and provenance.status == "unmarked":
            summary += f" PROVENANCE WARNING: {provenance.detail} "

        # RAG Pattern Corroboration (Feature A4)
        if retrieved_context:
            pat = next((rc for rc in retrieved_context if rc.source == "pattern"), None)
            if pat:
                summary += f" Corroborating context: consistent with known historical fraud pattern [{pat.ref_id}: {pat.title}]."

    # Enforce Numeric Grounding Guard on Summary and Finding Explanations
    from backend.tools.registry import CLAIM_COMPUTED_STORE
    computed_store = dict(get_all_computed_values(claim.claim_id))
    for f in all_findings:
        if getattr(f, "computed_details", None) and isinstance(f.computed_details, dict):
            computed_store.update(f.computed_details)
    if ml_score is not None:
        computed_store["ml_probability"] = float(ml_score)
        computed_store["ml_percentage"] = round(float(ml_score) * 100, 1)
        computed_store["ml_percentage_int"] = round(float(ml_score) * 100)
    if top_ml_features:
        for idx, feat in enumerate(top_ml_features):
            attr_val = feat.attribution if hasattr(feat, "attribution") else feat.get("attribution", 0.0)
            computed_store[f"ml_attr_{idx}"] = float(attr_val)
    CLAIM_COMPUTED_STORE.setdefault(claim.claim_id, {}).update(computed_store)

    sanitized_summary, ungrounded_summary = sanitize_text_grounding(summary, computed_store, claim)
    summary = sanitized_summary
    for ung in ungrounded_summary:
        all_findings.append(Finding(
            finding_id=f"F-UNGROUNDED-SUM-{len(all_findings)+1}",
            agent=AgentName.ML,
            check_id="ungrounded_number",
            severity=Severity.INFO,
            title="Ungrounded numerical claim suppressed",
            explanation=f"Suppressed sentence containing ungrounded numerical value '{ung['value']}' not traceable to deterministic tool outputs.",
            evidence=[],
            confidence=1.0
        ))

    for f in list(all_findings):
        finding_store = dict(computed_store)
        if getattr(f, "computed_details", None) and isinstance(f.computed_details, dict):
            finding_store.update(f.computed_details)
        sanitized_exp, ungrounded_f = sanitize_text_grounding(f.explanation, finding_store, claim)
        if ungrounded_f:
            f.explanation = sanitized_exp
            for ung in ungrounded_f:
                all_findings.append(Finding(
                    finding_id=f"F-UNGROUNDED-F-{len(all_findings)+1}",
                    agent=AgentName.ML,
                    check_id="ungrounded_number",
                    severity=Severity.INFO,
                    title="Ungrounded numerical claim suppressed in finding",
                    explanation=f"Suppressed ungrounded numerical value '{ung['value']}' in finding {f.finding_id}.",
                    evidence=[],
                    confidence=1.0
                ))

    from backend.tools.scoring import is_incomplete_analysis_condition
    is_incomplete = any(
        is_incomplete_analysis_condition(f)
        for f in all_findings
    )
    dossier_status = "incomplete" if is_incomplete else "complete"
    if is_incomplete and verdict == Verdict.APPROVE:
        verdict = Verdict.REVIEW
        risk_score = max(risk_score, 45)

    return Dossier(
        claim_id=claim.claim_id,
        risk_score=risk_score,
        ml_score=ml_score,
        baseline_ml_score=baseline_ml_score,
        verdict=verdict,
        status=dossier_status,
        summary=summary,
        findings=all_findings,
        top_ml_features=top_ml_features,
        timeline=timeline,
        retrieved_context=retrieved_context,
        provenance=provenance,
        created_at=datetime.utcnow()
    )


def create_synthesizer_agent() -> LlmAgent:
    return LlmAgent(
        name="synthesizer_agent",
        instruction=SYNTHESIZER_SYSTEM_PROMPT,
        model=settings.GEMINI_PRO_MODEL,
        tools=[score_findings],
        output_schema=Dossier,
        output_key="final_dossier"
    )
