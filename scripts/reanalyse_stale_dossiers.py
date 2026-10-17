#!/usr/bin/env python3
"""
Stale Dossier Audit & Re-analysis Tool.

Audits Cloud Firestore dossiers to identify cases where:
- The dossier status is marked "complete"
- BUT the dossier carries an unreadable, corrupt, or incomplete extraction finding
  (e.g. CLM-4AF523DD, CLM-508CF642).

Usage:
    # Dry-run audit (prints candidate stale dossiers without re-running analysis):
    PYTHONPATH=. .venv/bin/python scripts/reanalyse_stale_dossiers.py

    # Apply re-analysis (only when explicitly approved by user):
    PYTHONPATH=. .venv/bin/python scripts/reanalyse_stale_dossiers.py --apply
"""

import sys
import argparse
import requests
from typing import Dict, Any, List

from backend.app.config import settings
from backend.app.services.db import db_service

UNREADABLE_OR_INCOMPLETE_CHECK_IDS = {
    "DOCUMENT_UNREADABLE",
    "DOC_UNREADABLE",
    "CORRUPT_DOCUMENT",
    "EXTRACTION_FAILED",
    "INCOMPLETE_EXTRACTION",
    "INCOMPLETE_ANALYSIS",
    "TOKEN_BUDGET_EXCEEDED",
    "NOT_A_MEDICAL_BILL",
}


def find_stale_dossiers() -> List[Dict[str, Any]]:
    """Scans Cloud Firestore for dossiers with status complete but unreadable/incomplete findings."""
    fs = db_service.client
    dossier_docs = list(fs.collection("dossiers").stream())
    stale = []

    for doc in dossier_docs:
        data = doc.to_dict() or {}
        claim_id = doc.id
        status = data.get("status", "complete")

        findings = data.get("findings", [])
        flagged_findings = []
        for f in findings:
            cid = str(f.get("check_id", "")).upper()
            title = str(f.get("title", "")).lower()
            expl = str(f.get("explanation", "")).lower()

            is_stale_finding = (
                cid in UNREADABLE_OR_INCOMPLETE_CHECK_IDS
                or "unreadable" in cid
                or "unreadable" in title
                or "corrupt" in title
                or "could not be read" in expl
                or "incomplete analysis" in title
            )
            if is_stale_finding:
                flagged_findings.append({
                    "finding_id": f.get("finding_id"),
                    "check_id": f.get("check_id"),
                    "title": f.get("title")
                })

        # If it has unreadable/incomplete findings but is marked complete:
        if flagged_findings and status == "complete":
            stale.append({
                "claim_id": claim_id,
                "status": status,
                "verdict": data.get("verdict"),
                "risk_score": data.get("risk_score"),
                "flagged_findings": flagged_findings
            })

    return stale


def main():
    parser = argparse.ArgumentParser(description="Audit and re-analyse stale dossiers.")
    parser.add_argument("--apply", action="store_true", help="Re-run analysis via POST /api/claims/{id}/analyze (requires approval).")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Base API URL for re-analysis.")
    args = parser.parse_args()

    mode_label = "LIVE APPLY" if args.apply else "DRY RUN (Audit Only)"
    print(f"=== Drishti AI Stale Dossier Audit [{mode_label}] ===")
    print(f"Firestore Database: {settings.FIRESTORE_DATABASE}")
    print(f"Google Cloud Project: {settings.GCP_PROJECT}\n")

    stale_list = find_stale_dossiers()

    if not stale_list:
        print("No stale dossiers found. All dossiers in Cloud Firestore are correctly status-calibrated.")
        return

    print(f"Found {len(stale_list)} stale dossiers (marked 'complete' with unreadable/incomplete findings):\n")
    print(f"{'Claim ID':<20} | {'Status':<10} | {'Verdict':<8} | {'Risk':<5} | {'Offending Finding(s)'}")
    print("-" * 85)

    for item in stale_list:
        findings_str = ", ".join(f"{f['check_id']} ({f['finding_id']})" for f in item["flagged_findings"])
        print(f"{item['claim_id']:<20} | {item['status']:<10} | {str(item['verdict']):<8} | {str(item['risk_score']):<5} | {findings_str}")

    print("-" * 85)
    print(f"\nTotal stale dossiers identified: {len(stale_list)}")

    if not args.apply:
        print("\n[DRY RUN AUDIT COMPLETE]")
        print("Notice: Per safety constraints, re-analysis is NOT executed automatically.")
        print("Present this list to the user and re-run with --apply only upon explicit user confirmation.")
        return

    print(f"\nTriggering re-analysis against API at {args.api_url}...")
    headers = {"Authorization": "Bearer dev-token-adjuster"}
    for item in stale_list:
        cid = item["claim_id"]
        print(f"  -> Triggering POST /api/claims/{cid}/analyze ...", end=" ", flush=True)
        try:
            resp = requests.post(f"{args.api_url}/api/claims/{cid}/analyze?force_refresh=true", headers=headers, timeout=120)
            if resp.status_code == 200:
                res_json = resp.json()
                print(f"SUCCESS [Status: {res_json.get('status')}, Verdict: {res_json.get('verdict')}]")
            else:
                print(f"FAILED (HTTP {resp.status_code}: {resp.text[:80]})")
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
