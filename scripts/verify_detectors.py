#!/usr/bin/env python3
"""
scripts/verify_detectors.py

Evaluates the 9 QA Fix 2 test bills generated in data/eval_bills_v2 against
data/eval_bills_v2/ground_truth.json.
Validates:
  - Exact or compliant verdicts (APPROVE / REVIEW / REJECT)
  - Detection of DUPLICATE_LINE_ITEM, ROOM_DAYS_EXCEED_STAY, FUTURE_OR_IMPLAUSIBLE_DATE,
    TAX_RATE_MISMATCH, LINE_ITEM_PRICE_ABOVE_BENCHMARK, TOTAL_ABOVE_DIAGNOSIS_BENCHMARK,
    REVERSED_HOSPITALIZATION_DATES
  - Absence of false positive findings on clean bills
  - Risk thresholds (e.g. clean < 30, inflated >= 45, reversed >= 85)
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.schemas import Claim, LineItem, Claimant, Provider, Verdict
from backend.agents.policy import analyze_policy_and_arithmetic
from backend.tools.scoring import score_findings

EVAL_CASES = {
    "clean_base_bill": Claim(
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
    ),
    "clean_expensive_bill": Claim(
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
    ),
    "clean_rotated_noisy_photo": Claim(
        claim_id="CLM-EVAL-ROTATED-PHOTO",
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
    ),
    "duplicate_line_item": Claim(
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
    ),
    "room_days_exceed_stay": Claim(
        claim_id="CLM-EVAL-ROOM-DAYS",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",
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
    ),
    "future_date_bill": Claim(
        claim_id="CLM-EVAL-FUTURE-DATE",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2031-03-14T09:00:00",  # Future year 2031
        discharge_ts="2031-03-16T12:00:00",
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
    ),
    "tax_rate_mismatch": Claim(
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
    ),
    "price_inflated_bill": Claim(
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
            LineItem(description="Ward bed charges (3 nights)", qty=3, unit_price=6000.0, amount=18000.0, page=1, source="form"),
            LineItem(description="Consultation charges", qty=3, unit_price=1800.0, amount=5400.0, page=1, source="form"),
            LineItem(description="IV fluids & Electrolytes", qty=4, unit_price=1050.0, amount=4200.0, page=1, source="form"),
            LineItem(description="Diagnostic lab tests (Stool/CBC)", qty=1, unit_price=2700.0, amount=2700.0, page=1, source="form"),
            LineItem(description="Medicines & Antibiotics", qty=1, unit_price=4500.0, amount=4500.0, page=1, source="form"),
        ]
    ),
    "reversed_dates_bill": Claim(
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
    ),
    "subtle_arithmetic_mismatch": Claim(
        claim_id="CLM-EVAL-SUBTLE-MATH",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",
        subtotal=11850.0,  # ₹500 mismatch with sum of line items (11350)
        tax=567.5,
        total_claimed=12417.5,
        line_items=[
            LineItem(description="Consultation charges", qty=2, unit_price=800.0, amount=1600.0, page=1, source="form"),
            LineItem(description="HbA1c test", qty=1, unit_price=450.0, amount=450.0, page=1, source="form"),
            LineItem(description="Lipid profile", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="Insulin therapy 3x1200", qty=3, unit_price=1200.0, amount=3600.0, page=1, source="form"),
            LineItem(description="Ward bed charges", qty=2, unit_price=2500.0, amount=5000.0, page=1, source="form"),
        ]
    ),
    "canva_clean_amounts": Claim(
        claim_id="CLM-EVAL-CANVA-CLEAN",
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
    ),
    "missing_total_bill": Claim(
        claim_id="CLM-EVAL-MISSING-TOTAL",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-KOCH-1", name="Lotus Care Hospital", city="Kochi"),
        admission_ts="2026-09-10T09:00:00",
        discharge_ts="2026-09-12T12:00:00",
        subtotal=11350.0,
        tax=567.5,
        total_claimed=None,
        line_items=[
            LineItem(description="Consultation charges", qty=2, unit_price=800.0, amount=1600.0, page=1, source="form"),
            LineItem(description="HbA1c test", qty=1, unit_price=450.0, amount=450.0, page=1, source="form"),
            LineItem(description="Lipid profile", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="Insulin therapy 3x1200", qty=3, unit_price=1200.0, amount=3600.0, page=1, source="form"),
            LineItem(description="Ward bed charges", qty=2, unit_price=2500.0, amount=5000.0, page=1, source="form"),
        ]
    ),
    "restaurant_invoice": Claim(
        claim_id="CLM-EVAL-RESTAURANT",
        diagnosis_code=None,
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-KOCH-1", name="Kavita Menon", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-REST-1", name="Spice Garden Bistro", city="Kochi"),
        subtotal=1780.0,
        tax=89.0,
        total_claimed=1869.0,
        line_items=[
            LineItem(description="Paneer Tikka Platter", qty=2, unit_price=350.0, amount=700.0, page=1, source="form"),
            LineItem(description="Butter Garlic Naan", qty=4, unit_price=70.0, amount=280.0, page=1, source="form"),
            LineItem(description="Special Veg Dum Biryani", qty=2, unit_price=400.0, amount=800.0, page=1, source="form"),
        ]
    ),
    "uti_bill_with_total": Claim(
        claim_id="CLM-EVAL-UTI-WITH-TOTAL",
        diagnosis_code="N39.0",
        policy_id="POL-STAR-88123",
        claimant=Claimant(claimant_id="CLMNT-DDN-1", name="Amit Sharma", phone="9876543213", bank_account_hash="h4"),
        provider=Provider(hospital_id="HOSP-DDN-1", name="Doon Valley Hospital", city="Dehradun"),
        admission_ts="2026-10-15T10:00:00",
        discharge_ts="2026-10-17T11:00:00",
        subtotal=9100.0,
        tax=455.0,
        total_claimed=9555.0,
        field_sources={"total_claimed": "form"},
        metadata={"has_printed_total": True},
        line_items=[
            LineItem(description="Ward bed charges", qty=2, unit_price=2200.0, amount=4400.0, page=1, source="form"),
            LineItem(description="Consultation", qty=2, unit_price=500.0, amount=1000.0, page=1, source="form"),
            LineItem(description="Urine culture", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="IV antibiotics", qty=6, unit_price=300.0, amount=1800.0, page=1, source="form"),
            LineItem(description="Ultrasound abdomen", qty=1, unit_price=1200.0, amount=1200.0, page=1, source="form"),
        ]
    ),
    "uti_bill_without_total": Claim(
        claim_id="CLM-EVAL-UTI-NO-TOTAL",
        diagnosis_code="N39.0",
        policy_id="POL-STAR-88123",
        claimant=Claimant(claimant_id="CLMNT-DDN-1", name="Amit Sharma", phone="9876543213", bank_account_hash="h4"),
        provider=Provider(hospital_id="HOSP-DDN-1", name="Doon Valley Hospital", city="Dehradun"),
        admission_ts="2026-10-15T10:00:00",
        discharge_ts="2026-10-17T11:00:00",
        subtotal=9100.0,
        tax=455.0,
        total_claimed=9555.0,
        field_sources={"total_claimed": "derived"},
        metadata={"has_printed_total": False, "derived_total": 9555.0, "extraction_incomplete": True},
        line_items=[
            LineItem(description="Ward bed charges", qty=2, unit_price=2200.0, amount=4400.0, page=1, source="form"),
            LineItem(description="Consultation", qty=2, unit_price=500.0, amount=1000.0, page=1, source="form"),
            LineItem(description="Urine culture", qty=1, unit_price=700.0, amount=700.0, page=1, source="form"),
            LineItem(description="IV antibiotics", qty=6, unit_price=300.0, amount=1800.0, page=1, source="form"),
            LineItem(description="Ultrasound abdomen", qty=1, unit_price=1200.0, amount=1200.0, page=1, source="form"),
        ]
    ),
}


def main():
    gt_path = ROOT_DIR / "data" / "eval_bills_v2" / "ground_truth.json"
    if not gt_path.exists():
        print(f"Error: {gt_path} not found.")
        sys.exit(1)

    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    print("\n" + "=" * 98)
    print("FINSHIELD / DRISHTI.AI — QA FIX 2 & 3 EVALUATION (13 Eval Bills)")
    print("=" * 98)
    print(f"{'Case Name':<28} | {'Exp Verdict':<11} | {'Act Verdict':<11} | {'Risk':<5} | {'Status':<6} | Findings")
    print("-" * 98)

    passed_count = 0
    total_count = len(EVAL_CASES)

    for case_name, claim in EVAL_CASES.items():
        gt = ground_truth.get(case_name, {})
        exp_verdict = gt.get("expected_verdict", "approve").upper()
        req_findings = gt.get("required_findings", [])
        forb_findings = gt.get("forbidden_findings", [])
        exp_risk_min = gt.get("expected_risk_min", 0)
        exp_risk_max = gt.get("expected_risk_max", 100)
        exp_status = gt.get("expected_status")

        findings = analyze_policy_and_arithmetic(claim)

        # Include forensic metadata check for canva test case
        if case_name == "canva_clean_amounts":
            from backend.tools.forensics_tools import pdf_metadata_check
            pdf_path = ROOT_DIR / "data" / "eval_bills_v2" / "canva_clean_amounts.pdf"
            if pdf_path.exists():
                _, meta_f = pdf_metadata_check(pdf_path.read_bytes(), doc_id="DOC-CANVA")
                findings.extend(meta_f)

        finding_ids = [f.check_id for f in findings]

        # Use baseline ml probability unless claim has deception
        base_ml = 0.05
        if any(f.severity.value == "critical" for f in findings):
            base_ml = 0.45

        risk_score, act_verdict_enum = score_findings(findings, ml_probability=base_ml)
        act_verdict = act_verdict_enum.value.upper()

        # Check conditions
        verdict_ok = (act_verdict == exp_verdict)
        req_ok = all(rf in finding_ids for rf in req_findings)
        forb_ok = not any(ff in finding_ids for ff in forb_findings)
        risk_ok = (exp_risk_min <= risk_score <= exp_risk_max)

        if exp_status:
            from backend.tools.scoring import is_incomplete_analysis_condition
            act_status = "incomplete" if any(is_incomplete_analysis_condition(f) for f in findings) else "complete"
            status_ok = (act_status == exp_status)
        else:
            status_ok = True

        case_ok = verdict_ok and req_ok and forb_ok and risk_ok and status_ok
        if case_ok:
            passed_count += 1
            status_str = "PASS"
        else:
            status_str = "FAIL"

        key_findings_str = ", ".join(finding_ids) if finding_ids else "(Clean / None)"
        if len(key_findings_str) > 28:
            key_findings_str = key_findings_str[:25] + "..."

        print(f"{case_name:<28} | {exp_verdict:<11} | {act_verdict:<11} | {risk_score:<5} | {status_str:<6} | {key_findings_str}")

    print("-" * 98)
    print(f"Summary: {passed_count}/{total_count} evaluation cases passed.\n")

    if passed_count < total_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
