#!/usr/bin/env python3
"""
Clean Test Claims Script for FinShield (Drishti.ai).

Identifies and removes test claims created during automated test runs.
By default runs in DRY-RUN mode. Pass --apply to perform the actual deletion.

Target criteria:
- Claim ID starts with: 'CLM-SEC-', 'CLM-BOUNDS-', 'CLM-API-TEST'
- OR claimant_name is: 'Test Claimant' or 'Test User'
"""

import sys
import json
import shutil
import sqlite3
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "finshield.db"
DEFAULT_UPLOADS_DIR = REPO_ROOT / "data" / "uploads"

PREFIXES = ("CLM-SEC-", "CLM-BOUNDS-", "CLM-API-TEST")
TEST_CLAIMANT_NAMES = {"Test Claimant", "Test User"}


def should_remove_claim(claim_id: str, claim_data: dict) -> tuple[bool, str]:
    if claim_id.startswith(PREFIXES):
        for prefix in PREFIXES:
            if claim_id.startswith(prefix):
                return True, f"Claim ID prefix '{prefix}'"

    claimant = claim_data.get("claimant") or {}
    claimant_name = claimant.get("name", "").strip()
    if claimant_name in TEST_CLAIMANT_NAMES:
        return True, f"Claimant name '{claimant_name}'"

    return False, ""


def main():
    parser = argparse.ArgumentParser(description="Clean test claims from FinShield database.")
    parser.add_argument("--apply", action="store_true", help="Execute deletion (default is dry-run)")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to finshield.db")
    args = parser.parse_args()

    if not args.db_path.exists():
        print(f"Error: Database file not found at {args.db_path}")
        sys.exit(1)

    print(f"Connecting to database: {args.db_path}")
    print(f"Mode: {'APPLY (Deletions will be made)' if args.apply else 'DRY-RUN (No changes will be made)'}")
    print("-" * 70)

    conn = sqlite3.connect(args.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT claim_id, data FROM claims")
    rows = cursor.fetchall()

    to_remove = []
    for claim_id, data_str in rows:
        try:
            data = json.loads(data_str)
        except Exception:
            data = {}

        match, reason = should_remove_claim(claim_id, data)
        if match:
            claimant_name = (data.get("claimant") or {}).get("name", "N/A")
            total_claimed = data.get("total_claimed", 0.0)
            to_remove.append((claim_id, claimant_name, total_claimed, reason))

    if not to_remove:
        print("No test claims found matching criteria. Database is clean.")
        conn.close()
        return

    print(f"Found {len(to_remove)} test claim(s):")
    for claim_id, name, amount, reason in to_remove:
        print(f"  • {claim_id:20} | Claimant: {name:16} | Amount: ₹{amount:10,.2f} | Reason: {reason}")

    print("-" * 70)

    if not args.apply:
        print(f"[DRY-RUN] {len(to_remove)} claim(s) would be deleted.")
        print("Run with '--apply' to delete these claims from finshield.db.")
        conn.close()
        return

    # Perform actual deletion
    claim_ids = [c[0] for c in to_remove]
    placeholders = ",".join("?" for _ in claim_ids)

    cursor.execute(f"DELETE FROM claims WHERE claim_id IN ({placeholders})", claim_ids)
    deleted_claims = cursor.rowcount

    cursor.execute(f"DELETE FROM dossiers WHERE claim_id IN ({placeholders})", claim_ids)
    deleted_dossiers = cursor.rowcount

    cursor.execute(f"DELETE FROM chat_messages WHERE claim_id IN ({placeholders})", claim_ids)
    deleted_chat = cursor.rowcount

    cursor.execute(f"DELETE FROM issuance_ledger WHERE claim_id IN ({placeholders})", claim_ids)
    deleted_ledger = cursor.rowcount

    conn.commit()
    conn.close()

    # Also clean up any uploaded test files for these claim IDs
    cleaned_uploads = 0
    if DEFAULT_UPLOADS_DIR.exists():
        for cid in claim_ids:
            claim_upload_dir = DEFAULT_UPLOADS_DIR / cid
            if claim_upload_dir.exists() and claim_upload_dir.is_dir():
                try:
                    shutil.rmtree(claim_upload_dir)
                    cleaned_uploads += 1
                except Exception as e:
                    print(f"  Warning: Could not remove directory {claim_upload_dir}: {e}")

    print(f"[APPLIED] Successfully deleted {deleted_claims} claim(s), {deleted_dossiers} dossier(s), "
          f"{deleted_chat} chat message(s), and cleaned {cleaned_uploads} upload dir(s).")


if __name__ == "__main__":
    main()
