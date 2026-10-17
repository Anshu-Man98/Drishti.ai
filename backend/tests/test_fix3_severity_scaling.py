"""
backend/tests/test_fix3_severity_scaling.py

Comprehensive tests for Fix 3:
1. Arithmetic mismatch severity scaling with rupee amount and percentage:
   - Discrepancy <= 1000 INR or <= 5% -> LOW or MEDIUM (verdict floor REVIEW, risk ~35-55)
   - Discrepancy > 5000 INR or > 10% -> CRITICAL (verdict REJECT, risk >= 85)
2. Missing printed total/subtotal on document:
   - Handled as EXTRACTION_INCOMPLETE with status 'incomplete', verdict floor REVIEW
   - NEVER emit TOTAL_PAYABLE_MISMATCH unless total is actually printed and wrong
3. Suspicious producer metadata alone (e.g. Canva on clean amounts):
   - Verdict floor REVIEW, risk score <= 65
   - Only escalates to REJECT when combined with font tampering, date edits, or amount inconsistency
4. Document type gate:
   - Classifies non-medical dining receipts as NOT_A_MEDICAL_BILL with status 'incomplete'
   - Does NOT run arithmetic fraud findings or benchmark findings on it
5. Diminishing returns combining formula:
   - Decaying weights (w_1 + 0.8 w_2 + 0.6 w_3 + 0.4 sum_{i>=4} w_i)
   - Preserves monotonicity and prevents minor issues from summing to 100
"""

import pytest
from backend.app.schemas import Claim, LineItem, Claimant, Provider, Finding, Severity, AgentName, Verdict
from backend.tools.registry import validate_arithmetic, calculate_arithmetic_severity
from backend.tools.scoring import score_findings, calculate_diminishing_score, is_incomplete_analysis_condition
from backend.agents.policy import analyze_policy_and_arithmetic, is_non_medical_bill


# ------------------------------------------------------------------------------
# 1. Diminishing Returns Formula & Monotonicity
# ------------------------------------------------------------------------------

def test_diminishing_returns_formula():
    """Verify exact formula behavior on single, multiple, and minor findings."""
    assert calculate_diminishing_score([]) == 0.0
    assert calculate_diminishing_score([50]) == 50.0
    assert calculate_diminishing_score([50, 30]) == 50.0 + 0.8 * 30.0  # 74.0
    assert calculate_diminishing_score([30, 30, 30]) == 30.0 + 0.8 * 30.0 + 0.6 * 30.0  # 72.0

    # 5 minor LOW findings (5 each): 5 + 4 + 3 + 2 + 2 = 16 (not 25)
    five_low = [5, 5, 5, 5, 5]
    assert calculate_diminishing_score(five_low) == 16.0

    # 5 minor MEDIUM findings (15 each): 15 + 12 + 9 + 6 + 6 = 48 (not 75 / REJECT)
    five_med = [15, 15, 15, 15, 15]
    score_med = calculate_diminishing_score(five_med)
    assert score_med == 48.0
    assert score_med < 70.0  # Stays safely within REVIEW


def test_diminishing_returns_monotonicity():
    """Adding findings or increasing finding severity strictly increases or preserves score."""
    w1 = [15, 15]
    w2 = [15, 15, 15]
    w3 = [30, 15, 15]
    w4 = [50, 30, 15]

    s1 = calculate_diminishing_score(w1)
    s2 = calculate_diminishing_score(w2)
    s3 = calculate_diminishing_score(w3)
    s4 = calculate_diminishing_score(w4)

    assert s1 < s2 < s3 < s4


# ------------------------------------------------------------------------------
# 2. Arithmetic Discrepancy Severity Scaling Tiers
# ------------------------------------------------------------------------------

def test_arithmetic_severity_helper():
    """Test calculate_arithmetic_severity helper logic across tiers."""
    # <= 1000 INR or <= 5%
    assert calculate_arithmetic_severity(100.0, 1.0) == Severity.LOW
    assert calculate_arithmetic_severity(500.0, 4.0) == Severity.MEDIUM
    assert calculate_arithmetic_severity(500.0, 12.0) == Severity.MEDIUM  # diff <= 1000 overrides pct

    # > 5000 INR or > 10%
    assert calculate_arithmetic_severity(17475.0, 12.0) == Severity.CRITICAL
    assert calculate_arithmetic_severity(6000.0, 8.0) == Severity.CRITICAL

    # Intermediate: between 1000 and 5000 and between 5% and 10%
    assert calculate_arithmetic_severity(3000.0, 7.5) == Severity.HIGH


def test_subtle_500_rupee_mismatch_routes_to_review():
    """A 500 rupee line-item/subtotal mismatch must be MEDIUM severity and REVIEW ~35-55 (not REJECT 85)."""
    line_items = [
        {"description": "Consultation", "qty": 1, "unit_price": 5000.0, "amount": 5000.0},
        {"description": "Diagnostic Test", "qty": 1, "unit_price": 3000.0, "amount": 3000.0},
    ]
    # Sum is 8000, printed subtotal is 8500 (+500 mismatch)
    res = validate_arithmetic(line_items=line_items, subtotal=8500.0, tax=425.0, total=8925.0)

    findings = res["findings"]
    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == "SUBTOTAL_SUM_MISMATCH"
    assert f.severity == Severity.MEDIUM

    risk, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.REVIEW
    assert 35 <= risk <= 55


def test_large_17475_rupee_mismatch_routes_to_reject():
    """A 17,475 rupee mismatch (like G2) must be CRITICAL severity and REJECT with risk >= 85."""
    line_items = [
        {"description": "Room Charges", "qty": 3, "unit_price": 5000.0, "amount": 15000.0},
        {"description": "Surgery", "qty": 1, "unit_price": 75000.0, "amount": 75000.0},
    ]
    # Sum is 90000, printed subtotal is 107475 (+17475 mismatch)
    res = validate_arithmetic(line_items=line_items, subtotal=107475.0, tax=5373.75, total=112848.75)

    findings = res["findings"]
    sub_f = next(f for f in findings if f.check_id == "SUBTOTAL_SUM_MISMATCH")
    assert sub_f.severity == Severity.CRITICAL

    risk, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.REJECT
    assert risk >= 85


# ------------------------------------------------------------------------------
# 3. Missing Printed Total / Subtotal
# ------------------------------------------------------------------------------

def test_missing_printed_total_emits_extraction_incomplete():
    """Invoice without a printed total must emit EXTRACTION_INCOMPLETE, never TOTAL_PAYABLE_MISMATCH."""
    line_items = [
        {"description": "Consultation", "qty": 1, "unit_price": 1000.0, "amount": 1000.0},
        {"description": "Medicine", "qty": 1, "unit_price": 2000.0, "amount": 2000.0},
    ]
    # total is None / 0
    res = validate_arithmetic(line_items=line_items, subtotal=3000.0, tax=150.0, total=None)

    findings = res["findings"]
    check_ids = [f.check_id for f in findings]

    assert "EXTRACTION_INCOMPLETE" in check_ids
    assert "TOTAL_PAYABLE_MISMATCH" not in check_ids
    assert res["status"] == "incomplete"

    # Must be marked incomplete condition and route to REVIEW
    assert any(is_incomplete_analysis_condition(f) for f in findings)
    risk, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.REVIEW
    assert risk >= 45


# ------------------------------------------------------------------------------
# 4. Suspicious Producer Metadata Isolation
# ------------------------------------------------------------------------------

def test_canva_metadata_alone_routes_to_review():
    """Canva/Photoshop producer metadata alone on clean amounts must route to REVIEW with risk <= 65."""
    findings = [
        Finding(
            finding_id="F-CANVA-ALONE",
            agent=AgentName.FORENSICS,
            check_id="SUSPICIOUS_PRODUCER_METADATA",
            severity=Severity.HIGH,
            title="Document generated using non-standard software: Canva",
            explanation="PDF metadata identifies the producing application as Canva.",
            evidence=[],
            confidence=0.95
        )
    ]
    risk, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.REVIEW
    assert risk <= 65


def test_canva_metadata_with_font_tampering_escalates_to_reject():
    """Canva metadata combined with font tampering escalates to REJECT with risk >= 85."""
    findings = [
        Finding(
            finding_id="F-CANVA-1",
            agent=AgentName.FORENSICS,
            check_id="SUSPICIOUS_PRODUCER_METADATA",
            severity=Severity.HIGH,
            title="Document generated using Canva",
            explanation="Canva producer detected.",
            evidence=[],
            confidence=0.95
        ),
        Finding(
            finding_id="F-FONT-1",
            agent=AgentName.FORENSICS,
            check_id="FONT_INCONSISTENCY_TAMPERING",
            severity=Severity.HIGH,
            title="Font inconsistency detected across total row",
            explanation="Different typeface used for total row.",
            evidence=[],
            confidence=0.95
        )
    ]
    risk, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.REJECT
    assert risk >= 85


# ------------------------------------------------------------------------------
# 5. Document Type Gate (Non-Medical Bill)
# ------------------------------------------------------------------------------

def test_restaurant_invoice_classified_as_not_a_medical_bill():
    """A dining/restaurant receipt is gated as NOT_A_MEDICAL_BILL with status incomplete and no math checks."""
    restaurant_claim = Claim(
        claim_id="CLM-TEST-RESTAURANT",
        diagnosis_code=None,
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-1", name="Rohan Sharma", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-1", name="Royal Spice Bistro & Bar", city="Mumbai"),
        subtotal=2500.0,
        tax=125.0,
        total_claimed=2625.0,
        line_items=[
            LineItem(description="Chicken Tikka Butter Masala", qty=2, unit_price=450.0, amount=900.0, page=1, source="form"),
            LineItem(description="Butter Garlic Naan", qty=4, unit_price=80.0, amount=320.0, page=1, source="form"),
            LineItem(description="Hyderabadi Dum Biryani", qty=2, unit_price=480.0, amount=960.0, page=1, source="form"),
            LineItem(description="Fresh Lime Soda", qty=4, unit_price=80.0, amount=320.0, page=1, source="form"),
        ]
    )

    is_non_med, prov, items = is_non_medical_bill(restaurant_claim)
    assert is_non_med is True
    assert len(items) >= 3

    findings = analyze_policy_and_arithmetic(restaurant_claim)
    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == "NOT_A_MEDICAL_BILL"
    assert f.severity == Severity.HIGH
    assert f.computed_details.get("status") == "incomplete"

    # Arithmetic checks and benchmarks must NOT have run
    check_ids = [x.check_id for x in findings]
    assert "SUBTOTAL_SUM_MISMATCH" not in check_ids
    assert "TOTAL_PAYABLE_MISMATCH" not in check_ids
    assert "LINE_ITEM_PRICE_ABOVE_BENCHMARK" not in check_ids

    # Must be marked incomplete condition and floor at REVIEW
    assert is_incomplete_analysis_condition(f) is True
    risk, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.REVIEW
    assert risk >= 45
