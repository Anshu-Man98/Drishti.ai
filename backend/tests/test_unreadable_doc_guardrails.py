import pytest
from backend.app.schemas import Finding, Severity, Verdict, AgentName, Claim, Claimant, Provider
from backend.tools.scoring import score_findings, is_incomplete_analysis_condition
from backend.agents.synthesizer import synthesize_dossier


def test_is_incomplete_analysis_condition():
    # 1. Unreadable / blurred / cropped / low-DPI / OCR confidence
    f1 = Finding(
        finding_id="F1",
        agent=AgentName.FORENSICS,
        check_id="document_unreadable_manual_review",
        severity=Severity.HIGH,
        title="Document Unreadable / Manual Review Required",
        explanation="Document text blurred and unreadable",
        evidence=[],
        confidence=0.9
    )
    assert is_incomplete_analysis_condition(f1) is True

    f1_crop = Finding(
        finding_id="F1b",
        agent=AgentName.FORENSICS,
        check_id="document_cropped",
        severity=Severity.MEDIUM,
        title="Cropped Document Image",
        explanation="Bill cropped at margins",
        evidence=[],
        confidence=0.9
    )
    assert is_incomplete_analysis_condition(f1_crop) is True

    f1_ocr = Finding(
        finding_id="F1c",
        agent=AgentName.FORENSICS,
        check_id="low_ocr_confidence",
        severity=Severity.MEDIUM,
        title="OCR Confidence Below Threshold",
        explanation="Document AI confidence 0.42 below 0.70 threshold",
        evidence=[],
        confidence=0.9
    )
    assert is_incomplete_analysis_condition(f1_ocr) is True

    # 2. Extraction incomplete / missing mandatory fields
    f2 = Finding(
        finding_id="F2",
        agent=AgentName.FORENSICS,
        check_id="EXTRACTION_INCOMPLETE",
        severity=Severity.HIGH,
        title="Extraction Incomplete",
        explanation="Missing mandatory hospital and diagnosis fields",
        evidence=[],
        confidence=0.9
    )
    assert is_incomplete_analysis_condition(f2) is True

    f2_missing = Finding(
        finding_id="F2b",
        agent=AgentName.FORENSICS,
        check_id="missing_mandatory_field",
        severity=Severity.HIGH,
        title="Missing Mandatory Claim Fields",
        explanation="Total claimed amount could not be extracted",
        evidence=[],
        confidence=0.9
    )
    assert is_incomplete_analysis_condition(f2_missing) is True

    # 3. Hidden-text classification could not run
    f3 = Finding(
        finding_id="F3",
        agent=AgentName.INJECTION,
        check_id="hidden_text_classification_unavailable",
        severity=Severity.MEDIUM,
        title="Hidden Text Classification Unavailable",
        explanation="Classification model service timed out",
        evidence=[],
        confidence=0.9
    )
    assert is_incomplete_analysis_condition(f3) is True

    # 4. Agent failed or timed out
    f4 = Finding(
        finding_id="F4",
        agent=AgentName.FORENSICS,
        check_id="AGENT_FAILED:forensics",
        severity=Severity.INFO,
        title="Agent Failed: forensics",
        explanation="Forensics agent encountered unexpected exception",
        evidence=[],
        confidence=1.0
    )
    assert is_incomplete_analysis_condition(f4) is True

    f4_timeout = Finding(
        finding_id="F4b",
        agent=AgentName.SPACETIME,
        check_id="AGENT_TIMEOUT:spacetime",
        severity=Severity.INFO,
        title="Agent Timed Out: spacetime",
        explanation="Spacetime agent exceeded execution deadline",
        evidence=[],
        confidence=1.0
    )
    assert is_incomplete_analysis_condition(f4_timeout) is True


@pytest.mark.parametrize("condition_check_id,condition_title,severity", [
    ("document_unreadable_manual_review", "Document Unreadable / Manual Review Required", Severity.HIGH),
    ("document_blurred", "Document Blurred / Out of Focus", Severity.MEDIUM),
    ("document_cropped", "Document Cropped / Incomplete Scan", Severity.MEDIUM),
    ("low_dpi_document", "Low-DPI Document Image (100 DPI)", Severity.MEDIUM),
    ("low_ocr_confidence", "OCR Confidence Below Threshold (0.45)", Severity.MEDIUM),
    ("EXTRACTION_INCOMPLETE", "Extraction Incomplete / Missing Fields", Severity.HIGH),
    ("missing_mandatory_fields", "Missing Mandatory Claim Fields", Severity.HIGH),
    ("hidden_text_classification_unavailable", "Hidden Text Classification Unavailable", Severity.MEDIUM),
    ("AGENT_FAILED:forensics", "Agent Failed: forensics", Severity.INFO),
    ("AGENT_TIMEOUT:crossref", "Agent Timed Out: crossref", Severity.INFO),
    ("BQML_SERVICE_FAILURE", "BigQuery ML Service Unavailable", Severity.INFO),
])
def test_each_incomplete_condition_individually_caps_at_review(condition_check_id, condition_title, severity):
    """
    Each condition individually MUST cap the verdict at REVIEW (or REJECT), NEVER APPROVE,
    even with 0.0 ML probability and zero other findings.
    """
    finding = Finding(
        finding_id="F-TEST",
        agent=AgentName.FORENSICS,
        check_id=condition_check_id,
        severity=severity,
        title=condition_title,
        explanation="Test condition for incomplete analysis guardrail",
        evidence=[],
        confidence=0.95
    )

    score, verdict = score_findings([finding], ml_probability=0.0)
    assert verdict != Verdict.APPROVE, f"{condition_check_id} must never end in APPROVE"
    assert verdict == Verdict.REVIEW, f"{condition_check_id} floor must be REVIEW"
    assert score >= 45, f"Risk score must reflect unanalysed risk (>= 45), got {score}"


def test_incomplete_with_deceptive_fraud_retains_reject():
    """If a claim is incomplete but also contains confirmed fraud, verdict stays REJECT."""
    unreadable_f = Finding(
        finding_id="F1",
        agent=AgentName.FORENSICS,
        check_id="document_unreadable_manual_review",
        severity=Severity.HIGH,
        title="Document Unreadable",
        explanation="Cannot read document",
        evidence=[],
        confidence=0.9
    )
    tamper_f = Finding(
        finding_id="F2",
        agent=AgentName.PROVENANCE,
        check_id="issued_doc_tampered",
        severity=Severity.CRITICAL,
        title="Document Tampering Detected",
        explanation="Cryptographic signature mismatch on altered hospital bill",
        evidence=[],
        confidence=1.0
    )

    score, verdict = score_findings([unreadable_f, tamper_f], ml_probability=0.2)
    assert verdict == Verdict.REJECT
    assert score >= 85


def test_synthesizer_marks_incomplete_dossier_status():
    """Verify synthesizer creates dossier with status='incomplete' and verdict=REVIEW."""
    claim = Claim(
        claim_id="CLM-TEST-UNREADABLE-01",
        policy_id="POL-CARE-001",
        insurer_id="INS-CARE",
        claimant=Claimant(claimant_id="CLMNT-1", name="Test Claimant", phone="+91-9999999999", bank_account_hash="bankhash001"),
        provider=Provider(hospital_id="HOSP-1", name="Apollo Hospital", city="Mumbai"),
        admission_ts="2026-07-20T10:00:00",
        discharge_ts="2026-07-22T10:00:00",
        diagnosis_code="A09.9",
        total_claimed=50000.0,
        subtotal=50000.0,
        tax=0.0,
        line_items=[],
        documents=[]
    )

    unreadable_f = Finding(
        finding_id="F1",
        agent=AgentName.FORENSICS,
        check_id="document_unreadable_manual_review",
        severity=Severity.HIGH,
        title="Document Unreadable / Manual Review Required",
        explanation="Text extraction failed",
        evidence=[],
        confidence=0.95
    )

    dossier = synthesize_dossier(
        claim=claim,
        all_findings=[unreadable_f],
        ml_score=0.10,
        top_ml_features=[],
        timeline=[],
        retrieved_context=None,
        provenance=None
    )

    assert dossier.status == "incomplete"
    assert dossier.verdict == Verdict.REVIEW
    assert dossier.risk_score >= 45
