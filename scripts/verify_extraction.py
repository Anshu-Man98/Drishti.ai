"""
Automated Verification Script for Document Extraction on Unseen Hospital Bills.
Runs live Document AI + Gemini multimodal vision pipeline across the unseen test corpus,
compares against ground truth, and reports field-level precision and recall.
Target: >= 90% field-level accuracy across claimant, hospital, city, dates, line items, totals.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.tools.docai import process_document_docai
from backend.agents.root import run_claims_fraud_pipeline

GT_PATH = PROJECT_ROOT / "data" / "demo" / "unseen_ground_truth.json"
BILLS_DIR = PROJECT_ROOT / "data" / "unseen_bills"


def evaluate_field(actual: Any, expected: Any, field_name: str) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False

    if field_name in ("subtotal", "tax", "total_claimed"):
        try:
            return abs(float(actual) - float(expected)) <= 1.0
        except Exception:
            return False

    if field_name == "line_items_count":
        return int(actual) == int(expected)

    if field_name in ("hospital_name", "claimant_name", "city"):
        # Substring / partial match tolerance for hospital legal entity prefixes
        act_str = str(actual).lower().strip()
        exp_str = str(expected).lower().strip()
        return exp_str in act_str or act_str in exp_str

    if field_name in ("doctor_id", "diagnosis_code"):
        return str(expected).lower().strip() in str(actual).lower().strip()

    if field_name in ("admission_date", "discharge_date"):
        if hasattr(actual, "strftime"):
            act_str = actual.strftime("%d-%b-%Y").lower()
        else:
            act_str = str(actual).lower()
        exp_str = str(expected).lower().strip()
        return exp_str in act_str or act_str in exp_str

    return str(actual).strip() == str(expected).strip()


def main():
    if not GT_PATH.exists():
        print(f"Ground truth file not found at {GT_PATH}")
        sys.exit(1)

    with open(GT_PATH) as f:
        corpus = json.load(f)

    print("=" * 110)
    print(f"FINSHIELD EXTRACTION VERIFICATION — UNSEEN BILLS CORPUS ({len(corpus)} Documents)")
    print("Document AI (Invoice Processor) + Gemini Multimodal Vision (Vertex AI: gemini-3.5-flash)")
    print("=" * 110)

    FIELDS = [
        "claimant_name",
        "hospital_name",
        "city",
        "doctor_id",
        "diagnosis_code",
        "admission_date",
        "discharge_date",
        "subtotal",
        "tax",
        "total_claimed",
        "line_items_count"
    ]

    field_stats: Dict[str, Dict[str, int]] = {
        f: {"tp": 0, "fp": 0, "fn": 0, "total": 0} for f in FIELDS
    }

    doc_results = []

    for item in corpus:
        doc_id = item["id"]
        filename = item["file"]
        expected = item["expected"]
        filepath = BILLS_DIR / filename

        print(f"\nProcessing {doc_id}: {filename} ({item['type']}) ...", end=" ", flush=True)

        if not filepath.exists():
            print(f"[ERROR: File not found: {filepath}]")
            continue

        raw_bytes = filepath.read_bytes()
        claim, ents = process_document_docai(raw_bytes, filename=filename, claim_id=f"CLM-{doc_id}")

        # Extract actual values
        actual_values = {
            "claimant_name": claim.claimant.name if claim.claimant else None,
            "hospital_name": claim.provider.name if claim.provider else None,
            "city": claim.provider.city if claim.provider else None,
            "doctor_id": claim.doctor_id,
            "diagnosis_code": claim.diagnosis_code,
            "admission_date": claim.admission_ts,
            "discharge_date": claim.discharge_ts,
            "subtotal": claim.subtotal,
            "tax": claim.tax,
            "total_claimed": claim.total_claimed,
            "line_items_count": len(claim.line_items)
        }

        # Check fields
        doc_field_matches = {}
        for f in FIELDS:
            exp_val = expected.get(f)
            act_val = actual_values.get(f)
            is_match = evaluate_field(act_val, exp_val, f)
            doc_field_matches[f] = is_match

            field_stats[f]["total"] += 1
            if is_match:
                field_stats[f]["tp"] += 1
            else:
                if act_val is not None:
                    field_stats[f]["fp"] += 1
                else:
                    field_stats[f]["fn"] += 1

        # Run pipeline to check final verdict
        dossier = run_claims_fraud_pipeline(claim)
        exp_verdict = expected.get("expected_verdict")
        actual_verdict = dossier.verdict.value.upper() if hasattr(dossier.verdict, "value") else str(dossier.verdict).upper()
        verdict_pass = (actual_verdict == exp_verdict)

        print(f"Done -> Verdict: {actual_verdict} (Risk: {dossier.risk_score}) [{'PASS' if verdict_pass else 'FAIL'}]")

        doc_results.append({
            "id": doc_id,
            "file": filename,
            "type": item["type"],
            "matches": doc_field_matches,
            "actual_verdict": actual_verdict,
            "expected_verdict": exp_verdict,
            "risk_score": dossier.risk_score,
            "verdict_pass": verdict_pass,
            "sources": claim.field_sources
        })

    # Summary Table
    print("\n" + "=" * 110)
    print("FIELD-LEVEL ACCURACY METRICS")
    print("=" * 110)
    print(f"{'Field Name':<25} | {'Ground Truth':<12} | {'Correct (TP)':<12} | {'Precision':<10} | {'Recall':<10} | {'Accuracy':<10}")
    print("-" * 110)

    total_tp = 0
    total_expected = 0

    for f in FIELDS:
        stats = field_stats[f]
        tp = stats["tp"]
        fp = stats["fp"]
        fn = stats["fn"]
        tot = stats["total"]

        total_tp += tp
        total_expected += tot

        precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 100.0
        recall = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 0.0
        accuracy = (tp / tot) * 100 if tot > 0 else 0.0

        print(f"{f:<25} | {tot:<12} | {tp:<12} | {precision:>8.1f}% | {recall:>8.1f}% | {accuracy:>8.1f}%")

    overall_accuracy = (total_tp / total_expected) * 100 if total_expected > 0 else 0.0
    print("-" * 110)
    print(f"{'OVERALL (ALL FIELDS)':<25} | {total_expected:<12} | {total_tp:<12} | {'-':>10} | {'-':>10} | {overall_accuracy:>8.1f}%")

    # Document Level Table
    print("\n" + "=" * 110)
    print("DOCUMENT-LEVEL EXTRACTION & VERDICT RESULTS")
    print("=" * 110)
    print(f"{'ID':<10} | {'Filename':<35} | {'Fields Matched':<15} | {'Exp Verdict':<12} | {'Act Verdict':<12} | {'Risk':<5} | {'Status'}")
    print("-" * 110)
    for r in doc_results:
        matched_cnt = sum(1 for m in r["matches"].values() if m)
        tot_cnt = len(r["matches"])
        status = "PASS" if (r["verdict_pass"] and matched_cnt >= tot_cnt - 1) else "WARN"
        print(f"{r['id']:<10} | {r['file'][:35]:<35} | {matched_cnt}/{tot_cnt:<13} | {r['expected_verdict']:<12} | {r['actual_verdict']:<12} | {r['risk_score']:<5} | {status}")

    print("\n" + "=" * 110)
    print(f"Extraction Verification Result: {overall_accuracy:.1f}% accuracy across {len(corpus)} unseen bills.")
    if overall_accuracy >= 90.0:
        print("PASS: Field-level accuracy meets and exceeds the >= 90% benchmark requirement.")
    else:
        print("FAIL: Field-level accuracy below 90%.")
        sys.exit(1)


if __name__ == "__main__":
    main()
