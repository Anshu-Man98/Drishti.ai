#!/usr/bin/env python3
"""
scripts/run_live_duel.py

Executes a live 5-round adversarial duel between Red-Team Fraudster and FinShield Defender
using Vertex AI Gemini and the multi-agent claims scrutiny pipeline.
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

from backend.app.services.db import db_service
from backend.agents.duel import run_duel, DuelResult

def main():
    print("\n" + "=" * 95)
    print("FINSHIELD LIVE 5-ROUND ADVERSARIAL DUEL (Red-Team Fraudster vs. FinShield Defender)")
    print("=" * 95 + "\n")

    base_claim = db_service.get_claim("CLM-G1-CLEAN-DEMO")
    if not base_claim:
        print("Error: Baseline claim CLM-G1-CLEAN-DEMO not found.")
        sys.exit(1)

    print(f"Base Claim: {base_claim.claim_id} (Diagnosis: {base_claim.diagnosis_code}, Total: ₹{base_claim.total_claimed:,.2f})")
    print("Executing 5 adversarial duel rounds with live Vertex AI...\n")

    duel_res: DuelResult = run_duel(base_claim, max_rounds=5)

    print("\n" + "=" * 95)
    print(f"DUEL SUMMARY: {duel_res.duel_id}")
    print(f"Winning Side: {duel_res.winning_side.upper()} | Status: {duel_res.status} | Rounds Executed: {len(duel_res.rounds)}")
    print("=" * 95 + "\n")

    print(f"| {'Rnd':<3} | {'Tactic / Mutation':<32} | {'Claimed Total':<14} | {'Inflat':<6} | {'Verdict':<8} | {'Risk':<5} | {'Result':<6} |")
    print("|" + "-" * 5 + "+" + "-" * 34 + "+" + "-" * 16 + "+" + "-" * 8 + "+" + "-" * 10 + "+" + "-" * 7 + "+" + "-" * 8 + "|")

    for r in duel_res.rounds:
        tactic_trunc = (r.tactic[:30] + "..") if len(r.tactic) > 32 else r.tactic
        result_str = "CAUGHT" if r.caught else "EVADED"
        print(f"| {r.round_number:<3} | {tactic_trunc:<32} | ₹{r.total_claimed:>11,.2f} | {r.inflation_ratio:.2f}x | {r.verdict:<8} | {r.risk_score:<5} | {result_str:<6} |")

    print("-" * 95)

    # Detailed catches
    print("\nROUND-BY-ROUND DEFENDER SCRUTINY & CATCHING FINDINGS:")
    for r in duel_res.rounds:
        print(f"\nRound {r.round_number}: {r.tactic}")
        print(f"  Claimed Amount: ₹{r.total_claimed:,.2f} ({r.inflation_ratio:.2f}x baseline ₹{r.baseline_amount:,.2f})")
        print(f"  Defender Verdict: {r.verdict} (Risk Score: {r.risk_score})")
        print(f"  Outcome: {'CAUGHT by Defender' if r.caught else 'EVADED Defender'}")
        if r.catching_check_ids:
            print(f"  Catching Check IDs: {', '.join(r.catching_check_ids)}")
        else:
            print("  Catching Check IDs: None")

    if duel_res.learned_pattern:
        print("\nLEARNED ADVERSARIAL PATTERN REGISTERED:")
        print(f"  Pattern ID: {duel_res.learned_pattern.get('pattern_id')}")
        print(f"  Title: {duel_res.learned_pattern.get('title')}")
        print(f"  Signature: {duel_res.learned_pattern.get('signature')}")
        print(f"  Typical Severity: {duel_res.learned_pattern.get('typical_severity')}")

    if duel_res.winning_side == "defender":
        if duel_res.learned_pattern:
            print("\nSUCCESS: Evade -> Learn -> Catch cycle complete! FinShield Defender learned the fraudster's evasion tactic and neutralized it in subsequent rounds.")
        else:
            print("\nSUCCESS: FinShield Defender successfully neutralized all fraud attempts across all rounds!")
    else:
        print(f"\nFraudster evaded in round {duel_res.rounds[-1].round_number}. Pattern registered.")

if __name__ == "__main__":
    main()
