"""
Cross-Reference Agent for FinShield.
Queries the claims warehouse (BigQuery) for duplicate bills, cross-insurer duplicates,
and shared bank account fraud rings.
"""

from typing import List, Dict, Any
from pydantic import BaseModel
from google.adk.agents import LlmAgent

from backend.app.schemas import Finding, Claim, AgentName, Severity, Evidence
from backend.app.config import settings
from backend.tools.bq import bq_warehouse

CROSSREF_SYSTEM_PROMPT = """You are a fraud investigator with access to the claims warehouse. Run every lookup. Report matches
with the matching claim_ids as evidence. Don't speculate beyond query results. JSON only."""


class CrossRefOutput(BaseModel):
    findings: List[Finding]


import io
import re
import logging
import pdfplumber
from backend.app.services.storage import storage_service

logger = logging.getLogger("finshield.agents.crossref")


def analyze_cross_references(claim: Claim) -> List[Finding]:
    """
    Deterministic specialist runner for Cross-Reference warehouse lookups.
    """
    findings: List[Finding] = []
    sha256 = claim.documents[0].sha256 if claim.documents else "dummy_sha"
    bill_no = None

    # Extract invoice / bill number from document text if available
    if claim.documents:
        doc = claim.documents[0]
        try:
            doc_bytes = storage_service.read_file(doc.gcs_uri)
        except Exception as e:
            findings.append(Finding(
                finding_id=f"F-ERR-CROSSREF-{len(findings)+1}",
                agent=AgentName.CROSSREF,
                check_id="AGENT_FAILED:crossref",
                severity=Severity.HIGH,
                title=f"Cross-reference specialist could not read document {doc.doc_id}",
                explanation=f"Storage read failed for document {doc.doc_id} at {doc.gcs_uri}: {e}. Dossier marked incomplete.",
                evidence=[Evidence(doc_id=doc.doc_id, page=1, quote=str(e)[:120])],
                confidence=1.0,
                computed_chip="Read Error",
                computed_details={"error": str(e), "gcs_uri": doc.gcs_uri}
            ))
            doc_bytes = None

        if doc_bytes:
            if doc_bytes.startswith(b"%PDF"):
                try:
                    with pdfplumber.open(io.BytesIO(doc_bytes)) as pdf:
                        page_text = pdf.pages[0].extract_text() or ""
                        m = re.search(r"Bill\s*(?:No|Number)?[:\s]+([A-Za-z0-9\-]+)", page_text)
                        if m:
                            bill_no = m.group(1).strip()
                except Exception as e:
                    logger.debug("Failed to extract bill_no from PDF text for doc %s: %s", doc.doc_id, e)
            else:
                bill_no = (claim.metadata or {}).get("bill_no")

    # 1. Exact Duplicate Search
    exact_matches = bq_warehouse.find_exact_duplicates(
        sha256=sha256,
        bill_number=bill_no or (claim.documents[0].filename if claim.documents else None),
        hospital_id=claim.provider.hospital_id if claim.provider else "HOSP-UNKNOWN",
        current_claim_id=claim.claim_id
    )
    findings.extend(exact_matches)

    # 2. Cross-Insurer Duplicate Search
    if claim.claimant and claim.admission_ts:
        cross_matches = bq_warehouse.find_cross_insurer_duplicates(
            claimant_id=claim.claimant.claimant_id,
            admission_ts=claim.admission_ts,
            amount=claim.total_claimed or 0.0,
            current_claim_id=claim.claim_id,
            insurer_id=claim.insurer_id or "INS-UNKNOWN"
        )
        findings.extend(cross_matches)

    # 3. Shared Bank Account Ring Search
    if claim.claimant and claim.claimant.bank_account_hash:
        ring_findings = bq_warehouse.shared_account_check(
            bank_account_hash=claim.claimant.bank_account_hash,
            current_claimant_id=claim.claimant.claimant_id
        )
        findings.extend(ring_findings)

    return findings


def create_crossref_agent() -> LlmAgent:
    return LlmAgent(
        name="crossref_agent",
        instruction=CROSSREF_SYSTEM_PROMPT,
        model=settings.GEMINI_FLASH_MODEL,
        tools=[
            bq_warehouse.find_exact_duplicates,
            bq_warehouse.find_cross_insurer_duplicates,
            bq_warehouse.shared_account_check,
            bq_warehouse.claimant_history
        ],
        output_schema=CrossRefOutput,
        output_key="crossref_findings"
    )
