#!/usr/bin/env python3
"""
scripts/verify_golden.py

Live cloud verification script for FinShield / Drishti.ai Golden Demo Claims (G1-G9).
Runs the end-to-end multi-agent claims fraud pipeline against real Google Cloud services
(Vertex AI Gemini, Firestore, Cloud Storage, BigQuery ML, Document AI) and compares the
resulting verdicts against data/demo/ground_truth.json.

Usage:
    python scripts/verify_golden.py [--no-force] [--claim <claim_id>]

Prerequisites:
    - ADC configured: gcloud auth application-default login
    - PATH includes Google Cloud SDK (~/google-cloud-sdk/bin)
    - Active environment variables for GCP project drishti-demo
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure root repository directory is on sys.path
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

from backend.agents.root import run_claims_fraud_pipeline
from backend.app.services.db import db_service

GOLDEN_CLAIMS = [
    {"key": "G1", "claim_id": "CLM-G1-CLEAN-DEMO", "title": "Clean Claim"},
    {"key": "G2", "claim_id": "CLM-G2-ARITHMETIC-DEMO", "title": "Arithmetic Mismatch"},
    {"key": "G3", "claim_id": "CLM-G3-POLICYCAP-DEMO", "title": "Policy Cap Breach"},
    {"key": "G4", "claim_id": "CLM-G4-CROSSINS-DEMO", "title": "Cross-Insurer Duplicate"},
    {"key": "G5", "claim_id": "CLM-G5-TRAVEL-DEMO", "title": "Impossible Travel"},
    {"key": "G6", "claim_id": "CLM-G6-FORGERY-DEMO", "title": "Forged Document"},
    {"key": "G7", "claim_id": "CLM-G7-INJECTION-DEMO", "title": "Prompt Injection"},
    {"key": "G8", "claim_id": "CLM-G8-ALTERED-DEMO", "title": "Altered Approval Letter"},
    {"key": "G9", "claim_id": "CLM-G9-PATTERN-DEMO", "title": "Known Fraud Pattern"},
]


def verify_claims(claims_to_check, force: bool = True):
    gt_path = ROOT_DIR / "data" / "demo" / "ground_truth.json"
    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    results = []
    print(f"\n{'='*95}")
    print(f"FINSHIELD GOLDEN CLAIMS VERIFICATION (Real Cloud: {os.environ['GOOGLE_CLOUD_PROJECT']})")
    print(f"Force re-analysis: {force}")
    print(f"{'='*95}\n")

    for item in claims_to_check:
        key = item["key"]
        claim_id = item["claim_id"]
        gt_entry = ground_truth.get(key, {})
        expected_verdict = gt_entry.get("expected_verdict", "unknown").lower()
        expected_risk = gt_entry.get("expected_risk_category", "unknown").lower()

        print(f"Analyzing {key} ({claim_id}) ... ", end="", flush=True)
        try:
            dossier = run_claims_fraud_pipeline(claim_id)
            actual_verdict = dossier.verdict.value.lower()
            risk_score = dossier.risk_score
            findings_count = len(dossier.findings)
            status_match = actual_verdict == expected_verdict

            # Collect primary finding IDs
            finding_ids = [f.check_id for f in dossier.findings if getattr(f, "severity", None) in ("high", "critical")]
            findings_summary = ", ".join(finding_ids[:2])
            if len(finding_ids) > 2:
                findings_summary += f" (+{len(finding_ids) - 2} more)"
            if not findings_summary:
                findings_summary = f"{findings_count} findings"

            results.append({
                "key": key,
                "claim_id": claim_id,
                "expected": expected_verdict,
                "actual": actual_verdict,
                "expected_risk": expected_risk,
                "risk_score": risk_score,
                "match": status_match,
                "findings": findings_summary,
                "error": None,
            })
            print(f"Done -> Actual: {actual_verdict.upper()} (Risk: {risk_score}) [{'PASS' if status_match else 'FAIL'}]")
        except Exception as e:
            results.append({
                "key": key,
                "claim_id": claim_id,
                "expected": expected_verdict,
                "actual": "ERROR",
                "expected_risk": expected_risk,
                "risk_score": -1,
                "match": False,
                "findings": "Pipeline raised exception",
                "error": str(e),
            })
            print(f"ERROR: {e}")

    # Print Table
    print(f"\n{'-'*95}")
    header = f"| {'Key':<4} | {'Claim ID':<23} | {'Expected':<8} | {'Actual':<8} | {'Risk':<5} | {'Status':<6} | {'Key Flags / Evidence':<25} |"
    print(header)
    print(f"|{'-'*6}+{'-'*25}+{'-'*10}+{'-'*10}+{'-'*7}+{'-'*8}+{'-'*27}|")

    passed_count = 0
    for r in results:
        status_str = "PASS" if r["match"] else "FAIL"
        if r["match"]:
            passed_count += 1
        line = f"| {r['key']:<4} | {r['claim_id']:<23} | {r['expected'].upper():<8} | {r['actual'].upper():<8} | {r['risk_score']:<5} | {status_str:<6} | {r['findings']:<25} |"
        print(line)

    print(f"{'-'*95}\n")
    print(f"Verification Results: {passed_count}/{len(results)} Golden Claims Matched Expected Ground Truth.")

    return passed_count == len(results)


def main():
    parser = argparse.ArgumentParser(description="Verify Golden Claims against ground_truth.json")
    parser.add_argument("--no-force", action="store_true", help="Do not force re-analysis; use cached dossier if present")
    parser.add_argument("--claim", type=str, default=None, help="Verify specific claim ID or key (e.g. G2 or CLM-G2-ARITHMETIC-DEMO)")
    args = parser.parse_args()

    claims = GOLDEN_CLAIMS
    if args.claim:
        target = args.claim.strip().upper()
        claims = [c for c in GOLDEN_CLAIMS if c["key"].upper() == target or c["claim_id"].upper() == target]
        if not claims:
            print(f"Error: Claim '{args.claim}' not found in golden claims list.")
            sys.exit(1)

    success = verify_claims(claims, force=not args.no_force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
