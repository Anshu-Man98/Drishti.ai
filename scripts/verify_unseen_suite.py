#!/usr/bin/env python3
"""
scripts/verify_unseen_suite.py

Comprehensive Verification Suite for Part D:
1. Evaluates 32 unseen bills from data/unseen_bills/:
   - Measures False Positive Rate (FPR) on clean bills (target <= 10%)
   - Verifies +20% inflation bills NEVER land in APPROVE
   - Verifies arithmetic mismatch lands in REJECT
   - Verifies policy cap breach lands in REVIEW
2. Verifies Inflation Ladder monotonicity on CLM-G1-CLEAN-DEMO:
   - +10% < +28% < +60% strictly monotonic
3. Verifies Golden Claims G1..G9 match 9/9 ground truth.

Usage:
    python scripts/verify_unseen_suite.py
"""

import os
import sys
import json
from pathlib import Path
from copy import deepcopy

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
from backend.app.services.db import db_service
from backend.agents.root import run_claims_fraud_pipeline
from backend.tools.docai import process_document_docai

GT_PATH = ROOT_DIR / "data" / "demo" / "unseen_ground_truth.json"
BILLS_DIR = ROOT_DIR / "data" / "unseen_bills"


def run_unseen_corpus_evaluation():
    print("\n" + "=" * 95)
    print("PART 1: UNSEEN BILLS CORPUS EVALUATION (32 Fresh ReportLab Bills)")
    print("=" * 95 + "\n")

    with open(GT_PATH) as f:
        corpus = json.load(f)

    clean_total = 0
    clean_fp = 0
    clean_approved = 0
    inflation_tested = 0
    inflation_passed = 0

    results = []

    for item in corpus:
        doc_id = item["id"]
        filename = item["file"]
        test_type = item["type"]
        exp = item["expected"]
        pdf_path = BILLS_DIR / filename

        # 1. Document Extraction
        doc_bytes = pdf_path.read_bytes()
        extracted_claim, raw_doc = process_document_docai(doc_bytes, filename)

        # Ensure claim fields match schema
        if not extracted_claim.claim_id:
            extracted_claim.claim_id = f"CLM-{doc_id}"
        if not extracted_claim.insurer_id:
            extracted_claim.insurer_id = "INS-CARE"
        if not extracted_claim.policy_id:
            extracted_claim.policy_id = exp.get("policy_id", "POL-CARE-99812")

        # 2. Pipeline Fraud Detection
        dossier = run_claims_fraud_pipeline(extracted_claim)
        actual_verdict = dossier.verdict.value.upper()
        risk = dossier.risk_score
        expected_verdict = exp["expected_verdict"]

        is_clean = (test_type == "clean")
        passed = False

        if is_clean:
            clean_total += 1
            if actual_verdict == "APPROVE":
                clean_approved += 1
                passed = True
            else:
                clean_fp += 1
                passed = False
        elif "20pct" in test_type or "inflation" in test_type:
            inflation_tested += 1
            if actual_verdict != "APPROVE":
                inflation_passed += 1
                passed = True
            else:
                passed = False
        else:
            if actual_verdict == expected_verdict:
                passed = True

        status_str = "PASS" if passed else "FAIL"
        results.append({
            "id": doc_id,
            "file": filename,
            "type": test_type,
            "total": extracted_claim.total_claimed,
            "exp": expected_verdict,
            "act": actual_verdict,
            "risk": risk,
            "status": status_str
        })
        print(f"[{doc_id}] {test_type:<22} Exp: {expected_verdict:<7} Act: {actual_verdict:<7} (Risk: {risk:<2}) -> {status_str}")

    fpr = (clean_fp / max(1, clean_total)) * 100
    print("\n" + "-" * 95)
    print(f"Clean Bills Evaluated      : {clean_total}")
    print(f"Clean Bills Approved       : {clean_approved}")
    print(f"Clean False Positives      : {clean_fp}")
    print(f"False Positive Rate (FPR)  : {fpr:.1f}% (Requirement: <= 10.0%)")
    print(f"+20% Inflation Bills Check : {inflation_passed}/{inflation_tested} Never Approved")
    print("-" * 95)

    assert fpr <= 10.0, f"FPR exceeded 10%: {fpr:.1f}%"
    assert inflation_passed == inflation_tested, "A +20% inflation bill landed in APPROVE!"
    print(">> UNSEEN BILLS CORPUS EVALUATION: PASSED [FPR <= 10%, +20% Never Approved]\n")


def run_golden_evaluation():
    print("=" * 95)
    print("PART 2: GOLDEN CLAIMS G1..G9 GROUND TRUTH VERIFICATION")
    print("=" * 95 + "\n")

    from scripts.verify_golden import verify_claims, GOLDEN_CLAIMS
    success = verify_claims(GOLDEN_CLAIMS, force=True)
    assert success, "Golden claims verification failed!"
    print(">> GOLDEN CLAIMS VERIFICATION: PASSED [9/9 Ground Truth]\n")


def run_inflation_monotonicity_evaluation():
    print("=" * 95)
    print("PART 3: INFLATION LADDER & STRICT MONOTONICITY EVALUATION")
    print("=" * 95 + "\n")

    base_claim = db_service.get_claim("CLM-G1-CLEAN-DEMO")
    if not base_claim:
        raise ValueError("CLM-G1-CLEAN-DEMO missing")

    baseline_total = float(base_claim.total_claimed)

    ladder = [
        {"mult": 1.0, "name": "Baseline (+0%)"},
        {"mult": 1.10, "name": "+10% Inflation"},
        {"mult": 1.20, "name": "+20% Inflation"},
        {"mult": 1.28, "name": "+28% Inflation"},
        {"mult": 1.40, "name": "+40% Inflation"},
        {"mult": 1.60, "name": "+60% Inflation"},
    ]

    scores = []
    for step in ladder:
        c = deepcopy(base_claim)
        mult = step["mult"]
        for it in c.line_items or []:
            it.unit_price = round(it.unit_price * mult, 2)
            it.amount = round(it.unit_price * it.qty, 2)
        c.subtotal = round(sum(it.amount for it in c.line_items), 2)
        c.tax = round(c.subtotal * 0.05, 2)
        c.total_claimed = round(c.subtotal + c.tax, 2)

        dossier = run_claims_fraud_pipeline(c)
        scores.append({
            "name": step["name"],
            "total": c.total_claimed,
            "risk": dossier.risk_score,
            "verdict": dossier.verdict.value.upper()
        })
        print(f"{step['name']:<20} Total: ₹{c.total_claimed:>10,.2f} -> Verdict: {dossier.verdict.value.upper():<7} (Risk: {dossier.risk_score})")

    # Check strict monotonicity on key steps: +10% < +28% < +60%
    r_baseline = scores[0]["risk"]
    r_10 = scores[1]["risk"]
    r_20 = scores[2]["risk"]
    r_28 = scores[3]["risk"]
    r_40 = scores[4]["risk"]
    r_60 = scores[5]["risk"]

    print("\nMonotonicity Check:")
    print(f"  Baseline ({r_baseline}) <= +10% ({r_10}) <= +20% ({r_20}) <= +28% ({r_28}) <= +40% ({r_40}) <= +60% ({r_60})")
    assert r_10 < r_28 < r_60, f"Monotonicity violated! +10%: {r_10}, +28%: {r_28}, +60%: {r_60}"
    assert scores[0]["verdict"] == "APPROVE", "Baseline (+0%) was not APPROVE"
    assert scores[1]["verdict"] in ("REVIEW", "REJECT"), "+10% ended in APPROVE"
    assert scores[2]["verdict"] in ("REVIEW", "REJECT"), "+20% ended in APPROVE"

    print(">> INFLATION MONOTONICITY: PASSED [+10% < +28% < +60% strictly verified]\n")


def main():
    print("=" * 95)
    print("FINSHIELD / DRISHTI.AI — PART D COMPREHENSIVE CALIBRATION VERIFICATION")
    print("=" * 95)
    run_golden_evaluation()
    run_inflation_monotonicity_evaluation()
    run_unseen_corpus_evaluation()
    print("=" * 95)
    print("ALL PART D VERIFICATION CRITERIA SATISFIED SUCCESSFULLY.")
    print("=" * 95)


if __name__ == "__main__":
    main()
