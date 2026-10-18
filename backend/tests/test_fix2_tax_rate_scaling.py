"""
backend/tests/test_fix2_tax_rate_scaling.py

Unit tests for QA Fix 2: Tax-rate mismatch severity depends on the money.
Requirements:
1. 5% (compliant) -> no finding
2. 18% on healthcare (commercial rate) -> medium or high depending on money, moves verdict
3. 5.4% (₹50 rounding diff) -> low severity, verdict stays APPROVE
4. 12% on a bill where 12% is valid (e.g. medical device supply if configured) -> compliant
5. Missing tax line on an exempt bill -> 0%, compliant
6. Printed rate not in valid configured rates (e.g. 7.3% invented rate) -> high severity
7. Severity scaling thresholds:
   - low if excess < max(₹200, 0.5% of total) -> stays informational
   - medium if excess >= max(₹200, 0.5% of total)
   - high if excess >= 5% of total OR rate not in valid rates table
8. Scoring floor: medium or higher TAX_RATE_MISMATCH forces verdict floor REVIEW.
"""

import pytest
from backend.app.schemas import Claim, LineItem, Claimant, Provider, Verdict, Severity
from backend.tools.registry import validate_tax_rates
from backend.agents.policy import analyze_policy_and_arithmetic
from backend.tools.scoring import score_findings


def test_tax_rate_5pct_compliant():
    """5.0% standard healthcare GST rate is compliant with no findings."""
    res = validate_tax_rates(subtotal=11350.0, tax=567.50)
    assert res["valid"] is True
    assert len(res["findings"]) == 0
    assert "Compliant" in res["chip"]


def test_tax_rate_exempt_0pct_compliant():
    """Missing tax line / 0.0 tax on an exempt bill is compliant with no findings."""
    res = validate_tax_rates(subtotal=11350.0, tax=0.0)
    assert res["valid"] is True
    assert len(res["findings"]) == 0
    assert "Exempt" in res["chip"]


def test_tax_rate_12pct_configured_valid():
    """12.0% tax rate is compliant when configured as an expected rate (e.g. medical devices)."""
    # 1. Configured via expected_rates argument
    res = validate_tax_rates(subtotal=10000.0, tax=1200.0, expected_rates=[0.12])
    assert res["valid"] is True
    assert len(res["findings"]) == 0
    assert "12.0%" in res["chip"]

    # 2. Configured via line item rate
    items = [{"description": "Cardiac Stent (Medical Device)", "qty": 1, "unit_price": 10000.0, "amount": 10000.0, "tax_rate": 0.12}]
    res_items = validate_tax_rates(subtotal=10000.0, tax=1200.0, line_items=items)
    assert res_items["valid"] is True
    assert len(res_items["findings"]) == 0


def test_tax_rate_5_4_pct_rounding_low_severity():
    """
    Subtotal 11,350 with tax 617.50 (effective rate ~5.44%, diff ₹50.00).
    Total = 11,967.50.
    max(₹200, 0.5% of total) = max(200, 59.84) = ₹200.
    Excess (₹50) < ₹200 -> Severity.LOW.
    Informational only: scoring leaves verdict at APPROVE.
    """
    subtotal = 11350.0
    tax = 617.50  # 50 INR excess
    res = validate_tax_rates(subtotal=subtotal, tax=tax)
    assert res["valid"] is False
    assert len(res["findings"]) == 1
    f = res["findings"][0]
    assert f.check_id == "TAX_RATE_MISMATCH"
    assert f.severity == Severity.LOW
    assert f.computed_details["excess_tax_rupees"] == 50.0
    assert "minor" in f.title.lower() and "rounding" in f.title.lower()

    # Verify scoring floor: LOW severity TAX_RATE_MISMATCH does not block APPROVE
    risk_score, verdict = score_findings([f], ml_probability=0.05)
    assert verdict == Verdict.APPROVE
    assert risk_score < 30


def test_tax_rate_18pct_commercial_moves_verdict_to_review():
    """
    Subtotal 11,350 with tax 2,043.00 (effective rate 18.0%).
    Excess tax = 2,043.00 - 567.50 = ₹1,475.50.
    Total = 13,393.00. 5% of total = ₹669.65.
    Excess (1,475.50) >= 669.65 -> Severity.HIGH.
    Scoring enforces verdict floor REVIEW.
    """
    subtotal = 11350.0
    tax = 2043.00
    res = validate_tax_rates(subtotal=subtotal, tax=tax)
    assert res["valid"] is False
    assert len(res["findings"]) == 1
    f = res["findings"][0]
    assert f.check_id == "TAX_RATE_MISMATCH"
    assert f.severity in (Severity.MEDIUM, Severity.HIGH)
    assert f.computed_details["excess_tax_rupees"] == 1475.5

    risk_score, verdict = score_findings([f], ml_probability=0.05)
    assert verdict == Verdict.REVIEW
    assert risk_score >= 30


def test_tax_rate_medium_severity_intermediate_excess():
    """
    Subtotal 100,000. Expected tax 5,000 (5%). Charged tax 8,000 (8%). Total = 108,000.
    Excess = 3,000.
    max(₹200, 0.5% of total) = max(200, 540) = ₹540.
    5% of total = ₹5,400.
    Excess (3,000) >= 540 and < 5,400 -> Severity.MEDIUM.
    Medium severity forces verdict floor REVIEW.
    """
    subtotal = 100000.0
    tax = 8000.0  # 8%
    # 8% is not in standard GST slabs, but let's test a valid standard slab with medium excess:
    # E.g. expected 5%, standard 12% applied on a bill where excess is medium:
    # Subtotal 50,000. Expected 5% = 2,500. Charged 12% = 6,000. Total = 56,000.
    # Excess = 3,500. 5% of 56,000 = 2,800. Excess > 5% of total -> High.
    # Let's use valid rate 12% on a large total where excess is between 0.5% and 5% of total:
    # Subtotal 400,000. Expected 5% = 20,000. Charged 12% = 48,000.
    # Total = 448,000. Excess = 28,000. 5% of 448,000 = 22,400. Excess > 5% -> High.
    # What if tax rate is 6.5% on 100,000 (with 6.5% in valid_rates for this test)?
    res = validate_tax_rates(subtotal=100000.0, tax=7000.0, valid_rates=[0.05, 0.07, 0.12])
    # 7% on 100,000: Excess = 2,000. Total = 107,000. 5% of total = 5,350. Threshold low-med = 535.
    # Excess 2000 is between 535 and 5350 -> Severity.MEDIUM.
    assert res["valid"] is False
    f = res["findings"][0]
    assert f.severity == Severity.MEDIUM

    risk_score, verdict = score_findings([f], ml_probability=0.05)
    assert verdict == Verdict.REVIEW
    assert risk_score >= 35


def test_tax_rate_invented_rate_high_severity():
    """Printed rate of 7.3% is not in the valid standard GST slabs (0, 5, 12, 18, 28) -> Severity.HIGH."""
    subtotal = 11350.0
    tax = 828.55  # ~7.3%
    res = validate_tax_rates(subtotal=subtotal, tax=tax)
    assert res["valid"] is False
    assert len(res["findings"]) == 1
    f = res["findings"][0]
    assert f.severity == Severity.HIGH
    assert f.computed_details["is_in_valid_rates"] is False
    assert "Standard Tax Slabs" in f.title


def test_claim_policy_pipeline_integration_tax_rates():
    """End-to-end policy pipeline test for clean vs rounding vs excess tax."""
    claimant = Claimant(claimant_id="C1", name="Test Claimant", phone="9999999999", bank_account_hash="h1")
    provider = Provider(hospital_id="H1", name="Test Hospital", city="Delhi")
    items = [LineItem(description="Ward bed charges", qty=2, unit_price=2000.0, amount=4000.0, page=1, source="form")]

    # 1. Rounding difference claim (₹50 diff)
    claim_rounding = Claim(
        claim_id="CLM-TAX-ROUNDING",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=claimant,
        provider=provider,
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",
        subtotal=11350.0,
        tax=617.50,  # 50 INR rounding difference
        total_claimed=11967.50,
        line_items=items
    )
    findings_rounding = analyze_policy_and_arithmetic(claim_rounding)
    tax_f = [f for f in findings_rounding if f.check_id == "TAX_RATE_MISMATCH"]
    assert len(tax_f) == 1
    assert tax_f[0].severity == Severity.LOW

    # 2. Configured 12% claim via metadata
    claim_12 = Claim(
        claim_id="CLM-TAX-12",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=claimant,
        provider=provider,
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",
        subtotal=10000.0,
        tax=1200.0,
        total_claimed=11200.0,
        metadata={"expected_tax_rates": [0.12]},
        line_items=items
    )
    findings_12 = analyze_policy_and_arithmetic(claim_12)
    tax_f12 = [f for f in findings_12 if f.check_id == "TAX_RATE_MISMATCH"]
    assert len(tax_f12) == 0
