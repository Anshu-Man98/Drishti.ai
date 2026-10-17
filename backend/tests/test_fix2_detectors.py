"""
backend/tests/test_fix2_detectors.py

Unit and integration tests for QA Fix 2: Missing fraud detectors.
Tests:
1. DUPLICATE_LINE_ITEM: Exact & normalized duplicates flagged, different dates exempted.
2. ROOM_DAYS_EXCEED_STAY: Billed room days exceeding length of stay.
3. FUTURE_OR_IMPLAUSIBLE_DATE: Future dates rejected (>= 2030 Critical, future High).
4. TAX_RATE_MISMATCH: Effective GST rate mismatch against 5% / 0% healthcare rules.
5. LINE_ITEM_PRICE_ABOVE_BENCHMARK & TOTAL_ABOVE_DIAGNOSIS_BENCHMARK: 3x price inflated bill flags both and reaches REVIEW >= 45.
6. REVERSED_HOSPITALIZATION_DATES: Chronological impossibility triggers REJECT >= 85.
7. Clean bills (base bill, clean expensive bill) stay APPROVE with risk < 30.
"""

import json
from pathlib import Path
import pytest

from backend.app.schemas import Claim, LineItem, Finding, Severity, Verdict, Claimant, Provider
from backend.tools.registry import (
    detect_duplicate_line_items,
    check_room_days_vs_stay,
    validate_tax_rates,
    check_dates,
    check_price_benchmarks,
    to_paise,
    to_rupees
)
from backend.agents.policy import analyze_policy_and_arithmetic
from backend.tools.scoring import score_findings

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
EVAL_DIR = ROOT_DIR / "data" / "eval_bills_v2"


# ---------------------------------------------------------------------------
# Unit tests for individual deterministic detector tools
# ---------------------------------------------------------------------------

def test_detect_duplicate_line_items():
    items = [
        {"description": "Consultation charges", "qty": 2, "unit_price": 800.0, "amount": 1600.0},
        {"description": "Insulin therapy 3x1200", "qty": 3, "unit_price": 1200.0, "amount": 3600.0},
        {"description": "insulin therapy 3x1200", "qty": 3, "unit_price": 1200.0, "amount": 3600.0},  # duplicate (diff case)
        {"description": "Ward bed charges", "qty": 2, "unit_price": 2500.0, "amount": 5000.0},
    ]
    res = detect_duplicate_line_items(items)
    assert res["valid"] is False
    assert len(res["findings"]) == 1
    f = res["findings"][0]
    assert f.check_id == "DUPLICATE_LINE_ITEM"
    assert "Insulin therapy 3x1200" in f.title
    assert f.computed_details["excess_instances"] == 1
    assert f.computed_details["excess_rupees"] == 3600.0


def test_detect_duplicate_line_items_date_exempt():
    # If date is specified and different, it should be exempted
    items = [
        {"description": "Ward bed charges", "qty": 1, "unit_price": 2500.0, "amount": 2500.0, "date": "10-Sep-2026"},
        {"description": "Ward bed charges", "qty": 1, "unit_price": 2500.0, "amount": 2500.0, "date": "11-Sep-2026"},
    ]
    res = detect_duplicate_line_items(items)
    assert res["valid"] is True
    assert len(res["findings"]) == 0


def test_check_room_days_vs_stay():
    # 2 nights stay: 10-Sep to 12-Sep
    items = [
        {"description": "Ward bed charges", "qty": 9, "unit_price": 2500.0, "amount": 22500.0},
        {"description": "Consultation", "qty": 2, "unit_price": 800.0, "amount": 1600.0},
    ]
    res = check_room_days_vs_stay("2026-09-10T09:00:00", "2026-09-12T12:00:00", items)
    assert res["valid"] is False
    assert len(res["findings"]) == 1
    f = res["findings"][0]
    assert f.check_id == "ROOM_DAYS_EXCEED_STAY"
    assert f.computed_details["allowed_stay_days"] == 2
    assert f.computed_details["billed_room_days"] == 9.0
    assert f.computed_details["excess_room_days"] == 7.0
    assert f.computed_details["excess_room_amount_rupees"] == 17500.0


def test_check_room_days_vs_stay_compliant():
    items = [
        {"description": "Ward bed charges", "qty": 2, "unit_price": 2500.0, "amount": 5000.0},
    ]
    res = check_room_days_vs_stay("2026-09-10T09:00:00", "2026-09-12T12:00:00", items)
    assert res["valid"] is True
    assert len(res["findings"]) == 0


def test_validate_tax_rates_mismatch():
    # Subtotal 11350, printed tax 2043 (18% GST instead of expected 5%)
    res = validate_tax_rates(11350.0, 2043.0)
    assert res["valid"] is False
    assert len(res["findings"]) == 1
    f = res["findings"][0]
    assert f.check_id == "TAX_RATE_MISMATCH"
    assert f.computed_details["effective_tax_pct"] == 18.0
    assert f.computed_details["configured_expected_rates"] == [0.05, 0.0]
    assert f.computed_details["tax_discrepancy_rupees"] == 1475.5


def test_validate_tax_rates_compliant():
    # 5% GST
    res = validate_tax_rates(11350.0, 567.5)
    assert res["valid"] is True
    assert len(res["findings"]) == 0

    # 0% exempt
    res_exempt = validate_tax_rates(11350.0, 0.0)
    assert res_exempt["valid"] is True
    assert len(res_exempt["findings"]) == 0


def test_check_dates_future():
    res = check_dates("2031-03-14T09:00:00", "2031-03-16T12:00:00")
    findings = res["findings"]
    assert any(f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE" for f in findings)
    future_f = [f for f in findings if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"][0]
    assert future_f.severity == Severity.CRITICAL


def test_check_dates_reversed():
    # Admission after discharge: 12-Sep admission, 10-Sep discharge
    res = check_dates("2026-09-12T12:00:00", "2026-09-10T09:00:00")
    assert res["valid"] is False
    assert any(f.check_id == "REVERSED_HOSPITALIZATION_DATES" for f in res["findings"])
    rev_f = [f for f in res["findings"] if f.check_id == "REVERSED_HOSPITALIZATION_DATES"][0]
    assert rev_f.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# Integration tests on Eval Bills V2
# ---------------------------------------------------------------------------

def test_eval_clean_base_bill():
    """Base bill (Lotus Care, Kochi, E11.9, total ₹11,917.50) must stay APPROVE."""
    claim = Claim(
        claim_id="CLM-EVAL-BASE-CLEAN",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",
        subtotal=11350.0,
        tax=567.5,
        total_claimed=11917.5,
        line_items=[
            LineItem(description="Consultation charges", qty=2, unit_price=800.0, amount=1600.0, page=1, source="form"),
            LineItem(description="HbA1c test", qty=1, unit_price=450.0, amount=450.0, page=1, source="form"),
            LineItem(description="Lipid profile", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="Insulin therapy 3x1200", qty=3, unit_price=1200.0, amount=3600.0, page=1, source="form"),
            LineItem(description="Ward bed charges", qty=2, unit_price=2500.0, amount=5000.0, page=1, source="form"),
        ]
    )
    findings = analyze_policy_and_arithmetic(claim)
    assert not any(f.check_id in ("DUPLICATE_LINE_ITEM", "ROOM_DAYS_EXCEED_STAY", "TAX_RATE_MISMATCH", "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK") for f in findings)
    risk, verdict = score_findings(findings, ml_probability=0.04)
    assert verdict == Verdict.APPROVE
    assert risk < 30


def test_eval_clean_expensive_bill():
    """Clean expensive bill (Sahyadri, Pune, K80.2, total ₹68,250) must stay APPROVE."""
    claim = Claim(
        claim_id="CLM-EVAL-EXPENSIVE-CLEAN",
        diagnosis_code="K80.2",
        policy_id="POL-AROGYA-SANJEEVANI-001",
        claimant=Claimant(claimant_id="CLMNT-PUNE-1", name="Meera Joshi", phone="9876543211", bank_account_hash="h2"),
        provider=Provider(hospital_id="HOSP-PUNE-1", name="Sahyadri Multispeciality Hospital", city="Pune"),
        admission_ts="2026-08-10T09:00:00",
        discharge_ts="2026-08-13T12:00:00",
        subtotal=65000.0,
        tax=3250.0,
        total_claimed=68250.0,
        line_items=[
            LineItem(description="Ward bed charges", qty=3, unit_price=4500.0, amount=13500.0, page=1, source="form"),
            LineItem(description="Operation Theatre (OT) charges", qty=1, unit_price=20000.0, amount=20000.0, page=1, source="form"),
            LineItem(description="Surgeon fee", qty=1, unit_price=22000.0, amount=22000.0, page=1, source="form"),
            LineItem(description="Anaesthesia charges", qty=1, unit_price=6000.0, amount=6000.0, page=1, source="form"),
            LineItem(description="Pharmacy & Consumables", qty=1, unit_price=3500.0, amount=3500.0, page=1, source="form"),
        ]
    )
    findings = analyze_policy_and_arithmetic(claim)
    assert not any(f.check_id in ("LINE_ITEM_PRICE_ABOVE_BENCHMARK", "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK", "TAX_RATE_MISMATCH") for f in findings)
    risk, verdict = score_findings(findings, ml_probability=0.06)
    assert verdict == Verdict.APPROVE
    assert risk < 30


def test_eval_duplicate_line_item():
    claim = Claim(
        claim_id="CLM-EVAL-DUP-ITEM",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",
        subtotal=14950.0,
        tax=747.5,
        total_claimed=15697.5,
        line_items=[
            LineItem(description="Consultation charges", qty=2, unit_price=800.0, amount=1600.0, page=1, source="form"),
            LineItem(description="HbA1c test", qty=1, unit_price=450.0, amount=450.0, page=1, source="form"),
            LineItem(description="Lipid profile", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="Insulin therapy 3x1200", qty=3, unit_price=1200.0, amount=3600.0, page=1, source="form"),
            LineItem(description="Insulin therapy 3x1200", qty=3, unit_price=1200.0, amount=3600.0, page=1, source="form"),  # duplicated
            LineItem(description="Ward bed charges", qty=2, unit_price=2500.0, amount=5000.0, page=1, source="form"),
        ]
    )
    findings = analyze_policy_and_arithmetic(claim)
    assert any(f.check_id == "DUPLICATE_LINE_ITEM" for f in findings)
    risk, verdict = score_findings(findings, ml_probability=0.35)
    assert verdict == Verdict.REVIEW


def test_eval_room_days_exceed_stay():
    claim = Claim(
        claim_id="CLM-EVAL-ROOM-DAYS",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",  # 2 nights stay
        subtotal=28850.0,
        tax=1442.5,
        total_claimed=30292.5,
        line_items=[
            LineItem(description="Consultation charges", qty=2, unit_price=800.0, amount=1600.0, page=1, source="form"),
            LineItem(description="HbA1c test", qty=1, unit_price=450.0, amount=450.0, page=1, source="form"),
            LineItem(description="Lipid profile", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="Insulin therapy 3x1200", qty=3, unit_price=1200.0, amount=3600.0, page=1, source="form"),
            LineItem(description="Ward bed charges", qty=9, unit_price=2500.0, amount=22500.0, page=1, source="form"),  # 9 days!
        ]
    )
    findings = analyze_policy_and_arithmetic(claim)
    assert any(f.check_id == "ROOM_DAYS_EXCEED_STAY" for f in findings)
    risk, verdict = score_findings(findings, ml_probability=0.45)
    assert verdict == Verdict.REVIEW


def test_eval_tax_rate_mismatch():
    claim = Claim(
        claim_id="CLM-EVAL-TAX-RATE",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",
        subtotal=11350.0,
        tax=2043.0,  # 18% GST instead of 5%
        total_claimed=13393.0,
        line_items=[
            LineItem(description="Consultation charges", qty=2, unit_price=800.0, amount=1600.0, page=1, source="form"),
            LineItem(description="HbA1c test", qty=1, unit_price=450.0, amount=450.0, page=1, source="form"),
            LineItem(description="Lipid profile", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="Insulin therapy 3x1200", qty=3, unit_price=1200.0, amount=3600.0, page=1, source="form"),
            LineItem(description="Ward bed charges", qty=2, unit_price=2500.0, amount=5000.0, page=1, source="form"),
        ]
    )
    findings = analyze_policy_and_arithmetic(claim)
    assert any(f.check_id == "TAX_RATE_MISMATCH" for f in findings)
    risk, verdict = score_findings(findings, ml_probability=0.30)
    assert verdict == Verdict.REVIEW


def test_eval_price_inflated_bill():
    """Gastroenteritis A09 in Pune with tripled unit prices -> flags LINE_ITEM and TOTAL benchmarks, REVIEW >= 45."""
    claim = Claim(
        claim_id="CLM-EVAL-PRICE-INFLATED",
        diagnosis_code="A09",
        policy_id="POL-AROGYA-SANJEEVANI-001",
        claimant=Claimant(claimant_id="CLMNT-PUNE-2", name="Suresh Kulkarni", phone="9876543212", bank_account_hash="h3"),
        provider=Provider(hospital_id="HOSP-PUNE-2", name="Sahyadri Multispeciality Hospital", city="Pune"),
        admission_ts="2026-09-05T10:00:00",
        discharge_ts="2026-09-08T14:00:00",
        subtotal=34800.0,
        tax=1740.0,
        total_claimed=36540.0,
        line_items=[
            LineItem(description="Ward bed charges (3 nights)", qty=3, unit_price=6000.0, amount=18000.0, page=1, source="form"),  # tripled from 2000
            LineItem(description="Consultation charges", qty=3, unit_price=1800.0, amount=5400.0, page=1, source="form"),           # tripled from 600
            LineItem(description="IV fluids & Electrolytes", qty=4, unit_price=1050.0, amount=4200.0, page=1, source="form"),         # tripled from 350
            LineItem(description="Diagnostic lab tests (Stool/CBC)", qty=1, unit_price=2700.0, amount=2700.0, page=1, source="form"), # tripled from 900
            LineItem(description="Medicines & Antibiotics", qty=1, unit_price=4500.0, amount=4500.0, page=1, source="form"),        # tripled from 1500
        ]
    )
    findings = analyze_policy_and_arithmetic(claim)
    assert any(f.check_id == "LINE_ITEM_PRICE_ABOVE_BENCHMARK" for f in findings)
    assert any(f.check_id == "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK" for f in findings)
    risk, verdict = score_findings(findings, ml_probability=0.45)
    assert verdict == Verdict.REVIEW
    assert risk >= 45


def test_eval_reversed_dates_bill():
    """Admission after discharge must trigger REVERSED_HOSPITALIZATION_DATES and REJECT >= 85."""
    claim = Claim(
        claim_id="CLM-EVAL-REVERSED-DATES",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2026-09-12T12:00:00",  # Admission AFTER discharge!
        discharge_ts="2026-09-10T09:00:00",
        subtotal=11350.0,
        tax=567.5,
        total_claimed=11917.5,
        line_items=[
            LineItem(description="Consultation charges", qty=2, unit_price=800.0, amount=1600.0, page=1, source="form"),
            LineItem(description="HbA1c test", qty=1, unit_price=450.0, amount=450.0, page=1, source="form"),
            LineItem(description="Lipid profile", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="Insulin therapy 3x1200", qty=3, unit_price=1200.0, amount=3600.0, page=1, source="form"),
            LineItem(description="Ward bed charges", qty=2, unit_price=2500.0, amount=5000.0, page=1, source="form"),
        ]
    )
    findings = analyze_policy_and_arithmetic(claim)
    assert any(f.check_id == "REVERSED_HOSPITALIZATION_DATES" for f in findings)
    risk, verdict = score_findings(findings, ml_probability=0.12)
    assert verdict == Verdict.REJECT
    assert risk >= 85
