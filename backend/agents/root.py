"""
FinShield Multi-Agent Claims Fraud Pipeline (ADK Orchestrator).
Root Architecture:
SequentialAgent[
  ParallelAgent[ForensicsAgent, PolicyAgent, CrossRefAgent],
  SynthesizerAgent
]
"""

from typing import List, Dict, Any, Callable, Optional
from google.adk.agents import SequentialAgent, ParallelAgent
from google.adk.sessions import InMemorySessionService
from google.adk import Runner

from backend.app.schemas import Claim, Dossier, Finding
from backend.agents.forensics import create_forensics_agent, analyze_document_forensics
from backend.agents.policy import create_policy_agent, analyze_policy_and_arithmetic
from backend.agents.crossref import create_crossref_agent, analyze_cross_references
from backend.agents.spacetime import create_spacetime_agent, analyze_spacetime_feasibility
from backend.agents.synthesizer import create_synthesizer_agent, synthesize_dossier


def build_adk_pipeline() -> SequentialAgent:
    """
    Constructs the canonical ADK agent hierarchy.
    """
    forensics = create_forensics_agent()
    policy = create_policy_agent()
    crossref = create_crossref_agent()
    spacetime = create_spacetime_agent()

    specialists = ParallelAgent(
        name="specialist_investigators",
        sub_agents=[forensics, policy, crossref, spacetime]
    )

    synthesizer = create_synthesizer_agent()

    root_pipeline = SequentialAgent(
        name="finshield_pipeline",
        sub_agents=[specialists, synthesizer]
    )
    return root_pipeline


def run_claims_fraud_pipeline(
    claim: Claim,
    status_callback: Optional[Callable[[str, str], None]] = None
) -> Dossier:
    """
    Executes the 4-agent fraud scrutiny pipeline on a given claim.
    Emits progress for Forensics, Policy, CrossRef, and Synthesizer agents.
    """
    all_findings: List[Finding] = []

    # 1. Parallel Specialist Agents
    # Forensics Agent
    if status_callback:
        status_callback("forensics", "running")
    forensics_findings = analyze_document_forensics(claim)
    all_findings.extend(forensics_findings)
    if status_callback:
        status_callback("forensics", "done")

    # Policy & Arithmetic Agent
    if status_callback:
        status_callback("policy", "running")
    policy_findings = analyze_policy_and_arithmetic(claim)
    all_findings.extend(policy_findings)
    if status_callback:
        status_callback("policy", "done")

    # Cross-Reference Agent
    if status_callback:
        status_callback("crossref", "running")
    crossref_findings = analyze_cross_references(claim)
    all_findings.extend(crossref_findings)
    if status_callback:
        status_callback("crossref", "done")

    # Spacetime Feasibility Agent
    if status_callback:
        status_callback("spacetime", "running")
    spacetime_findings, timeline = analyze_spacetime_feasibility(claim)
    all_findings.extend(spacetime_findings)
    if status_callback:
        status_callback("spacetime", "done")

    # 2. BigQuery ML Scoring Step
    if status_callback:
        status_callback("ml", "running")
    from backend.tools.bq import extract_claim_features, ml_score
    from backend.app.schemas import MlFeature, AgentName, Severity

    claim_features = extract_claim_features(claim)
    ml_prob, top_ml_features_dicts = ml_score(claim_features)

    top_ml_features = [
        MlFeature(feature=it["feature"], attribution=it["attribution"])
        for it in top_ml_features_dicts
    ]

    # Add an agent="ml" Finding when probability > 0.6 (F3 Requirement 3)
    if ml_prob > 0.6:
        feat_summaries = []
        for f in top_ml_features[:3]:
            feat_summaries.append(f"{f.feature.replace('_', ' ')} (impact: {f.attribution:+.2f})")

        all_findings.append(Finding(
            finding_id="F-ML-PREDICT-ELEVATED",
            agent=AgentName.ML,
            check_id="BQML_HIGH_RISK_ANOMALY",
            severity=Severity.HIGH if ml_prob < 0.85 else Severity.CRITICAL,
            title=f"BigQuery ML predicts elevated fraud probability ({(ml_prob*100):.1f}%)",
            explanation=(
                f"Boosted tree classifier predicts elevated fraud probability of {(ml_prob*100):.1f}%. "
                f"Primary anomaly drivers: {', '.join(feat_summaries)}."
            ),
            evidence=[],
            confidence=round(ml_prob, 2)
        ))

    if status_callback:
        status_callback("ml", "done")

    # 3. Synthesizer Agent
    if status_callback:
        status_callback("synthesizer", "running")
    dossier = synthesize_dossier(
        claim=claim,
        all_findings=all_findings,
        ml_score=ml_prob,
        top_ml_features=top_ml_features,
        timeline=timeline
    )
    if status_callback:
        status_callback("synthesizer", "done")

    return dossier
