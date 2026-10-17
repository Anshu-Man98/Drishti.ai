"""
Unit and regression tests for Fix 3 (Detector Gaps) and Fix 4 (Learned Patterns).
Covers:
1. Flexible and robust future date parsing with injectable reference date (now).
2. Missing printed total handling (produces 'incomplete' and floor REVIEW, not REJECT or TOTAL_PAYABLE_MISMATCH).
3. Firestore cross-claim duplicate detection (SHA-256 exact match, invoice number match, overlapping dates).
4. Learned pattern discriminating features requirement (honest claims don't match, adversarial do).
"""

import uuid
from datetime import datetime, timezone
import pytest

from backend.app.schemas import (
    Claim, Claimant, Provider, LineItem, Document, DocType, Severity, Verdict, AgentName
)
from backend.tools.date_utils import parse_flexible_date, is_date_after_reference
from backend.tools.registry import check_dates, validate_arithmetic
from backend.tools.scoring import score_findings
from backend.tools.pattern_tools import (
    build_claim_fingerprint,
    search_patterns,
    register_learned_pattern,
    clear_learned_patterns_cache
)


# ==============================================================================
# 1. Date Parsing & Future Date Validation (Fix 3a)
# ==============================================================================

def test_flexible_date_parsing_formats():
    """Verify parse_flexible_date handles all standard, Indian, and edge-case formats."""
    # ISO formats
    dt1 = parse_flexible_date("2031-03-14")
    assert dt1 is not None and dt1.year == 2031 and dt1.month == 3 and dt1.day == 14
    dt2 = parse_flexible_date("2031-03-14T10:30:00Z")
    assert dt2 is not None and dt2.year == 2031 and dt2.hour == 10

    # dd-Mon-yyyy
    dt3 = parse_flexible_date("14-Mar-2031")
    assert dt3 is not None and dt3.year == 2031 and dt3.month == 3
    dt4 = parse_flexible_date("15-Oct-2026 11:30 AM")
    assert dt4 is not None and dt4.year == 2026 and dt4.month == 10 and dt4.day == 15

    # dd/mm/yyyy
    dt5 = parse_flexible_date("14/03/2031")
    assert dt5 is not None and dt5.year == 2031 and dt5.month == 3 and dt5.day == 14

    # 2-digit years: d-m-yy
    dt6 = parse_flexible_date("14-3-31")
    assert dt6 is not None and dt6.year == 2031 and dt6.month == 3 and dt6.day == 14

    # Month names and ordinals
    dt7 = parse_flexible_date("March 14, 2031")
    assert dt7 is not None and dt7.year == 2031 and dt7.month == 3
    dt8 = parse_flexible_date("14th March 2031")
    assert dt8 is not None and dt8.year == 2031 and dt8.month == 3

    # Indian dot notation
    dt9 = parse_flexible_date("14.03.2031")
    assert dt9 is not None and dt9.year == 2031 and dt9.month == 3


def test_future_date_detection_with_injectable_now():
    """Verify check_dates emits FUTURE_OR_IMPLAUSIBLE_DATE against injectable reference date."""
    ref_now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)

    # 1. ISO bill date in 2031
    res = check_dates(
        admission_ts="2026-10-10",
        discharge_ts="2026-10-12",
        bill_date="2031-03-14",
        now=ref_now
    )
    assert not res["valid"]
    future_finding = next((f for f in res["findings"] if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"), None)
    assert future_finding is not None
    assert future_finding.severity == Severity.CRITICAL
    assert "2031-03-14" in future_finding.evidence[0].quote
    assert "2026-10-15" in future_finding.evidence[0].quote
    assert future_finding.computed_details["diff_days"] > 1000

    # 2. Honest dates in the past
    res_clean = check_dates(
        admission_ts="2026-10-10",
        discharge_ts="2026-10-12",
        bill_date="2026-10-12",
        now=ref_now
    )
    assert res_clean["valid"]
    assert len(res_clean["findings"]) == 0


# ==============================================================================
# 2. Missing Printed Total Handling (Fix 3b)
# ==============================================================================

def test_missing_printed_total_floors_at_review_not_reject():
    """
    A bill without a NET PAYABLE / total line must produce status 'incomplete'
    and verdict floor REVIEW with EXTRACTION_INCOMPLETE, NOT TOTAL_PAYABLE_MISMATCH and not REJECT.
    """
    line_items = [
        {"description": "Ward bed charges", "qty": 2.0, "unit_price": 2200.0, "amount": 4400.0},
        {"description": "Doctor consultation", "qty": 2.0, "unit_price": 500.0, "amount": 1000.0}
    ]

    res = validate_arithmetic(
        subtotal=5400.0,
        tax=270.0,
        total=None,  # No printed total on invoice
        line_items=line_items,
        extraction_incomplete=False
    )

    assert res["status"] == "incomplete"
    check_ids = [f.check_id for f in res["findings"]]
    assert "EXTRACTION_INCOMPLETE" in check_ids
    assert "TOTAL_PAYABLE_MISMATCH" not in check_ids
    assert "SUBTOTAL_SUM_MISMATCH" not in check_ids

    # Find the missing total finding
    f_missing = next(f for f in res["findings"] if f.finding_id == "F-MATH-MISSING-TOTAL")
    assert "EXTRACTION_INCOMPLETE: no printed total" in f_missing.title
    assert f_missing.severity == Severity.LOW

    # Score findings: must produce REVIEW (45-65), never REJECT
    risk_score, verdict = score_findings(res["findings"])
    assert verdict == Verdict.REVIEW
    assert 45 <= risk_score <= 65


def test_real_total_mismatch_remains_fraud():
    """A printed total that is incorrect must still emit TOTAL_PAYABLE_MISMATCH and REJECT."""
    line_items = [
        {"description": "Surgery charges", "qty": 1.0, "unit_price": 40000.0, "amount": 40000.0}
    ]

    res = validate_arithmetic(
        subtotal=40000.0,
        tax=2000.0,
        total=82000.0,  # Stated total 82,000 vs expected 42,000 (huge fraud mismatch)
        line_items=line_items
    )

    check_ids = [f.check_id for f in res["findings"]]
    assert "TOTAL_PAYABLE_MISMATCH" in check_ids

    risk_score, verdict = score_findings(res["findings"])
    assert verdict == Verdict.REJECT
    assert risk_score >= 85


# ==============================================================================
# 3. Cross-Claim Duplicate for Uploaded Claims in Firestore (Fix 3c)
# ==============================================================================

def test_firestore_duplicate_detection(monkeypatch):
    """Verify find_firestore_duplicates catches SHA-256 and invoice number duplicates."""
    from backend.app.services.db import db_service

    # Create base claim
    claim1 = Claim(
        claim_id="CLM-BASE-001",
        policy_id="POL-001",
        insurer_id="INS-001",
        claimant=Claimant(claimant_id="C1", name="Ramesh Kumar", phone="9999999999", bank_account_hash="hash_ramesh_123"),
        provider=Provider(hospital_id="H1", name="City Speciality Hospital", city="New Delhi"),
        admission_ts=datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc),
        discharge_ts=datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc),
        total_claimed=25000.0,
        documents=[
            Document(
                doc_id="DOC-1",
                gcs_uri="gs://b/1.pdf",
                doc_type=DocType.BILL,
                sha256="abc123def456789012345678901234567890123456789012345678901234abcd",
                filename="bill_oct.pdf"
            )
        ],
        metadata={"invoice_number": "INV-2026-9999"}
    )

    # Mock Firestore stream
    fake_doc = type("FakeDoc", (), {
        "id": "CLM-BASE-001",
        "to_dict": lambda self=None: {
            "claim_id": "CLM-BASE-001",
            "source": "upload",
            "claimant": {"name": "Ramesh Kumar"},
            "provider": {"name": "City Speciality Hospital"},
            "admission_ts": "2026-10-10T10:00:00Z",
            "total_claimed": 25000.0,
            "documents": [{
                "sha256": "abc123def456789012345678901234567890123456789012345678901234abcd",
                "filename": "bill_oct.pdf"
            }],
            "metadata": {"invoice_number": "INV-2026-9999"}
        }
    })()

    monkeypatch.setattr(db_service, "_call_fs", lambda fn, timeout=15.0: [fake_doc])

    # 1. Exact SHA-256 duplicate uploaded under new claim ID
    claim2_exact = Claim(
        claim_id="CLM-DUP-002",
        policy_id="POL-002",
        insurer_id="INS-002",
        claimant=Claimant(claimant_id="C2", name="Ramesh Kumar", phone="+91-9999999999", bank_account_hash="hash_ramesh_123"),
        provider=Provider(hospital_id="H1", name="City Speciality Hospital"),
        total_claimed=25000.0,
        documents=[
            Document(
                doc_id="DOC-2",
                gcs_uri="gs://b/2.pdf",
                doc_type=DocType.BILL,
                sha256="abc123def456789012345678901234567890123456789012345678901234abcd",
                filename="copy_of_bill.pdf"
            )
        ]
    )

    findings = db_service.find_firestore_duplicates(claim2_exact)
    assert len(findings) == 1
    assert findings[0].check_id == "EXACT_DUPLICATE_BILL"
    assert findings[0].severity == Severity.CRITICAL
    assert "CLM-BASE-001" in findings[0].title

    # 2. Different document file, but matching invoice number
    claim3_invoice_dup = Claim(
        claim_id="CLM-DUP-003",
        policy_id="POL-003",
        insurer_id="INS-003",
        claimant=Claimant(claimant_id="C3", name="Ramesh Kumar", phone="+91-9999999999", bank_account_hash="hash_ramesh_123"),
        provider=Provider(hospital_id="H1", name="City Speciality Hospital"),
        total_claimed=25000.0,
        documents=[
            Document(
                doc_id="DOC-3",
                gcs_uri="gs://b/3.pdf",
                doc_type=DocType.BILL,
                sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                filename="rescanned_bill.pdf"
            )
        ],
        metadata={"invoice_number": "INV-2026-9999"}
    )

    findings_inv = db_service.find_firestore_duplicates(claim3_invoice_dup)
    assert len(findings_inv) == 1
    assert findings_inv[0].check_id == "EXACT_DUPLICATE_BILL"
    assert "INV-2026-9999" in findings_inv[0].title

    # 3. Duel simulation marker: mutations do not flag duplicate of base
    claim_duel = Claim(
        claim_id="CLM-DUEL-ROUND2",
        policy_id="POL-001",
        insurer_id="INS-001",
        source="duel",
        claimant=Claimant(claimant_id="C1", name="Ramesh Kumar", phone="+91-9999999999", bank_account_hash="hash_ramesh_123"),
        provider=Provider(hospital_id="H1", name="City Speciality Hospital"),
        total_claimed=25000.0,
        documents=[
            Document(
                doc_id="DOC-D",
                gcs_uri="gs://b/d.pdf",
                doc_type=DocType.BILL,
                sha256="abc123def456789012345678901234567890123456789012345678901234abcd",
                filename="mutated_bill.pdf"
            )
        ]
    )
    findings_duel = db_service.find_firestore_duplicates(claim_duel)
    assert len(findings_duel) == 0


# ==============================================================================
# 4. Learned Pattern Discriminating Feature Rules (Fix 4)
# ==============================================================================

def test_learned_pattern_requires_discriminating_features():
    """
    Learned evasion patterns require:
    1. Diagnosis family match
    2. At least one discriminating feature (inflation ratio, padded ancillary, room rate ratio)
    Clean claims without discriminating features must NOT match.
    """
    clear_learned_patterns_cache()

    # Register an adversarial evasion pattern targeting S82 fracture with tariff arbitrage
    learned_pattern = register_learned_pattern({
        "pattern_id": "PAT-LEARNED-S82-ARBITRAGE",
        "fraud_type": "learned_evasion",
        "title": "Learned Evasion: Diagnostic Category Arbitrage and Upcoding to S82.8",
        "tactic": "Tariff Arbitrage and Upcoding to S82.8 with Clean Tariff Compliance",
        "narrative": "Upcoding to S82.8 tariff corridor with inflated ancillary and multiplier 1.26",
        "signature": "diagnosis_code:S82.8 inflation_ratio:1.26 unbundled_or_padded_ancillary",
        "typical_severity": "HIGH"
    })

    # Case A: Honest fracture bill with S82.8, standard price (103,635), no inflation, room rent 4,000
    clean_fracture_claim = Claim(
        claim_id="CLM-CLEAN-FRACTURE",
        policy_id="POL-STD",
        insurer_id="INS-STAR",
        claimant=Claimant(claimant_id="C1", name="Honest Patient", phone="+91-9999999999", bank_account_hash="hash_honest_123"),
        diagnosis_code="S82.8",
        total_claimed=103635.0,
        admission_ts=datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc),
        discharge_ts=datetime(2026, 10, 12, 11, 0, tzinfo=timezone.utc),
        line_items=[
            LineItem(description="Room rent", qty=4.0, unit_price=4000.0, amount=16000.0),
            LineItem(description="OT charges", qty=1.0, unit_price=22000.0, amount=22000.0),
            LineItem(description="Orthopaedic surgeon fee", qty=1.0, unit_price=20000.0, amount=20000.0),
            LineItem(description="Physiotherapy", qty=4.0, unit_price=800.0, amount=3200.0)
        ]
    )

    fp_clean = build_claim_fingerprint(clean_fracture_claim, findings=[])
    matches_clean = search_patterns(fp_clean, k=3, min_score=0.5)

    # Must NOT match the learned evasion pattern!
    matched_ids = [m["pattern_id"] for m in matches_clean]
    assert "PAT-LEARNED-S82-ARBITRAGE" not in matched_ids

    # Case B: Adversarial claim with discriminating features: inflation ratio 1.26 and padded ancillary share
    adversarial_claim = Claim(
        claim_id="CLM-ADV-FRACTURE",
        policy_id="POL-STD",
        insurer_id="INS-STAR",
        claimant=Claimant(claimant_id="C2", name="Adversarial Patient", phone="+91-9999999999", bank_account_hash="hash_adv_123"),
        diagnosis_code="S82.8",
        total_claimed=130000.0,
        admission_ts=datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc),
        discharge_ts=datetime(2026, 10, 12, 11, 0, tzinfo=timezone.utc),
        line_items=[
            LineItem(description="Room rent", qty=4.0, unit_price=4000.0, amount=16000.0),
            LineItem(description="Implant titanium plate and screws", qty=1.0, unit_price=60000.0, amount=60000.0),  # Padded ancillary > 45%
            LineItem(description="Specialist Consumables", qty=1.0, unit_price=20000.0, amount=20000.0)
        ]
    )

    # Simulated finding showing price benchmark violation
    from backend.app.schemas import Finding
    bench_finding = Finding(
        finding_id="F-BENCH-1",
        agent=AgentName.POLICY,
        check_id="TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
        severity=Severity.HIGH,
        title="Total above benchmark",
        explanation="Total exceeds standard corridor",
        evidence=[],
        confidence=0.95,
        computed_details={"ratio": 1.26}
    )

    fp_adv = build_claim_fingerprint(adversarial_claim, findings=[bench_finding])
    matches_adv = search_patterns(fp_adv, k=3, min_score=0.5)

    # DOES match the learned pattern!
    matched_adv_ids = [m["pattern_id"] for m in matches_adv]
    assert "PAT-LEARNED-S82-ARBITRAGE" in matched_adv_ids


# ==============================================================================
# 5. City Extraction Fallback from Address Strings (Fix 3d)
# ==============================================================================

def test_city_extraction_from_address_entities():
    """Verify city name resolution extracts valid cities from address strings."""
    import re
    from backend.tools.docai import CITY_COORDS

    def resolve_city_from_text(addr_text: str) -> str:
        for city_key, (c_name, c_lat, c_lng) in CITY_COORDS.items():
            if re.search(r"\b" + re.escape(city_key) + r"\b", addr_text.lower()):
                return c_name
        return "Unknown"

    assert resolve_city_from_text("Dehradun, Uttarakhand, India - 248001") == "Dehradun"
    assert resolve_city_from_text("Indore, Madhya Pradesh 452001") == "Indore"
    assert resolve_city_from_text("Bandra West, Mumbai 400050") == "Mumbai"
    assert resolve_city_from_text("Himalaya Care Centre, Rajpur Road, Dehradun") == "Dehradun"
    assert resolve_city_from_text("Unknown Hospital Road, Somewhere") == "Unknown"


