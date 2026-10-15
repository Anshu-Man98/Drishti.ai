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
from backend.agents.synthesizer import create_synthesizer_agent, synthesize_dossier


def build_adk_pipeline() -> SequentialAgent:
    """
    Constructs the canonical ADK agent hierarchy.
    """
    forensics = create_forensics_agent()
    policy = create_policy_agent()
    crossref = create_crossref_agent()

    specialists = ParallelAgent(
        name="specialist_investigators",
        sub_agents=[forensics, policy, crossref]
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

    # 2. Synthesizer Agent
    if status_callback:
        status_callback("synthesizer", "running")
    dossier = synthesize_dossier(claim, all_findings)
    if status_callback:
        status_callback("synthesizer", "done")

    return dossier
