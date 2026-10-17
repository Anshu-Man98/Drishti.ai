"""
Comprehensive F1 acceptance test suite.
Validates:
1. Tool tests: validate_arithmetic, check_policy_caps, pdf_metadata_check, font_consistency_check, score_findings
2. Pipeline tests on Golden Claims:
   - G1 -> approve, no high/critical findings
   - G2 -> arithmetic finding
   - G3 -> policy-cap finding citing clause
   - G4 -> cross-insurer duplicate
   - G6 -> forensics findings (producer + font mismatch + date mismatch)
3. Determinism: Same claim analyzed 3 times yields exact same score and verdict
"""

import json
from pathlib import Path
import pytest
from datetime import datetime

from backend.app.schemas import Claim, LineItem, Provider, Claimant, Document, DocType, Verdict
from backend.tools.registry import validate_arithmetic, check_dates
from backend.tools.policy_tools import check_policy_caps, search_policy
from backend.tools.forensics_tools import pdf_metadata_check, font_consistency_check
from backend.tools.scoring import score_findings
from backend.agents.root import run_claims_fraud_pipeline

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "data" / "demo"


def test_tool_arithmetic_clean_and_mismatched():
    # Clean items
    items = [
        {"description": "Room Rent", "qty": 3, "unit_price": 4000.0, "amount": 12000.0},
        {"description": "Surgery", "qty": 1, "unit_price": 50000.0, "amount": 50000.0}
    ]
    findings = validate_arithmetic(items, subtotal=62000.0, tax=3100.0, total=65100.0)["findings"]
    assert len(findings) == 0, "Clean arithmetic should emit 0 findings"

    # Mismatched total (e.g. G2)
    findings_bad = validate_arithmetic(items, subtotal=62000.0, tax=3100.0, total=85000.0)["findings"]
    assert len(findings_bad) >= 1
    total_finding = next((f for f in findings_bad if f.check_id == "TOTAL_PAYABLE_MISMATCH"), None)
    assert total_finding is not None
    assert total_finding.severity == "critical"


def test_tool_policy_caps_room_rent():
    # Arogya Sanjeevani room rent cap is 5000.0 / day
    claim_ok = {
        "line_items": [{"description": "Normal Room Rent", "qty": 3, "unit_price": 4000.0, "amount": 12000.0}]
    }
    findings_ok = check_policy_caps("POL-AROGYA-88124", claim_ok)
    assert len(findings_ok) == 0

    # Breach (₹14,500/day)
    claim_breach = {
        "line_items": [{"description": "Super Deluxe Suite Room", "qty": 4, "unit_price": 14500.0, "amount": 58000.0}]
    }
    findings_breach = check_policy_caps("POL-AROGYA-33219", claim_breach)
    assert len(findings_breach) >= 1
    room_f = findings_breach[0]
    assert room_f.check_id == "POLICY_ROOM_RENT_CAP_EXCEEDED"
    assert "Clause 3.1" in room_f.explanation
    assert room_f.severity == "high"


def test_tool_forensics_clean_vs_forged_pdf():
    # G1 Clean PDF
    g1_path = DEMO_DIR / "G1_clean_claim.pdf"
    with open(g1_path, "rb") as f:
        g1_bytes = f.read()

    meta1, findings1 = pdf_metadata_check(g1_bytes)
    assert len(findings1) == 0, "G1 clean claim should have no metadata findings"
    anom1, font_findings1 = font_consistency_check(g1_bytes)
    assert len(font_findings1) == 0, "G1 clean claim should have no font findings"

    # G6 Forged PDF
    g6_path = DEMO_DIR / "G6_forged_document.pdf"
    with open(g6_path, "rb") as f:
        g6_bytes = f.read()

    meta6, findings6 = pdf_metadata_check(g6_bytes)
    producer_f = next((f for f in findings6 if f.check_id == "SUSPICIOUS_PRODUCER_METADATA"), None)
    assert producer_f is not None, "G6 must flag suspicious producer metadata"
    assert "photoshop" in producer_f.explanation.lower()

    date_f = next((f for f in findings6 if f.check_id == "METADATA_DATE_DISCREPANCY"), None)
    assert date_f is not None, "G6 must flag CreationDate vs ModDate discrepancy"

    anom6, font_findings6 = font_consistency_check(g6_bytes)
    assert len(font_findings6) >= 1, "G6 must flag font inconsistency on altered total row"
    assert font_findings6[0].check_id == "FONT_INCONSISTENCY_TAMPERING"
    assert font_findings6[0].evidence[0].bbox is not None, "Font finding must have bbox"


def test_pipeline_golden_g1_clean():
    g1_pdf = DEMO_DIR / "G1_clean_claim.pdf"
    claim = Claim(
        claim_id="CLM-G1-TEST",
        policy_id="POL-AROGYA-88124",
        insurer_id="INS-HDFC",
        claimant=Claimant(claimant_id="CLMNT-8921", name="Rohan Verma", phone="+91-9876543210", bank_account_hash="clean_hash_11"),
        provider=Provider(hospital_id="HOSP-101", name="Max Super Speciality Hospital", city="New Delhi", lat=28.5284, lng=77.2185),
        doctor_id="DOC-2045",
        admission_ts=datetime(2026, 3, 12, 9, 30),
        discharge_ts=datetime(2026, 3, 15, 11, 0),
        diagnosis_code="K35.8",
        subtotal=71000.0,
        tax=3550.0,
        total_claimed=74550.0,
        line_items=[
            LineItem(description="Semi-Private Room Rent (3 days)", qty=3, unit_price=4000.0, amount=12000.0),
            LineItem(description="Laparoscopic Appendectomy Surgery & OT", qty=1, unit_price=45000.0, amount=45000.0),
            LineItem(description="Consultant Surgeon & Anesthetist Visit Fees", qty=3, unit_price=2000.0, amount=6000.0),
            LineItem(description="Post-Op Pharmacy & Antibiotic Consumables", qty=1, unit_price=8000.0, amount=8000.0)
        ],
        documents=[Document(doc_id="DOC-G1", gcs_uri=f"file://{g1_pdf}", doc_type=DocType.BILL, sha256="sha_g1")]
    )

    dossier = run_claims_fraud_pipeline(claim)
    assert dossier.verdict == Verdict.APPROVE
    assert dossier.risk_score < 30
    high_critical = [f for f in dossier.findings if f.severity in ["high", "critical"]]
    assert len(high_critical) == 0


def test_pipeline_golden_g2_arithmetic_mismatch():
    g2_pdf = DEMO_DIR / "G2_arithmetic_mismatch.pdf"
    claim = Claim(
        claim_id="CLM-G2-TEST",
        policy_id="POL-CARE-55192",
        insurer_id="INS-STAR",
        claimant=Claimant(claimant_id="CLMNT-3310", name="Sunita Sharma", phone="+91-9820123456", bank_account_hash="clean_hash_22"),
        provider=Provider(hospital_id="HOSP-102", name="Lifeline Super Speciality Hospital", city="Mumbai", lat=19.0596, lng=72.8295),
        doctor_id="DOC-2089",
        admission_ts=datetime(2026, 4, 14, 10, 0),
        discharge_ts=datetime(2026, 4, 18, 15, 0),
        diagnosis_code="I20.9",
        # Subtotal claims 107142.86 + 5357.14 = 112500, but items sum to only 90500!
        subtotal=107142.86,
        tax=5357.14,
        total_claimed=112500.0,
        line_items=[
            LineItem(description="Hospital Room Rent (4 days)", qty=4, unit_price=4500.0, amount=18000.0),
            LineItem(description="ICU Nursing & Critical Care Monitoring", qty=1, unit_price=25000.0, amount=25000.0),
            LineItem(description="Cardiology Workup, ECG & 2D-Echo", qty=1, unit_price=32000.0, amount=32000.0),
            LineItem(description="In-Patient Pharmacy & Cardiac Infusions", qty=1, unit_price=15500.0, amount=15500.0)
        ],
        documents=[Document(doc_id="DOC-G2", gcs_uri=f"file://{g2_pdf}", doc_type=DocType.BILL, sha256="sha_g2")]
    )

    dossier = run_claims_fraud_pipeline(claim)
    assert any(f.check_id in ["SUBTOTAL_SUM_MISMATCH", "TOTAL_PAYABLE_MISMATCH"] for f in dossier.findings)
    assert dossier.risk_score >= 18


def test_pipeline_golden_g3_policy_cap_breach():
    g3_pdf = DEMO_DIR / "G3_policy_cap_breach.pdf"
    claim = Claim(
        claim_id="CLM-G3-TEST",
        policy_id="POL-AROGYA-33219",
        insurer_id="INS-ICICI",
        claimant=Claimant(claimant_id="CLMNT-6520", name="Vikram Patel", phone="+91-9845098765", bank_account_hash="clean_hash_33"),
        provider=Provider(hospital_id="HOSP-103", name="Metro Healthcare Institute", city="Bengaluru", lat=12.9784, lng=77.6408),
        doctor_id="DOC-2031",
        admission_ts=datetime(2026, 5, 18, 8, 0),
        discharge_ts=datetime(2026, 5, 22, 12, 0),
        diagnosis_code="K80.2",
        subtotal=126500.0,
        tax=6325.0,
        total_claimed=132825.0,
        line_items=[
            LineItem(description="Super Deluxe Executive Suite Room (4 days)", qty=4, unit_price=14500.0, amount=58000.0),
            LineItem(description="Cholecystectomy Laparoscopic Procedure", qty=1, unit_price=42000.0, amount=42000.0),
            LineItem(description="Surgeon & Anesthesia Professional Charges", qty=1, unit_price=15000.0, amount=15000.0),
            LineItem(description="OT Consumables & Surgical Disposables", qty=1, unit_price=11500.0, amount=11500.0)
        ],
        documents=[Document(doc_id="DOC-G3", gcs_uri=f"file://{g3_pdf}", doc_type=DocType.BILL, sha256="sha_g3")]
    )

    dossier = run_claims_fraud_pipeline(claim)
    cap_f = next((f for f in dossier.findings if f.check_id == "POLICY_ROOM_RENT_CAP_EXCEEDED"), None)
    assert cap_f is not None, "G3 must produce POLICY_ROOM_RENT_CAP_EXCEEDED finding"
    assert "Clause 3.1" in cap_f.explanation
    assert dossier.verdict in [Verdict.REVIEW, Verdict.REJECT]


def test_pipeline_golden_g4_cross_insurer_duplicate():
    g4_pdf = DEMO_DIR / "G4_cross_insurer_duplicate.pdf"
    claim = Claim(
        claim_id="CLM-G4-TEST",
        policy_id="POL-OPTIMA-44102",
        insurer_id="INS-NIVA",
        claimant=Claimant(claimant_id="CLMNT-9901", name="Ananya Gupta", phone="+91-9988776655", bank_account_hash="clean_hash_44"),
        provider=Provider(hospital_id="HOSP-104", name="Apex Super Speciality Hospital", city="Hyderabad", lat=17.4156, lng=78.4357),
        doctor_id="DOC-2067",
        admission_ts=datetime(2026, 6, 7, 11, 0),
        discharge_ts=datetime(2026, 6, 10, 16, 0),
        diagnosis_code="S82.8",
        subtotal=77000.0,
        tax=3850.0,
        total_claimed=80850.0,
        line_items=[
            LineItem(description="Twin-Sharing Room Rent (3 days)", qty=3, unit_price=3500.0, amount=10500.0),
            LineItem(description="ORIF Tibia Plating & Fixation Surgery", qty=1, unit_price=48000.0, amount=48000.0),
            LineItem(description="Orthopedic Surgeon Charges & Visits", qty=3, unit_price=2000.0, amount=6000.0),
            LineItem(description="Implants & Antibiotics Consumables", qty=1, unit_price=12500.0, amount=12500.0)
        ],
        documents=[Document(doc_id="DOC-G4", gcs_uri=f"file://{g4_pdf}", doc_type=DocType.BILL, sha256="sha_g4")]
    )

    dossier = run_claims_fraud_pipeline(claim)
    assert any(f.check_id == "CROSS_INSURER_DUPLICATE_CLAIM" for f in dossier.findings)
    assert dossier.verdict == Verdict.REJECT


def test_pipeline_golden_g6_forged_document():
    g6_pdf = DEMO_DIR / "G6_forged_document.pdf"
    claim = Claim(
        claim_id="CLM-G6-TEST",
        policy_id="POL-AROGYA-77112",
        insurer_id="INS-HDFC",
        claimant=Claimant(claimant_id="CLMNT-1200", name="Amit Kulkarni", phone="+91-9890123456", bank_account_hash="clean_hash_66"),
        provider=Provider(hospital_id="HOSP-106", name="CarePlus Medical Center", city="Pune", lat=18.5283, lng=73.8402),
        doctor_id="DOC-2051",
        admission_ts=datetime(2026, 8, 2, 10, 0),
        discharge_ts=datetime(2026, 8, 5, 13, 0),
        diagnosis_code="A09",
        subtotal=85238.10,
        tax=4261.90,
        total_claimed=89500.0,
        line_items=[
            LineItem(description="General Ward Bed Charges (3 days)", qty=3, unit_price=2500.0, amount=7500.0),
            LineItem(description="Conservative Medical Management for Colitis", qty=1, unit_price=12000.0, amount=12000.0),
            LineItem(description="Consultant Physician Daily Visits", qty=3, unit_price=1500.0, amount=4500.0),
            LineItem(description="IV Fluids & Injectable Antibiotics", qty=1, unit_price=6000.0, amount=6000.0)
        ],
        documents=[Document(doc_id="DOC-G6", gcs_uri=f"file://{g6_pdf}", doc_type=DocType.BILL, sha256="sha_g6")]
    )

    dossier = run_claims_fraud_pipeline(claim)
    check_ids = [f.check_id for f in dossier.findings]
    assert "SUSPICIOUS_PRODUCER_METADATA" in check_ids
    assert "FONT_INCONSISTENCY_TAMPERING" in check_ids
    assert "METADATA_DATE_DISCREPANCY" in check_ids
    assert dossier.verdict == Verdict.REJECT
    assert dossier.risk_score >= 70


def test_determinism_three_runs_identical_score_and_verdict():
    """Acceptance criterion: Same claim analyzed 3 times gives the exact same verdict and score."""
    g2_pdf = DEMO_DIR / "G2_arithmetic_mismatch.pdf"
    claim = Claim(
        claim_id="CLM-DETERMINISM-TEST",
        policy_id="POL-CARE-55192",
        insurer_id="INS-STAR",
        claimant=Claimant(claimant_id="CLMNT-3310", name="Sunita Sharma", phone="+91-9820123456", bank_account_hash="clean_hash_det"),
        provider=Provider(hospital_id="HOSP-102", name="Lifeline Super Speciality Hospital", city="Mumbai", lat=19.0596, lng=72.8295),
        doctor_id="DOC-2089",
        admission_ts=datetime(2026, 4, 14, 10, 0),
        discharge_ts=datetime(2026, 4, 18, 15, 0),
        diagnosis_code="I20.9",
        subtotal=107142.86,
        tax=5357.14,
        total_claimed=112500.0,
        line_items=[
            LineItem(description="Hospital Room Rent (4 days)", qty=4, unit_price=4500.0, amount=18000.0),
            LineItem(description="ICU Nursing & Critical Care Monitoring", qty=1, unit_price=25000.0, amount=25000.0)
        ],
        documents=[Document(doc_id="DOC-G2", gcs_uri=f"file://{g2_pdf}", doc_type=DocType.BILL, sha256="sha_g2")]
    )

    dossier1 = run_claims_fraud_pipeline(claim)
    dossier2 = run_claims_fraud_pipeline(claim)
    dossier3 = run_claims_fraud_pipeline(claim)

    assert dossier1.risk_score == dossier2.risk_score == dossier3.risk_score
    assert dossier1.verdict == dossier2.verdict == dossier3.verdict
    assert len(dossier1.findings) == len(dossier2.findings) == len(dossier3.findings)
