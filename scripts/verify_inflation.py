#!/usr/bin/env python3
"""
scripts/verify_inflation.py

Verification script for FinShield / Drishti.ai Benchmark-Driven Inflation Detection (Task B).
Verifies:
  1. Inflation Ladder on baseline claim CLM-G1-CLEAN-DEMO:
     - Baseline (₹74,550, +0%): APPROVE (risk <= 30)
     - +10% (₹82,005): within acceptable tolerance
     - +20% (₹89,460): elevated benchmark flags
     - +28% (₹95,424, Duel Evasion Claim): REVIEW/REJECT (risk >= 45, never APPROVE at risk 5)
     - +40% (₹104,370): REVIEW/REJECT
     - +60% (₹119,280): REJECT (severe inflation)
  2. False Positive Rate (FPR) on >= 20 authentic claims from BigQuery warehouse:
     - Target FPR < 5% (0 false positives expected)

Usage:
    python scripts/verify_inflation.py
"""

import os
import sys
import json
from copy import deepcopy
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
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

from google.cloud import bigquery
from backend.app.schemas import Claim, LineItem, Verdict
from backend.app.services.db import db_service
from backend.agents.root import run_claims_fraud_pipeline
from backend.tools.registry import check_price_benchmarks, to_paise, to_rupees


def cleanup_test_claim(claim_id: str):
    """Safely cleans up transient test claims from Firestore."""
    try:
        if db_service.client:
            db_service.client.collection("claims").document(claim_id).delete()
            db_service.client.collection("dossiers").document(claim_id).delete()
    except Exception as e:
        print(f"Warning: Cleanup for {claim_id} failed: {e}")


def test_inflation_ladder() -> bool:
    print("\n" + "=" * 95)
    print("PART 1: INFLATION LADDER TEST (Baseline: CLM-G1-CLEAN-DEMO ₹74,550.00)")
    print("=" * 95 + "\n")

    base_claim = db_service.get_claim("CLM-G1-CLEAN-DEMO")
    if not base_claim:
        raise ValueError("Baseline claim CLM-G1-CLEAN-DEMO not found in Firestore.")

    baseline_total = float(base_claim.total_claimed)

    ladder_specs = [
        {
            "name": "Baseline (+0%)",
            "multiplier": 1.0,
            "target_total": baseline_total,
            "expected_verdicts": ["APPROVE"],
            "max_risk": 25,
            "min_risk": 0,
            "must_not_approve": False,
            "type": "baseline",
        },
        {
            "name": "+10% Inflation",
            "multiplier": 1.10,
            "target_total": round(baseline_total * 1.10, 2),
            "expected_verdicts": ["APPROVE", "REVIEW"],
            "max_risk": 45,
            "min_risk": 12,
            "must_not_approve": False,
            "type": "uniform",
        },
        {
            "name": "+20% Inflation",
            "multiplier": 1.20,
            "target_total": round(baseline_total * 1.20, 2),
            "expected_verdicts": ["REVIEW"],
            "max_risk": 65,
            "min_risk": 30,
            "must_not_approve": True,
            "type": "uniform",
        },
        {
            "name": "+28% Duel Evasion Claim",
            "multiplier": 1.28,
            "target_total": 95424.0,
            "expected_verdicts": ["REVIEW"],
            "max_risk": 65,
            "min_risk": 40,
            "must_not_approve": True,
            "type": "duel_padding",
        },
        {
            "name": "+40% Inflation",
            "multiplier": 1.40,
            "target_total": round(baseline_total * 1.40, 2),
            "expected_verdicts": ["REVIEW", "REJECT"],
            "max_risk": 100,
            "min_risk": 50,
            "must_not_approve": True,
            "type": "uniform",
        },
        {
            "name": "+60% Inflation",
            "multiplier": 1.60,
            "target_total": round(baseline_total * 1.60, 2),
            "expected_verdicts": ["REJECT"],
            "max_risk": 100,
            "min_risk": 70,
            "must_not_approve": True,
            "type": "uniform",
        },
    ]

    all_passed = True
    results = []

    for spec in ladder_specs:
        test_claim_id = f"CLM-TEST-LADDER-{int(spec['multiplier']*100)}"
        claim_variant = deepcopy(base_claim)
        claim_variant.claim_id = test_claim_id

        if spec["type"] == "baseline":
            # Just baseline claim
            pass
        elif spec["type"] == "duel_padding":
            # The exact red-team duel scenario: micro-upcoding + padded ancillary
            claim_variant.subtotal = 90880.0
            claim_variant.tax = 4544.0
            claim_variant.total_claimed = 95424.0
            claim_variant.line_items = [
                LineItem(description="Semi-Private Room Rent (3 days)", qty=3, unit_price=4000.0, amount=12000.0, page=1, source="form"),
                LineItem(description="Laparoscopic Appendectomy Surgery & OT", qty=1, unit_price=51000.0, amount=51000.0, page=1, source="form"),
                LineItem(description="Consultant Surgeon & Anesthetist Visit Fees", qty=3, unit_price=2000.0, amount=6000.0, page=1, source="form"),
                LineItem(description="Post-Op Pharmacy & Antibiotic Consumables", qty=1, unit_price=8000.0, amount=8000.0, page=1, source="form"),
                LineItem(description="Surgical Consumables & Disposable Trocar Pack", qty=1, unit_price=7880.0, amount=7880.0, page=1, source="form"),
                LineItem(description="High-Definition Laparoscopy Tower Surcharge", qty=1, unit_price=6000.0, amount=6000.0, page=1, source="form"),
            ]
        else:
            mult = spec["multiplier"]
            new_items = []
            sub_paise = 0
            for it in base_claim.line_items or []:
                new_u = round(it.unit_price * mult, 2)
                new_a = round(new_u * it.qty, 2)
                sub_paise += to_paise(new_a)
                new_items.append(LineItem(
                    description=it.description,
                    qty=it.qty,
                    unit_price=new_u,
                    amount=new_a,
                    page=1,
                    source="form"
                ))
            claim_variant.line_items = new_items
            claim_variant.subtotal = to_rupees(sub_paise)
            tax_paise = int(round(sub_paise * 0.05))
            claim_variant.tax = to_rupees(tax_paise)
            claim_variant.total_claimed = to_rupees(sub_paise + tax_paise)

        print(f"Testing {spec['name']} (Target ₹{claim_variant.total_claimed:,.2f}) ... ", end="", flush=True)

        try:
            db_service.save_claim(claim_variant)
            dossier = run_claims_fraud_pipeline(claim_variant)
            verdict = dossier.verdict.value.upper()
            risk = dossier.risk_score

            # Evaluate pass/fail conditions
            passed = True
            if verdict not in spec["expected_verdicts"]:
                passed = False
            if spec["must_not_approve"] and verdict == "APPROVE":
                passed = False
            if risk < spec["min_risk"] or risk > spec["max_risk"]:
                passed = False

            # Extract benchmark findings
            bench_flags = [f.check_id for f in dossier.findings if "BENCH" in f.check_id or "ANCILLARY" in f.check_id]

            results.append({
                "test": spec["name"],
                "total": claim_variant.total_claimed,
                "verdict": verdict,
                "risk": risk,
                "passed": passed,
                "flags": ", ".join(bench_flags) if bench_flags else "None",
            })

            status_str = "PASS" if passed else "FAIL"
            print(f"Done -> Verdict: {verdict} (Risk: {risk}) [{status_str}]")
            if not passed:
                all_passed = False
        finally:
            cleanup_test_claim(test_claim_id)

    print("\n" + "-" * 95)
    print(f"| {'Test Case':<25} | {'Claimed Total':<14} | {'Verdict':<8} | {'Risk':<5} | {'Status':<6} | {'Benchmark Findings':<24} |")
    print("|" + "-" * 27 + "+" + "-" * 16 + "+" + "-" * 10 + "+" + "-" * 7 + "+" + "-" * 8 + "+" + "-" * 26 + "|")
    for r in results:
        print(f"| {r['test']:<25} | ₹{r['total']:>11,.2f} | {r['verdict']:<8} | {r['risk']:<5} | {('PASS' if r['passed'] else 'FAIL'):<6} | {r['flags'][:24]:<24} |")
    print("-" * 95 + "\n")

    # Issue 2c: Strict monotonicity check
    r_0 = results[0]["risk"]
    r_10 = results[1]["risk"]
    r_20 = results[2]["risk"]
    r_28 = results[3]["risk"]
    r_40 = results[4]["risk"]
    r_60 = results[5]["risk"]

    monotonicity_ok = (r_0 <= r_10 < r_20 <= r_28 < r_40 < r_60)
    print(f"Ladder Monotonicity Check: {r_0} <= {r_10} < {r_20} <= {r_28} < {r_40} < {r_60} -> {'PASS' if monotonicity_ok else 'FAIL'}")
    if not monotonicity_ok:
        all_passed = False

    return all_passed


def test_authentic_claims_fpr() -> bool:
    print("=" * 95)
    print("PART 2: FALSE POSITIVE RATE (FPR) AUDIT (20 Authentic Claims from finshield.claims)")
    print("=" * 95 + "\n")

    bq_client = bigquery.Client(project="drishti-demo")
    query = """
    SELECT c.claim_id, c.diagnosis_code, c.total_claimed,
           ARRAY_AGG(STRUCT(l.description, l.qty, l.unit_price, l.amount)) as line_items
    FROM `drishti-demo.finshield.claims` c
    JOIN `drishti-demo.finshield.line_items` l ON c.claim_id = l.claim_id
    WHERE c.is_fraud = 0
    GROUP BY c.claim_id, c.diagnosis_code, c.total_claimed
    ORDER BY FARM_FINGERPRINT(c.claim_id)
    LIMIT 20;
    """

    rows = list(bq_client.query(query).result())
    if len(rows) < 20:
        raise ValueError(f"Expected at least 20 authentic claims from BigQuery, found {len(rows)}")

    results = []
    false_positives = 0

    for idx, r in enumerate(rows, 1):
        claim_dict = {
            "claim_id": r.claim_id,
            "diagnosis_code": r.diagnosis_code,
            "total_claimed": float(r.total_claimed),
            "line_items": [
                {
                    "description": it["description"],
                    "qty": float(it["qty"]),
                    "unit_price": float(it["unit_price"]),
                    "amount": float(it["amount"]),
                }
                for it in r.line_items
            ],
        }

        bench_res = check_price_benchmarks(claim_dict)
        findings = bench_res.get("findings", [])
        high_findings = [f for f in findings if getattr(f, "severity", None) in ("high", "critical")]

        is_fp = len(high_findings) > 0
        if is_fp:
            false_positives += 1

        flag_names = [f.check_id for f in findings]
        results.append({
            "idx": idx,
            "claim_id": r.claim_id,
            "diagnosis": r.diagnosis_code,
            "total": float(r.total_claimed),
            "flags_count": len(findings),
            "high_flags": len(high_findings),
            "status": "PASS" if not is_fp else "FAIL",
            "flags": ", ".join(flag_names[:2]) if flag_names else "clean",
        })

    fpr = (false_positives / len(rows)) * 100.0

    print(f"| {'#':<3} | {'Claim ID':<12} | {'Diagnosis':<10} | {'Total Claimed':<14} | {'Flags':<6} | {'High':<5} | {'Status':<6} |")
    print("|" + "-" * 5 + "+" + "-" * 14 + "+" + "-" * 12 + "+" + "-" * 16 + "+" + "-" * 8 + "+" + "-" * 7 + "+" + "-" * 8 + "|")
    for r in results:
        print(f"| {r['idx']:<3} | {r['claim_id']:<12} | {r['diagnosis']:<10} | ₹{r['total']:>11,.2f} | {r['flags_count']:<6} | {r['high_flags']:<5} | {r['status']:<6} |")
    print("-" * 95)
    print(f"Authentic Claims Tested : {len(rows)}")
    print(f"False Positives Triggered: {false_positives}")
    print(f"False Positive Rate (FPR): {fpr:.2f}% (Threshold: < 5.0%)")
    print("-" * 95 + "\n")

    return fpr < 5.0


def test_property_monotonicity_across_diagnoses() -> bool:
    print("=" * 95)
    print("PART 3: MONOTONICITY PROPERTY TESTS ACROSS 5 DIAGNOSES")
    print("=" * 95 + "\n")
    from backend.tests.test_inflation_monotonicity import BASE_CLAIMS, test_inflation_monotonicity

    all_ok = True
    for claim in BASE_CLAIMS:
        print(f"Testing Monotonicity on {claim.claim_id} ({claim.diagnosis_code}) ... ", end="", flush=True)
        try:
            test_inflation_monotonicity(claim)
            print("PASS")
        except Exception as e:
            print(f"FAIL: {e}")
            all_ok = False
    print("-" * 95 + "\n")
    return all_ok


def main():
    print(f"\nFINSHIELD PRICE BENCHMARKS & INFLATION VERIFICATION")
    print(f"GCP Project: {os.environ['GOOGLE_CLOUD_PROJECT']}\n")

    ladder_ok = test_inflation_ladder()
    fpr_ok = test_authentic_claims_fpr()
    prop_ok = test_property_monotonicity_across_diagnoses()

    if ladder_ok and fpr_ok and prop_ok:
        print("ALL INFLATION & BENCHMARK VERIFICATIONS PASSED SUCCESSFULLY.")
        sys.exit(0)
    else:
        print("VERIFICATION FAILED: One or more inflation tests did not meet requirements.")
        sys.exit(1)


if __name__ == "__main__":
    main()
