"""
Forensics Agent for FinShield.
Inspects document authenticity using metadata, typography/font consistency,
Error Level Analysis, and Gemini visual inspection.
"""

from typing import List, Dict, Any
from pydantic import BaseModel
from google.adk.agents import LlmAgent

from backend.app.schemas import Finding, Claim, AgentName, Severity, Evidence
from backend.app.config import settings
from backend.tools.forensics_tools import (
    pdf_metadata_check, font_consistency_check,
    image_exif_check, error_level_analysis, synthid_check, gemini_visual_review
)
from backend.app.services.storage import storage_service

FORENSICS_SYSTEM_PROMPT = """You are a document forensics examiner for insurance claims. Call every available forensic tool on
every document. Report only what the tool outputs or the page visibly shows. For each anomaly, emit a
Finding with check_id, severity, a one-sentence plain-English explanation, and evidence with doc_id,
page and bbox. If tools find nothing, return an empty list. Never guess. Output JSON only."""


class ForensicsOutput(BaseModel):
    findings: List[Finding]


def analyze_document_forensics(claim: Claim) -> List[Finding]:
    """
    Deterministic specialist runner for Forensics checks.
    """
    findings: List[Finding] = []

    for doc in claim.documents:
        try:
            doc_bytes = storage_service.read_file(doc.gcs_uri)
        except Exception as e:
            findings.append(Finding(
                finding_id=f"F-ERR-FORENSICS-{len(findings)+1}",
                agent=AgentName.FORENSICS,
                check_id="AGENT_FAILED:forensics",
                severity=Severity.HIGH,
                title=f"Forensics specialist could not read document {doc.doc_id}",
                explanation=f"Storage read failed for document {doc.doc_id} at {doc.gcs_uri}: {e}. Dossier marked incomplete.",
                evidence=[Evidence(doc_id=doc.doc_id, page=1, quote=str(e)[:120])],
                confidence=1.0,
                computed_chip="Read Error",
                computed_details={"error": str(e), "gcs_uri": doc.gcs_uri}
            ))
            continue

        # 1. PDF vs Image Forensics Routing
        is_pdf = doc_bytes.startswith(b"%PDF")
        if is_pdf:
            meta_info, meta_findings = pdf_metadata_check(doc_bytes, doc_id=doc.doc_id)
            findings.extend(meta_findings)

            anomalies, font_findings = font_consistency_check(doc_bytes, doc_id=doc.doc_id)
            findings.extend(font_findings)

            synthid_res = synthid_check(doc_bytes)

            if anomalies or meta_findings:
                review_text = gemini_visual_review(doc_bytes, anomalies, claim_id=claim.claim_id)
        else:
            # Raster Image Forensics (PNG, JPEG, etc.)
            exif_res = image_exif_check(doc_bytes)
            is_suspicious, ela_bbox = error_level_analysis(doc_bytes)
            if is_suspicious:
                findings.append(Finding(
                    finding_id=f"F-FOR-ELA-{len(findings)+1}",
                    agent=AgentName.FORENSICS,
                    check_id="ELA_COMPRESSION_ANOMALY",
                    severity=Severity.HIGH,
                    title="Compression variance detected across document image",
                    explanation="Error Level Analysis (ELA) revealed abnormal compression gradients indicative of spliced or edited image content.",
                    evidence=[Evidence(doc_id=doc.doc_id, page=1, bbox=ela_bbox or [0.1, 0.4, 0.9, 0.6])],
                    confidence=0.88
                ))
            synthid_res = synthid_check(doc_bytes)

    return findings


def create_forensics_agent() -> LlmAgent:
    return LlmAgent(
        name="forensics_agent",
        instruction=FORENSICS_SYSTEM_PROMPT,
        model=settings.GEMINI_FLASH_MODEL,
        tools=[
            pdf_metadata_check,
            font_consistency_check,
            image_exif_check,
            error_level_analysis,
            synthid_check,
            gemini_visual_review
        ],
        output_schema=ForensicsOutput,
        output_key="forensics_findings"
    )

