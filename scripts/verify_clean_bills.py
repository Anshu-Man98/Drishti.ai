#!/usr/bin/env python3
"""
scripts/verify_clean_bills.py

Live cloud verification script for clean bills in data/eval_bills_v3/.
Executes Document AI + Gemini Vision extraction, followed by the full
multi-agent claims fraud pipeline on Google Cloud (drishti-demo).
Verifies:
1. False-Positive Rate (FPR) <= 5% on all 17 bills (14 PDFs + 3 Photos) -> all APPROVE.
2. City extraction accuracy across all bills (including Dehradun and Indore).
3. Prints structured comparison table of expected vs actual.
"""

import os
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure required cloud environment defaults
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "drishti-demo")
os.environ.setdefault("GCP_PROJECT", "drishti-demo")
os.environ.setdefault("FIRESTORE_DATABASE", "(default)")
os.environ.setdefault("GCS_BUCKET_NAME", "finshield-claims-docs-drishti-demo")
os.environ.setdefault("BIGQUERY_DATASET", "finshield")
os.environ.setdefault("REQUIRE_CLOUD_ON_STARTUP", "true")

from backend.app.schemas import Claim, Verdict
from backend.tools.docai import process_document_docai, clear_docai_extraction_cache
from backend.agents.root import run_claims_fraud_pipeline

EVAL_DIR = ROOT_DIR / "data" / "eval_bills_v3"
GT_PATH = EVAL_DIR / "ground_truth.json"


def main():
    if not GT_PATH.exists():
        print(f"Ground truth not found at {GT_PATH}")
        sys.exit(1)

    with open(GT_PATH) as f:
        ground_truth = json.load(f)

    print("=" * 110)
    print("FINSHIELD / DRISHTI AI — CLEAN BILLS VERIFICATION SUITE (V3 CORPUS)")
    print(f"Target: Real Cloud (drishti-demo) | Total Test Bills: {len(ground_truth)}")
    print("=" * 110 + "\n")

    clear_docai_extraction_cache()

    results = []
    total_bills = len(ground_truth)
    approved_count = 0
    fp_count = 0
    correct_city_count = 0

    for filename, meta in ground_truth.items():
        claim_id = meta["claim_id"]
        file_path = EVAL_DIR / filename
        expected_verdict = meta.get("expected_verdict", "APPROVE")
        expected_city = meta.get("city", "")

        print(f"Processing {filename} ({claim_id}) ... ", end="", flush=True)

        if not file_path.exists():
            print(f"[FAIL: File missing]")
            results.append({
                "filename": filename,
                "claim_id": claim_id,
                "type": "photo" if meta.get("is_photo") else "pdf",
                "expected": expected_verdict,
                "actual": "MISSING",
                "risk": 0,
                "city": "N/A",
                "findings": "File not found",
                "pass": False
            })
            continue

        file_bytes = file_path.read_bytes()

        try:
            # 1. Extraction via Document AI + Gemini Vision
            claim, ents = process_document_docai(file_bytes, filename=filename, claim_id=claim_id)

            # Ensure policy & insurer exist for scoring
            if not claim.insurer_id:
                claim.insurer_id = "INS-STAR"
            if not claim.policy_id:
                claim.policy_id = "POL-STAR-88123"

            actual_city = claim.provider.city if (claim.provider and claim.provider.city) else "Unknown"
            city_matched = expected_city.lower() in actual_city.lower() if expected_city else False
            if city_matched:
                correct_city_count += 1

            # 2. Multi-agent evaluation pipeline
            dossier = run_claims_fraud_pipeline(claim)
            actual_verdict = dossier.verdict.value.upper()
            risk_score = dossier.risk_score

            passed = (actual_verdict == expected_verdict)
            if actual_verdict == "APPROVE":
                approved_count += 1
            else:
                fp_count += 1

            findings_summary = ", ".join(f.check_id for f in dossier.findings if getattr(f, "severity", None) in ("high", "critical", "medium"))
            if not findings_summary:
                findings_summary = f"{len(dossier.findings)} low/info flags" if dossier.findings else "Clean"

            print(f"-> Actual: {actual_verdict} (Risk: {risk_score}, City: {actual_city}) [{'PASS' if passed else 'FAIL'}]")

            results.append({
                "filename": filename,
                "claim_id": claim_id,
                "type": "Photo (PNG)" if meta.get("is_photo") else "PDF",
                "expected": expected_verdict,
                "actual": actual_verdict,
                "risk": risk_score,
                "city": actual_city,
                "city_matched": city_matched,
                "findings": findings_summary,
                "pass": passed
            })

        except Exception as e:
            print(f"-> ERROR: {e}")
            fp_count += 1
            results.append({
                "filename": filename,
                "claim_id": claim_id,
                "type": "photo" if meta.get("is_photo") else "pdf",
                "expected": expected_verdict,
                "actual": "ERROR",
                "risk": 99,
                "city": "ERROR",
                "city_matched": False,
                "findings": str(e),
                "pass": False
            })

    # Print Table
    print("\n" + "-" * 110)
    print(f"| {'Filename':<30} | {'Claim ID':<20} | {'Type':<12} | {'Exp':<7} | {'Act':<7} | {'Risk':<5} | {'City':<12} | {'Status':<6} |")
    print("-" * 110)
    for r in results:
        status_label = "PASS" if r["pass"] else "FAIL"
        print(f"| {r['filename']:<30} | {r['claim_id']:<20} | {r['type']:<12} | {r['expected']:<7} | {r['actual']:<7} | {r['risk']:<5} | {r['city']:<12} | {status_label:<6} |")
    print("-" * 110)

    fpr = (fp_count / total_bills) * 100.0
    city_acc = (correct_city_count / total_bills) * 100.0

    print(f"\nFinal Summary:")
    print(f"  - Total Clean Bills Tested: {total_bills}")
    print(f"  - Clean Bills Approved:     {approved_count} / {total_bills}")
    print(f"  - False Positives:          {fp_count} / {total_bills}")
    print(f"  - False Positive Rate (FPR): {fpr:.2f}% (Requirement: <= 5.0%)")
    print(f"  - City Extraction Accuracy:  {correct_city_count} / {total_bills} ({city_acc:.1f}%)")

    if fpr <= 5.0 and approved_count == total_bills:
        print("\nALL CLEAN BILLS ACCEPTANCE CRITERIA MET (FPR <= 5.0%).")
        sys.exit(0)
    else:
        print(f"\nACCEPTANCE CRITERIA FAILED (FPR {fpr:.2f}% > 5.0%).")
        sys.exit(1)


if __name__ == "__main__":
    main()
