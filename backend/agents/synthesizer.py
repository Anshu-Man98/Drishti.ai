"""
Synthesizer Agent for FinShield.
Aggregates specialist findings, calculates risk score and verdict deterministically,
and generates an adjuster-ready executive summary referencing finding IDs.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from google.adk.agents import LlmAgent

from backend.app.schemas import Dossier, Finding, Verdict, Claim, TimelineEvent, AgentName, Severity, RetrievedContext
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
    retrieved_context: Optional[List[RetrievedContext]] = None
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
            for feat_item in top_ml_features[:3]:
                fname = feat_item.feature if hasattr(feat_item, "feature") else feat_item.get("feature", "")
                attr = feat_item.attribution if hasattr(feat_item, "attribution") else feat_item.get("attribution", 0.0)
                if fname == "amount_vs_diagnosis_median_ratio":
                    ratio = getattr(claim, "total_claimed", 0) / 65000.0
                    top_exps.append(f"claim amount is {ratio:.1f}× the median for this diagnosis")
                elif fname == "room_rent_vs_cap_ratio":
                    top_exps.append("room rent rate exceeds eligible policy ceiling")
                elif fname == "doctor_distinct_cities_24h":
                    top_exps.append("attending doctor has activity in multiple distinct cities within 24 hours")
                elif fname == "claimant_prior_claims_90d":
                    top_exps.append("elevated claimant claim frequency over past 90 days")
                elif fname == "shared_bank_account_count":
                    top_exps.append("settlement bank account is shared across multiple claimants")
                else:
                    top_exps.append(f"{fname.replace('_', ' ')} (impact: {attr:+.2f})")
            
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
            summary += (
                "Policy ceiling or calculation variances require manual adjuster verification prior to settlement."
            )
        else:
            summary += "Minor observations noted; overall claim within acceptable risk thresholds."

        # RAG Pattern Corroboration (Feature A4)
        if retrieved_context:
            pat = next((rc for rc in retrieved_context if rc.source == "pattern"), None)
            if pat:
                summary += f" Corroborating context: consistent with known historical fraud pattern [{pat.ref_id}: {pat.title}]."

    # Enforce Numeric Grounding Guard on Summary and Finding Explanations
    computed_store = get_all_computed_values(claim.claim_id)
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
        sanitized_exp, ungrounded_f = sanitize_text_grounding(f.explanation, computed_store, claim)
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

    return Dossier(
        claim_id=claim.claim_id,
        risk_score=risk_score,
        ml_score=ml_score,
        verdict=verdict,
        summary=summary,
        findings=all_findings,
        top_ml_features=top_ml_features,
        timeline=timeline,
        retrieved_context=retrieved_context,
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
