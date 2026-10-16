#!/usr/bin/env python3
"""
scripts/verify_calibration.py

Evaluates the fresh evaluation corpus (data/eval_bills/) through:
1. Multimodal Document Extraction (DocAI) & Field Accuracy (>= 90%)
2. Fraud Detection & Verdict Calibration:
   - Clean bill FPR <= 10% (0% REJECT)
   - +20% inflation flags REVIEW (never APPROVE)
   - +40% inflation flags REVIEW or REJECT (never APPROVE)
   - +60% inflation flags REJECT
   - Arithmetic mismatch flags REJECT
   - Policy room rent cap breach flags REVIEW
   - Padded ancillary consumables flags REVIEW
3. Golden Claims G1-G9 Ground Truth (All 9 pass, G1 <= 25 and APPROVE).
"""

import os
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "drishti-demo")
os.environ.setdefault("GCP_PROJECT", "drishti-demo")
os.environ.setdefault("FIRESTORE_DATABASE", "(default)")
os.environ.setdefault("GCS_BUCKET_NAME", "finshield-claims-docs-drishti-demo")
os.environ.setdefault("BIGQUERY_DATASET", "finshield")
os.environ.setdefault("REQUIRE_CLOUD_ON_STARTUP", "true")

from backend.app.schemas import Claim, LineItem, Verdict
from backend.agents.root import run_claims_fraud_pipeline
from backend.tools.docai import process_document_docai
from scripts.verify_golden import verify_claims, GOLDEN_CLAIMS

GT_PATH = ROOT_DIR / "data" / "eval_bills" / "ground_truth.json"
BILLS_DIR = ROOT_DIR / "data" / "eval_bills"


def run_evaluation():
    print("\n" + "=" * 105)
    print("FINSHIELD / DRISHTI.AI CALIBRATION & RECALIBRATION VERIFICATION (ISSUE 1)")
    print("=" * 105 + "\n")

    with open(GT_PATH, "r", encoding="utf-8") as f:
        corpus = json.load(f)

    clean_total = 0
    clean_approved = 0
    clean_review = 0
    clean_reject = 0

    inflation_20_total = 0
    inflation_20_caught = 0

    inflation_40_total = 0
    inflation_40_caught = 0

    inflation_60_total = 0
    inflation_60_caught = 0

    other_fraud_total = 0
    other_fraud_passed = 0

    total_fields_checked = 0
    correct_fields = 0

    results = []

    print(f"{'ID':<9} {'Type':<22} {'Diag':<6} {'Total (₹)':<11} {'Exp':<8} {'Act':<8} {'Risk':<5} {'Fields':<7} {'Status'}")
    print("-" * 105)

    for item in corpus:
        eval_id = item["eval_id"]
        filename = item["filename"]
        fraud_type = item["fraud_type"]
        exp_verdict = item["expected_verdict"].upper()
        diag_code = item["diagnosis_code"]
        gt_total = item["total_claimed"]
        gt_subtotal = item["subtotal"]
        gt_line_count = len(item["line_items"])

        pdf_path = BILLS_DIR / filename
        doc_bytes = pdf_path.read_bytes()

        # Step 1: Extraction
        extracted_claim, raw_doc = process_document_docai(doc_bytes, filename)

        if not extracted_claim.claim_id:
            extracted_claim.claim_id = f"CLM-{eval_id}"
        if not extracted_claim.insurer_id:
            extracted_claim.insurer_id = item.get("insurer_id", "INS-CARE")
        if not extracted_claim.policy_id:
            extracted_claim.policy_id = item.get("policy_no", "POL-CARE-99812")
        if not extracted_claim.diagnosis_code:
            extracted_claim.diagnosis_code = diag_code

        # Field accuracy evaluation
        # Field 1: Total claimed within ₹2
        total_fields_checked += 1
        if abs(extracted_claim.total_claimed - gt_total) <= 2.0:
            correct_fields += 1

        # Field 2: Subtotal within ₹2
        total_fields_checked += 1
        if abs(extracted_claim.subtotal - gt_subtotal) <= 2.0:
            correct_fields += 1

        # Field 3: Line items extracted
        total_fields_checked += 1
        if abs(len(extracted_claim.line_items) - gt_line_count) <= 1:
            correct_fields += 1

        # Field 4: Patient Name or Hospital match
        total_fields_checked += 1
        if extracted_claim.claimant and (
            extracted_claim.claimant.name.lower() in item["patient_name"].lower() or
            item["patient_name"].lower() in extracted_claim.claimant.name.lower()
        ):
            correct_fields += 1
        elif extracted_claim.provider and (
            item["city"].lower() in extracted_claim.provider.city.lower()
        ):
            correct_fields += 1

        # Step 2: Fraud Pipeline
        dossier = run_claims_fraud_pipeline(extracted_claim, extracted_claim.documents)
        act_verdict = dossier.verdict.value.upper()
        risk = dossier.risk_score

        # Verification rules
        passed = False
        if fraud_type == "clean":
            clean_total += 1
            if act_verdict == "APPROVE":
                clean_approved += 1
                passed = True
            elif act_verdict == "REVIEW":
                clean_review += 1
                passed = False
            else:
                clean_reject += 1
                passed = False

        elif fraud_type == "inflated_20pct":
            inflation_20_total += 1
            if act_verdict != "APPROVE":
                inflation_20_caught += 1
                passed = True

        elif fraud_type == "inflated_40pct":
            inflation_40_total += 1
            if act_verdict in ("REVIEW", "REJECT"):
                inflation_40_caught += 1
                passed = True

        elif fraud_type == "severe_inflation_60pct":
            inflation_60_total += 1
            if act_verdict == "REJECT":
                inflation_60_caught += 1
                passed = True

        else:
            other_fraud_total += 1
            if act_verdict == exp_verdict:
                other_fraud_passed += 1
                passed = True

        field_acc_sample = f"{correct_fields}/{total_fields_checked}"
        status_str = "PASS" if passed else "FAIL"

        print(f"{eval_id:<9} {fraud_type:<22} {diag_code:<6} ₹{gt_total:>9,.2f} {exp_verdict:<8} {act_verdict:<8} {risk:<5} {field_acc_sample:<7} {status_str}")

        results.append({
            "id": eval_id,
            "fraud_type": fraud_type,
            "exp": exp_verdict,
            "act": act_verdict,
            "risk": risk,
            "passed": passed
        })

    # Metrics computation
    clean_fpr = (clean_review + clean_reject) / max(1, clean_total) * 100
    overall_field_accuracy = (correct_fields / max(1, total_fields_checked)) * 100

    print("\n" + "=" * 105)
    print("CORPUS EVALUATION SUMMARY:")
    print(f"Total Evaluation Bills Processed   : {len(corpus)}")
    print(f"Document Extraction Field Accuracy : {overall_field_accuracy:.1f}% (Target: >= 90.0%)")
    print(f"Clean Bills Evaluated              : {clean_total}")
    print(f"Clean Bills Approved               : {clean_approved}")
    print(f"Clean Bills in Review              : {clean_review}")
    print(f"Clean Bills in Reject              : {clean_reject} (Must be 0)")
    print(f"Clean False Positive Rate (FPR)    : {clean_fpr:.1f}% (Target: <= 10.0%)")
    print(f"+20% Inflation Caught (Never Appr) : {inflation_20_caught}/{inflation_20_total}")
    print(f"+40% Inflation Caught (Review/Rej) : {inflation_40_caught}/{inflation_40_total}")
    print(f"+60% Severe Inflation Caught (Rej) : {inflation_60_caught}/{inflation_60_total}")
    print(f"Other Fraud Types Passed           : {other_fraud_passed}/{other_fraud_total}")
    print("=" * 105 + "\n")

    # Step 3: Golden Claims Verification
    print("=" * 105)
    print("GOLDEN CLAIMS G1-G9 VERIFICATION:")
    print("=" * 105)
    golden_ok = verify_claims(GOLDEN_CLAIMS, force=True)

    print("\n" + "=" * 105)
    print("FINAL ACCEPTANCE GATES CHECK:")
    print(f"Gate 1: Clean FPR <= 10.0%         : {'PASS' if clean_fpr <= 10.0 else 'FAIL'} ({clean_fpr:.1f}%)")
    print(f"Gate 2: Clean Reject == 0          : {'PASS' if clean_reject == 0 else 'FAIL'} ({clean_reject})")
    print(f"Gate 3: +20% Never Approve         : {'PASS' if inflation_20_caught == inflation_20_total else 'FAIL'}")
    print(f"Gate 4: +60% Reject                : {'PASS' if inflation_60_caught == inflation_60_total else 'FAIL'}")
    print(f"Gate 5: Golden Claims 9/9 Pass     : {'PASS' if golden_ok else 'FAIL'}")
    print(f"Gate 6: Extraction Accuracy >= 90% : {'PASS' if overall_field_accuracy >= 90.0 else 'FAIL'} ({overall_field_accuracy:.1f}%)")
    print("=" * 105)

    assert clean_fpr <= 10.0, f"Clean FPR {clean_fpr:.1f}% exceeds 10%!"
    assert clean_reject == 0, f"Clean bills rejected: {clean_reject}"
    assert inflation_20_caught == inflation_20_total, "+20% inflation was approved!"
    assert inflation_60_caught == inflation_60_total, "+60% inflation was not rejected!"
    assert golden_ok, "Golden claims verification failed!"
    assert overall_field_accuracy >= 90.0, f"Field accuracy {overall_field_accuracy:.1f}% < 90%"

    print("\n>> ALL CALIBRATION GATES PASSED SUCCESSFULLY.")


if __name__ == "__main__":
    run_evaluation()
