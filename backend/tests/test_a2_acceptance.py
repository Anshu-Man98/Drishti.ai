"""
Acceptance test suite for Feature A2: Tamper-Evident Document Provenance.

Validates:
1. Issue path + genuine verification: sign_and_mark issues approval letter for ₹50,000;
   verify_document returns status='verified' with valid Ed25519 signature and matching semantic hash.
2. Tamper detection: Altering the presented amount on rendered page from ₹50,000 to ₹5,00,000
   is detected with status='tampered', identifying field 'sanctioned_amount', issued: 5000000, presented: 50000000.
3. Dual-carrier redundancy: Stripping XMP metadata allows successful recovery and verification
   via Carrier 2 (LSB letterhead steganography with 3x error correction).
4. Third-party document handling: A hospital bill (G1) returns status='not_applicable' with ZERO findings.
5. Unmarked expected document: A document purporting to be a FinShield sanction order without watermark
   returns status='unmarked' and emits a HIGH severity finding.
6. Golden claim G8: End-to-end pipeline run produces a CRITICAL finding (issued_doc_tampered)
   and overall verdict REJECT.
7. Zero A1 false positives: Watermarked document produces 0 hidden text prompt injection findings.
8. Kill-switch: Setting WATERMARK_ENABLED=False cleanly short-circuits.
9. API endpoints: /provenance/pubkey, /provenance/verify, and /claims/{id}/issue-approval function correctly.
"""

import io
from pathlib import Path
import pypdf
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.schemas import Claim, Claimant, Provider, AgentName, Severity, Verdict
from backend.services.provenance import (
    sign_and_mark,
    verify_document,
    get_verifying_key,
    get_signing_key,
    PUBKEY_PATH
)
from backend.tools.docai import process_document_docai
from backend.tools.injection_tools import detect_hidden_text_injection
from backend.agents.root import run_claims_fraud_pipeline
from backend.app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "data" / "demo"


# ==============================================================================
# 1. ISSUE AND VERIFY GENUINE DOCUMENT
# ==============================================================================

def test_issue_and_verify_genuine():
    """
    Issue approval for ₹50,000 (5,000,000 paise).
    verify_document returns status='verified', carrier='xmp', signature valid, content hash matches.
    """
    fields = {
        "claim_id": "CLM-GENUINE-001",
        "claimant_id": "CLMNT-9901",
        "claimant_name": "Aarav Sharma",
        "amount_paise": 5000000,
        "doc_type": "approval_letter",
        "doc_id": "SANCTION-TEST-GENUINE",
        "policy_id": "POL-AROGYA-001",
        "insurer_id": "INS-FINSHIELD",
        "notes": "Pre-authorization approved under policy terms."
    }
    pdf_bytes, payload = sign_and_mark(fields)
    assert len(pdf_bytes) > 1000
    assert payload["amount_paise"] == 5000000

    res = verify_document(pdf_bytes, claim_id="CLM-GENUINE-001")
    assert res["status"] == "verified", f"Expected verified, got {res}"
    assert res["carrier"] == "xmp"
    assert res["diff"] is None
    assert res["payload"]["amount_paise"] == 5000000


# ==============================================================================
# 2. TAMPER DETECTION (PAGE TEXT ALTERED)
# ==============================================================================

def test_tamper_detection_altered_amount():
    """
    Issue approval for ₹50,000, alter rendered page text to ₹5,00,000.
    verify_document detects status='tampered', reporting exact issued vs presented diff.
    """
    fields = {
        "claim_id": "CLM-TAMPER-002",
        "claimant_id": "CLMNT-9902",
        "claimant_name": "Meera Joshi",
        "amount_paise": 5000000,  # ₹50,000
        "doc_type": "approval_letter",
        "doc_id": "SANCTION-TEST-TAMPER"
    }
    genuine_bytes, _ = sign_and_mark(fields)

    # Tamper the decompressed content stream of the PDF
    reader = pypdf.PdfReader(io.BytesIO(genuine_bytes))
    page = reader.pages[0]
    raw_content = page.get_contents().get_data()
    altered_content = raw_content.replace(b"50,000.00", b"500,000.00").replace(b"5,000,000", b"50,000,000")
    stream = pypdf.generic.DecodedStreamObject()
    stream.set_data(altered_content)
    page[pypdf.generic.NameObject("/Contents")] = stream

    writer = pypdf.PdfWriter()
    writer.add_page(page)
    writer.add_metadata(reader.metadata)
    buf = io.BytesIO()
    writer.write(buf)
    tampered_bytes = buf.getvalue()

    res = verify_document(tampered_bytes, claim_id="CLM-TAMPER-002")
    assert res["status"] == "tampered", f"Expected tampered, got {res}"
    assert res["diff"] is not None
    assert res["diff"]["field"] == "sanctioned_amount"
    assert res["diff"]["issued"] == 5000000
    assert res["diff"]["presented"] == 50000000
    assert "₹50,000.00" in res["diff"]["issued_display"]
    assert "₹500,000.00" in res["diff"]["presented_display"]


# ==============================================================================
# 3. DUAL-CARRIER REDUNDANCY: STRIPPED XMP -> LSB CARRIER RECOVERY
# ==============================================================================

def test_stripped_xmp_fallback_to_lsb():
    """
    Strip XMP metadata completely from the document.
    verify_document successfully recovers the payload via Carrier 2 (LSB Steganography).
    """
    fields = {
        "claim_id": "CLM-LSB-003",
        "claimant_id": "CLMNT-9903",
        "claimant_name": "Kiran Rao",
        "amount_paise": 7500000,
        "doc_type": "approval_letter",
        "doc_id": "SANCTION-TEST-LSB"
    }
    genuine_bytes, _ = sign_and_mark(fields)

    # Strip XMP metadata completely
    reader = pypdf.PdfReader(io.BytesIO(genuine_bytes))
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # Deliberately do NOT add metadata (metadata stripped)

    buf = io.BytesIO()
    writer.write(buf)
    stripped_bytes = buf.getvalue()

    # Verify via LSB carrier
    res = verify_document(stripped_bytes, claim_id="CLM-LSB-003")
    assert res["status"] == "verified", f"Expected verified via LSB, got {res}"
    assert res["carrier"] == "lsb", f"Expected lsb carrier, got {res['carrier']}"
    assert res["payload"]["amount_paise"] == 7500000


def test_stripped_xmp_tampered_document_via_lsb():
    """
    Strip XMP metadata AND alter text on page.
    verify_document recovers signed payload via LSB carrier and flags tampered status.
    """
    fields = {
        "claim_id": "CLM-LSB-TAMPER-004",
        "claimant_id": "CLMNT-9904",
        "claimant_name": "Kiran Rao",
        "amount_paise": 5000000,
        "doc_type": "approval_letter",
        "doc_id": "SANCTION-TEST-LSB-TAMPER"
    }
    genuine_bytes, _ = sign_and_mark(fields)

    reader = pypdf.PdfReader(io.BytesIO(genuine_bytes))
    page = reader.pages[0]
    raw_content = page.get_contents().get_data()
    altered_content = raw_content.replace(b"50,000.00", b"500,000.00").replace(b"5,000,000", b"50,000,000")
    stream = pypdf.generic.DecodedStreamObject()
    stream.set_data(altered_content)
    page[pypdf.generic.NameObject("/Contents")] = stream

    writer = pypdf.PdfWriter()
    writer.add_page(page)
    # Metadata stripped

    buf = io.BytesIO()
    writer.write(buf)
    stripped_tampered_bytes = buf.getvalue()

    res = verify_document(stripped_tampered_bytes, claim_id="CLM-LSB-TAMPER-004")
    assert res["status"] == "tampered", f"Expected tampered via LSB, got {res}"
    assert res["carrier"] == "lsb"
    assert res["diff"]["presented"] == 50000000


# ==============================================================================
# 4. THIRD-PARTY DOCUMENT (HOSPITAL BILL) -> NOT APPLICABLE
# ==============================================================================

def test_third_party_document_not_applicable():
    """
    Hospital bill (G1) is not an issued document and carries no watermark.
    verify_document returns status='not_applicable' with zero findings.
    """
    g1_path = DEMO_DIR / "G1_clean_claim.pdf"
    assert g1_path.exists()
    pdf_bytes = g1_path.read_bytes()

    res = verify_document(pdf_bytes, claim_id="CLM-G1-THIRD-PARTY")
    assert res["status"] == "not_applicable"
    assert res["payload"] is None

    claim, _ = process_document_docai(pdf_bytes, filename="G1_clean_claim.pdf", claim_id="CLM-G1-THIRD-PARTY")
    dossier = run_claims_fraud_pipeline(claim)
    assert dossier.provenance.status == "not_applicable"
    prov_findings = [f for f in dossier.findings if f.agent == AgentName.PROVENANCE]
    assert len(prov_findings) == 0


# ==============================================================================
# 5. UNMARKED EXPECTED SANCTION ORDER
# ==============================================================================

def test_unmarked_expected_sanction_document():
    """
    Document claims to be a FinShield sanction order, but carries no valid mark.
    verify_document returns status='unmarked' and pipeline emits a HIGH severity finding.
    """
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>FINSHIELD CLAIMS SANCTION ORDER</b>", styles["Heading1"]),
        Spacer(1, 10),
        Paragraph("Claim Reference: CLM-FORGERY-999", styles["Normal"]),
        Paragraph("SANCTIONED DISBURSEMENT AMOUNT: INR 1,00,000.00", styles["Normal"]),
    ]
    doc.build(story)
    fake_pdf = buf.getvalue()

    res = verify_document(fake_pdf, claim_id="CLM-FORGERY-999")
    assert res["status"] == "unmarked"

    claim, _ = process_document_docai(fake_pdf, filename="fake_sanction.pdf", claim_id="CLM-FORGERY-999")
    dossier = run_claims_fraud_pipeline(claim)
    assert dossier.provenance.status == "unmarked"
    unmarked_findings = [f for f in dossier.findings if f.check_id == "issued_doc_unmarked_expected"]
    assert len(unmarked_findings) == 1
    assert unmarked_findings[0].severity == Severity.HIGH


# ==============================================================================
# 6. GOLDEN CLAIM G8 PIPELINE REJECTION
# ==============================================================================

def test_g8_golden_claim_tampered_rejection():
    """
    Golden Claim G8 (approval letter altered from ₹50,000 to ₹5,00,000)
    produces a CRITICAL finding (issued_doc_tampered) and overall verdict REJECT.
    """
    g8_path = DEMO_DIR / "G8_altered_approval.pdf"
    assert g8_path.exists(), f"G8 PDF missing at {g8_path}"

    pdf_bytes = g8_path.read_bytes()
    claim, _ = process_document_docai(pdf_bytes, filename="G8_altered_approval.pdf", claim_id="CLM-SANCTION-G8")
    dossier = run_claims_fraud_pipeline(claim)

    assert dossier.verdict == Verdict.REJECT
    assert dossier.risk_score >= 85
    assert dossier.provenance.status == "tampered"
    assert "SANCTION-G8-GENUINE" in dossier.provenance.issued_doc_id

    tampered_findings = [f for f in dossier.findings if f.check_id == "issued_doc_tampered"]
    assert len(tampered_findings) == 1
    f = tampered_findings[0]
    assert f.agent == AgentName.PROVENANCE
    assert f.severity == Severity.CRITICAL
    assert "₹50,000" in f.explanation
    assert "₹500,000" in f.explanation or "50000000" in f.explanation


# ==============================================================================
# 7. WATERMARK ALLOWLIST: ZERO INJECTION FINDINGS
# ==============================================================================

def test_watermarked_document_zero_injection_findings():
    """
    Dual-carrier watermarked approval document is recognized by A1 allowlist
    as benign_metadata, producing ZERO prompt injection findings.
    """
    fields = {
        "claim_id": "CLM-INJ-CHECK-007",
        "claimant_id": "CLMNT-1122",
        "claimant_name": "Priya Nair",
        "amount_paise": 4000000,
        "doc_type": "approval_letter",
        "doc_id": "SANCTION-INJ-CHECK"
    }
    pdf_bytes, _ = sign_and_mark(fields)
    claim, _ = process_document_docai(pdf_bytes, filename="signed_test.pdf", claim_id="CLM-INJ-CHECK-007")

    inj_findings = detect_hidden_text_injection(claim)
    assert len(inj_findings) == 0, f"Expected 0 injection findings, got {inj_findings}"


# ==============================================================================
# 8. KILL-SWITCH TEST
# ==============================================================================

def test_kill_switch_watermark_disabled(monkeypatch):
    """
    When WATERMARK_ENABLED is False, verification and issuing cleanly short-circuit
    and no provenance findings are emitted.
    """
    monkeypatch.setattr(settings, "WATERMARK_ENABLED", False)

    client = TestClient(app)

    # 1. Verify endpoint returns disabled status
    files = {"file": ("dummy.pdf", b"%PDF-1.4 dummy", "application/pdf")}
    r_ver = client.post("/provenance/verify", files=files)
    assert r_ver.status_code == 200
    assert r_ver.json()["status"] == "disabled"

    # 2. Issue endpoint returns 400
    r_iss = client.post("/claims/CLM-DUMMY/issue-approval", json={"amount_paise": 100000})
    assert r_iss.status_code == 400
    assert "disabled" in r_iss.json()["detail"].lower()


# ==============================================================================
# 9. API ENDPOINTS INTEGRATION
# ==============================================================================

def test_provenance_api_endpoints():
    """
    Tests GET /provenance/pubkey, POST /claims/{id}/issue-approval, and POST /provenance/verify.
    """
    client = TestClient(app)

    # 1. Pubkey endpoint
    r_pk = client.get("/provenance/pubkey")
    assert r_pk.status_code == 200
    assert "BEGIN PUBLIC KEY" in r_pk.text

    # 2. Issue approval on an existing claim
    from backend.app.services.db import db_service
    from datetime import datetime
    claim_id = "CLM-API-TEST-99"
    claim = Claim(
        claim_id=claim_id,
        policy_id="POL-TEST-1",
        insurer_id="INS-TEST-1",
        claimant=Claimant(claimant_id="CLMNT-99", name="Test User", phone="+91-9999999999", bank_account_hash="hash99"),
        provider=Provider(hospital_id="H-99", name="City Hospital", city="Delhi", lat=28.5, lng=77.2),
        doctor_id="DOC-99",
        admission_ts=datetime(2026, 3, 1),
        discharge_ts=datetime(2026, 3, 4),
        diagnosis_code="K80.2",
        subtotal=47619.05,
        tax=2380.95,
        total_claimed=50000.0,
        documents=[]
    )
    db_service.save_claim(claim)

    r_issue = client.post(f"/claims/{claim_id}/issue-approval", json={"amount_paise": 5000000, "notes": "Approved."})
    assert r_issue.status_code == 200
    issue_data = r_issue.json()
    assert issue_data["amount_paise"] == 5000000
    assert "download_url" in issue_data

    # Download document
    r_dl = client.get(issue_data["download_url"])
    assert r_dl.status_code == 200

    # 3. Verify genuine document via API
    files = {"file": ("issued_sanction.pdf", r_dl.content, "application/pdf")}
    r_verify = client.post("/provenance/verify", files=files, data={"claim_id": claim_id})
    assert r_verify.status_code == 200
    verify_data = r_verify.json()
    assert verify_data["status"] == "verified"
    assert verify_data["payload"]["amount_paise"] == 5000000
