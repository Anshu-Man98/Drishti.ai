"""
Synthesizer Agent for FinShield.
Aggregates specialist findings, calculates risk score and verdict deterministically,
and generates an adjuster-ready executive summary referencing finding IDs.
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime
from google.adk.agents import LlmAgent

from backend.app.schemas import Dossier, Finding, Verdict, Claim
from backend.app.config import settings
from backend.tools.scoring import score_findings

SYNTHESIZER_SYSTEM_PROMPT = """You write the final risk dossier for an insurance adjuster. Use only the findings provided.
Do not add new accusations. Call score_findings for the score. Be specific, neutral, and concise."""


def synthesize_dossier(claim: Claim, all_findings: List[Finding]) -> Dossier:
    """
    Synthesizes all specialist agent findings into a final Dossier.
    Deterministic score and verdict via score_findings.
    """
    risk_score, verdict = score_findings(all_findings)

    # Generate grounded summary referencing finding_ids
    if not all_findings:
        summary = (
            f"Audit completed for Claim {claim.claim_id} (₹{claim.total_claimed:,.2f}) at {claim.provider.name}. "
            "Forensic metadata, mathematical reconciliation, policy cap checks, and claims warehouse cross-referencing "
            "revealed no irregularities or duplicate submissions. Recommended for automated approval."
        )
    else:
        critical_or_high = [f for f in all_findings if f.severity in ["critical", "high"]]
        finding_refs = ", ".join(f"[{f.finding_id}: {f.title}]" for f in all_findings[:4])
        
        summary = (
            f"Audit completed for Claim {claim.claim_id} with risk score {risk_score}/100 ({verdict.value.upper()}). "
            f"The multi-agent pipeline identified {len(all_findings)} anomaly flags: {finding_refs}. "
        )
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

    return Dossier(
        claim_id=claim.claim_id,
        risk_score=risk_score,
        ml_score=None,  # Populated in F3
        verdict=verdict,
        summary=summary,
        findings=all_findings,
        top_ml_features=None,
        timeline=None,
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
