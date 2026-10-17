#!/usr/bin/env python3
"""
Backfill script to tag existing claims in Cloud Firestore with their authentic source:
- 'demo': Golden demo claims and pre-seeded ground truth cases
- 'duel': Adversarial simulator / fraudster duel cases
- 'qa': QA evaluation bills
- 'upload': Real / authentic uploaded claims

Usage:
    # Dry-run (lists all claims and inferred sources without modifying Firestore):
    PYTHONPATH=. .venv/bin/python scripts/backfill_claim_sources.py

    # Apply backfill changes to live Cloud Firestore:
    PYTHONPATH=. .venv/bin/python scripts/backfill_claim_sources.py --apply
"""

import sys
import argparse
from typing import Dict, Any, List

from backend.app.config import settings
from backend.app.services.db import db_service


def infer_source(claim_id: str, claim_data: Dict[str, Any]) -> str:
    """Infers the source marker for a claim based on its ID, metadata, and origin."""
    existing_source = claim_data.get("source")
    if existing_source in ("upload", "demo", "duel", "qa"):
        return existing_source

    cid_upper = claim_id.upper()
    meta = claim_data.get("metadata") or {}

    # 1. Duel simulation
    if "DUEL" in cid_upper or meta.get("duel_id") or meta.get("duel_round"):
        return "duel"

    # 2. QA evaluation suite
    if "EVAL" in cid_upper or "QA-" in cid_upper:
        return "qa"

    # 3. Golden demo claims (from data/demo or seeded)
    demo_tokens = ("DEMO", "SYNTH", "CLM-100475", "CLM-4AF523DD", "CLM-508CF642", "CLM-882190", "CLM-902144", "CLM-990123")
    if any(token in cid_upper for token in demo_tokens):
        return "demo"

    # 4. Authentic user / hospital upload
    return "upload"


def main():
    parser = argparse.ArgumentParser(description="Backfill claim source markers in Cloud Firestore.")
    parser.add_argument("--apply", action="store_true", help="Execute write updates in Firestore (default is dry-run).")
    args = parser.parse_args()

    mode_label = "LIVE APPLY" if args.apply else "DRY RUN (No changes will be written)"
    print(f"=== Drishti AI Claim Source Backfill [{mode_label}] ===")
    print(f"Firestore Database: {settings.FIRESTORE_DATABASE}")
    print(f"Google Cloud Project: {settings.GCP_PROJECT}\n")

    fs = db_service.client
    claims_ref = fs.collection("claims")
    docs = list(claims_ref.stream())

    if not docs:
        print("No claims found in Firestore.")
        return

    print(f"Found {len(docs)} claims in Firestore collection 'claims'.\n")
    print(f"{'Claim ID':<30} | {'Current Source':<15} | {'Inferred Source':<15} | {'Action':<15}")
    print("-" * 80)

    updates_needed: List[tuple[str, str, Any]] = []

    for d in docs:
        cid = d.id
        data = d.to_dict() or {}
        curr_source = data.get("source", "<none>")
        inferred = infer_source(cid, data)

        if curr_source != inferred:
            action = "WILL UPDATE" if args.apply else "DRY-RUN UPDATE"
            updates_needed.append((cid, inferred, d.reference))
        else:
            action = "UNCHANGED"

        print(f"{cid:<30} | {curr_source:<15} | {inferred:<15} | {action:<15}")

    print("-" * 80)
    print(f"\nSummary: {len(updates_needed)} of {len(docs)} claims require source field update.")

    if not args.apply:
        print("\n[DRY RUN COMPLETE] To write these changes to Firestore, run with --apply")
        return

    print("\nApplying updates to Firestore...")
    for cid, source_val, doc_ref in updates_needed:
        doc_ref.update({"source": source_val})
        print(f"  -> Updated {cid} with source='{source_val}'")

    print(f"\nSuccessfully backfilled {len(updates_needed)} claims in Cloud Firestore.")


if __name__ == "__main__":
    main()
