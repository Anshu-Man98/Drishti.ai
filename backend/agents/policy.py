"""
Arithmetic & Policy Agent for FinShield.
Audits line item arithmetic, dates, policy caps, and sub-limits.
Calls deterministic tools for all math and policy clause grounding.
"""

from typing import List, Dict, Any
from pydantic import BaseModel
from google.adk.agents import LlmAgent

from backend.app.schemas import Finding, Claim
from backend.app.config import settings
from backend.tools.arithmetic import validate_arithmetic, check_dates
from backend.tools.policy_tools import check_policy_caps, search_policy

POLICY_SYSTEM_PROMPT = """You are a claims auditor. You NEVER compute numbers yourself — always call the tools. For every
violation, cite the policy clause id and text returned by search_policy. Emit Findings in JSON only."""


class PolicyOutput(BaseModel):
    findings: List[Finding]


def analyze_policy_and_arithmetic(claim: Claim) -> List[Finding]:
    """
    Deterministic specialist runner for Arithmetic & Policy verification.
    """
    findings: List[Finding] = []
    doc_id = claim.documents[0].doc_id if claim.documents else "doc_main"

    from backend.tools.docai import locate_field

    # 1. Validate Arithmetic with bounding boxes
    line_items_dict = [it.model_dump() for it in claim.line_items]
    sub_evidence = locate_field(doc_id, "subtotal", claim)
    tot_evidence = locate_field(doc_id, "total_claimed", claim)

    math_findings = validate_arithmetic(
        line_items=line_items_dict,
        subtotal=claim.subtotal,
        tax=claim.tax,
        total=claim.total_claimed,
        doc_id=doc_id,
        subtotal_bbox=sub_evidence.bbox if sub_evidence else None,
        total_bbox=tot_evidence.bbox if tot_evidence else None
    )
    findings.extend(math_findings)

    # 2. Check Dates
    date_findings = check_dates(
        admission_ts=claim.admission_ts,
        discharge_ts=claim.discharge_ts,
        doc_id=doc_id
    )
    findings.extend(date_findings)

    # 3. Check Policy Caps
    claim_dict = claim.model_dump()
    cap_findings = check_policy_caps(
        policy_id=claim.policy_id,
        claim_data=claim_dict,
        doc_id=doc_id
    )
    findings.extend(cap_findings)

    return findings


def create_policy_agent() -> LlmAgent:
    return LlmAgent(
        name="policy_agent",
        instruction=POLICY_SYSTEM_PROMPT,
        model=settings.GEMINI_FLASH_MODEL,
        tools=[
            validate_arithmetic,
            check_dates,
            check_policy_caps,
            search_policy
        ],
        output_schema=PolicyOutput,
        output_key="policy_findings"
    )
