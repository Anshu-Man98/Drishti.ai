#!/usr/bin/env python3
"""
Clean Test Claims Script for FinShield (Drishti.ai).

Identifies and removes test/QA claims, dossiers, issuance records, and GCS blobs
created during automated test runs, manual QA uploads, and adversarial duels.

Default mode is strictly DRY-RUN. Pass --apply to perform actual deletions.

Target criteria:
- Explicit test IDs: CLM-SEC-TEST, CLM-BOUNDS-TEST, CLM-API-TEST-99,
  CLM-G1-F4-ACCEPTANCE, CLM-G1-F8-TEST, CLM-G2-F8-TEST, CLM-G2-TEST,
  CLM-G3-F8-TEST, CLM-G5-F4-ACCEPTANCE, CLM-G6-F8-TEST, CLM-G1-DUEL-BASE,
  CLM-G1-DUEL-BASE-D1, CLM-G1-CLEAN-DEMO-D1
- ID patterns: prefixes 'CLM-SEC-', 'CLM-BOUNDS-', 'CLM-API-TEST', 'CLM-DUEL-'
  or suffixes containing '-TEST', '-ACCEPTANCE', or duel markers '-D<digits>'
- Claimant names: 'Test Claimant', 'Test User', or containing 'Unknown' or 'QA Upload'
- Orphaned test dossiers (e.g. CLM-BROKEN-DOC-TEST, CLM-G1-TEST)
- Test issuance ledger records (excluding canonical SANCTION-G8-GENUINE)
- Associated GCS blobs in finshield-claims-docs-drishti-demo under uploads/ or claims/
"""

import sys
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings

GOLDEN_CLAIM_IDS: Set[str] = {
    "CLM-G1-CLEAN-DEMO",
    "CLM-G2-ARITHMETIC-DEMO",
    "CLM-G3-POLICYCAP-DEMO",
    "CLM-G4-CROSSINS-DEMO",
    "CLM-G5-TRAVEL-DEMO",
    "CLM-G6-FORGERY-DEMO",
    "CLM-G7-INJECTION-DEMO",
    "CLM-G8-ALTERED-DEMO",
    "CLM-G9-PATTERN-DEMO",
}

PRESERVED_CLAIM_IDS: Set[str] = {
    "CLM-5198C0D6",
}

EXPLICIT_TEST_CLAIM_IDS: Set[str] = {
    "CLM-SEC-TEST",
    "CLM-BOUNDS-TEST",
    "CLM-API-TEST-99",
    "CLM-G1-F4-ACCEPTANCE",
    "CLM-G1-F8-TEST",
    "CLM-G2-F8-TEST",
    "CLM-G2-TEST",
    "CLM-G3-F8-TEST",
    "CLM-G5-F4-ACCEPTANCE",
    "CLM-G6-F8-TEST",
    "CLM-G1-DUEL-BASE",
    "CLM-G1-DUEL-BASE-D1",
    "CLM-G1-CLEAN-DEMO-D1",
    "CLM-2774E103",
    "CLM-A818D478",
    "CLM-A1F5C197",
}

TEST_PREFIXES = ("CLM-SEC-", "CLM-BOUNDS-", "CLM-API-TEST", "CLM-DUEL-")
TEST_CLAIMANT_EXACT = {"Test Claimant", "Test User"}


def is_test_claim(claim_id: str, claim_data: Dict[str, Any], include_all_non_golden: bool = False) -> Tuple[bool, str]:
    if claim_id in GOLDEN_CLAIM_IDS:
        return False, "Canonical Golden Demo Claim"

    if claim_id in PRESERVED_CLAIM_IDS:
        return False, "Explicitly Preserved Claim"

    if claim_id in EXPLICIT_TEST_CLAIM_IDS:
        return True, f"Explicit test claim ID '{claim_id}'"

    for prefix in TEST_PREFIXES:
        if claim_id.startswith(prefix):
            return True, f"Test ID prefix '{prefix}'"

    if re.search(r"-(TEST|ACCEPTANCE)", claim_id):
        return True, "Test/Acceptance pattern in claim ID"

    if re.search(r"-D\d+$", claim_id) or "-DUEL-" in claim_id or claim_id.endswith("-DUEL-BASE"):
        return True, "Duel synthetic claim pattern"

    claimant = claim_data.get("claimant") or {}
    name = (claimant.get("name") or "").strip()

    if name in TEST_CLAIMANT_EXACT:
        return True, f"Test claimant name '{name}'"

    if "unknown" in name.lower():
        return True, f"Unknown claimant name '{name}'"

    if "qa upload" in name.lower():
        return True, f"QA upload claimant name '{name}'"

    policy_id = claim_data.get("policy_id") or ""
    if policy_id == "POL-TRAVERSAL":
        return True, f"Path traversal test policy '{policy_id}'"

    if include_all_non_golden:
        return True, f"Non-golden upload claim '{claim_id}'"

    return False, ""


def delete_firestore_doc_and_subcollections(fs_client, doc_ref):
    """Recursively deletes a document and all its subcollections."""
    for subcoll in doc_ref.collections():
        for subdoc in subcoll.stream():
            delete_firestore_doc_and_subcollections(fs_client, subdoc.reference)
    doc_ref.delete()


def main():
    parser = argparse.ArgumentParser(description="Clean test/QA claims from FinShield Firestore and GCS.")
    parser.add_argument("--apply", action="store_true", help="Execute deletion (default is dry-run)")
    parser.add_argument("--include-all-non-golden", action="store_true",
                        help="Also delete any non-golden upload claim (e.g. ad-hoc uploads)")
    parser.add_argument("--skip-gcs", action="store_true", help="Skip GCS blob cleaning")
    parser.add_argument("--skip-orphans", action="store_true", help="Skip orphaned dossiers and issuance cleanup")
    args = parser.parse_args()

    mode_str = "APPLY (DELETIONS WILL BE EXECUTED)" if args.apply else "DRY-RUN (NO CHANGES WILL BE MADE)"
    print("=" * 80)
    print(f"FinShield Cloud Cleanup Tool — Mode: {mode_str}")
    print(f"Target Project:    {settings.GCP_PROJECT}")
    print(f"Target Database:   {settings.FIRESTORE_DATABASE}")
    print(f"Target GCS Bucket: {settings.GCS_BUCKET_NAME}")
    print("=" * 80)

    try:
        from google.cloud import firestore, storage
    except ImportError:
        print("Error: google-cloud-firestore and google-cloud-storage must be installed.")
        sys.exit(1)

    fs_client = firestore.Client(project=settings.GCP_PROJECT, database=settings.FIRESTORE_DATABASE)
    cs_client = storage.Client(project=settings.GCP_PROJECT)
    bucket = cs_client.bucket(settings.GCS_BUCKET_NAME)

    # 1. Inspect Claims Collection
    print("\nScanning Firestore 'claims' collection...")
    claims_docs = list(fs_client.collection("claims").stream())
    print(f"Found {len(claims_docs)} total claims in Firestore.")

    claims_to_delete: List[Tuple[str, str, Dict[str, Any]]] = []
    golden_claims_found: List[str] = []
    retained_claims: List[Tuple[str, str]] = []

    for doc in claims_docs:
        cid = doc.id
        data = doc.to_dict()
        is_test, reason = is_test_claim(cid, data, include_all_non_golden=args.include_all_non_golden)
        if is_test:
            claims_to_delete.append((cid, reason, data))
        elif cid in GOLDEN_CLAIM_IDS:
            golden_claims_found.append(cid)
        else:
            claimant_name = (data.get("claimant") or {}).get("name", "N/A")
            retained_claims.append((cid, claimant_name))

    print(f"\n[Claims Analysis]")
    print(f"  • Golden Demo Claims to PRESERVE: {len(golden_claims_found)} of {len(GOLDEN_CLAIM_IDS)}")
    for g in sorted(golden_claims_found):
        print(f"      [KEEP] {g}")

    if retained_claims:
        print(f"  • Other non-test claims retained: {len(retained_claims)} (pass --include-all-non-golden to clean)")
        for cid, name in retained_claims:
            print(f"      [RETAIN] {cid} (Claimant: {name})")

    print(f"  • Test/QA Claims to DELETE: {len(claims_to_delete)}")
    for cid, reason, data in sorted(claims_to_delete, key=lambda x: x[0]):
        cname = (data.get("claimant") or {}).get("name", "N/A")
        amount = data.get("total_claimed", 0.0)
        print(f"      [DELETE] {cid:24} | ₹{amount:10,.2f} | Claimant: {cname:28} | Reason: {reason}")

    test_claim_ids = {c[0] for c in claims_to_delete}

    # 2. Inspect Dossiers Collection for matched or orphaned dossiers
    print("\nScanning Firestore 'dossiers' collection...")
    dossier_docs = list(fs_client.collection("dossiers").stream())
    dossiers_to_delete: List[Tuple[str, str]] = []
    for d in dossier_docs:
        did = d.id
        if did in test_claim_ids:
            dossiers_to_delete.append((did, f"Belongs to test claim {did}"))
        elif did not in GOLDEN_CLAIM_IDS and not args.skip_orphans:
            is_test, reason = is_test_claim(did, {}, include_all_non_golden=args.include_all_non_golden)
            if is_test or args.include_all_non_golden:
                dossiers_to_delete.append((did, f"Orphaned test dossier ({reason})"))

    print(f"  • Test Dossiers to DELETE: {len(dossiers_to_delete)}")
    for did, reason in sorted(dossiers_to_delete, key=lambda x: x[0]):
        print(f"      [DELETE DOSSIER] {did:24} | Reason: {reason}")

    # 3. Inspect Issuance Ledger
    print("\nScanning Firestore 'issuance_ledger' collection...")
    issuance_docs = list(fs_client.collection("issuance_ledger").stream())
    issuances_to_delete: List[Tuple[str, str, str]] = []
    for doc in issuance_docs:
        doc_id = doc.id
        d = doc.to_dict()
        cid = d.get("claim_id", "")
        # Protect canonical genuine approval for G8
        if doc_id == "SANCTION-G8-GENUINE" or cid == "CLM-G8-ALTERED-DEMO":
            continue
        if cid in test_claim_ids:
            issuances_to_delete.append((doc_id, cid, f"Linked to test claim {cid}"))
        elif not args.skip_orphans:
            if doc_id.startswith(("SANCTION-TEST-", "SANCTION-INJ-", "SANCTION-G8-TEST-")) or "TEST" in cid or "TEST" in doc_id:
                issuances_to_delete.append((doc_id, cid, f"Test issuance document/claim ({cid})"))
            elif cid and cid not in GOLDEN_CLAIM_IDS:
                issuances_to_delete.append((doc_id, cid, f"Non-golden issuance record ({cid})"))

    print(f"  • Test Issuance Records to DELETE: {len(issuances_to_delete)}")
    for doc_id, cid, reason in sorted(issuances_to_delete, key=lambda x: x[0]):
        print(f"      [DELETE ISSUANCE] {doc_id:24} | Claim: {cid:20} | Reason: {reason}")

    # 4. Inspect GCS Objects
    blobs_to_delete: List[Tuple[str, str]] = []
    if not args.skip_gcs:
        print("\nScanning GCS bucket for test files...")
        all_blobs = list(bucket.list_blobs())
        print(f"Found {len(all_blobs)} total blobs in bucket {settings.GCS_BUCKET_NAME}.")

        for b in all_blobs:
            # Absolute guard: Never touch golden claims or preserved claims!
            is_preserved_blob = False
            for gid in GOLDEN_CLAIM_IDS | PRESERVED_CLAIM_IDS:
                if b.name.startswith(f"claims/{gid}/") or b.name.startswith(f"uploads/{gid}/"):
                    is_preserved_blob = True
                    break
            if is_preserved_blob:
                continue

            # Check if blob belongs to a deleted claim ID
            matched = False
            for cid in test_claim_ids:
                if b.name.startswith(f"claims/{cid}/") or b.name.startswith(f"uploads/{cid}/"):
                    blobs_to_delete.append((b.name, f"Belongs to test claim {cid}"))
                    matched = True
                    break

            if not matched and not args.skip_orphans:
                # Check for test run prefix patterns
                if any(p in b.name for p in ("-TEST/", "-ACCEPTANCE/", "-RUN1/", "-AUDIT/", "-THIRD-PARTY/",
                                             "CLM-1/", "CLM-FORGERY-999/", "CLM-INJ-CHECK-007/",
                                             "CLM-SANCTION-G8/", "CLM-TEST-RENDER-150DPI/", "CLM-UNREC-001/",
                                             "CLM-VERIFY-DOCAI-TEST/", "CLM-VISIBLE-001/",
                                             "G1-TEST/", "G2-TEST/", "G2/", "G3-TEST/", "G4-TEST/",
                                             "G5-TEST/", "G6-TEST/", "G7-ACCEPTANCE/", "G7-DISABLED/",
                                             "G7-SANITIZED/", "G7-TEST/", "G9-ACCEPTANCE/", "G9-KILLSWITCH/")):
                    blobs_to_delete.append((b.name, "Test artifact / prefix pattern"))
                elif args.include_all_non_golden:
                    blobs_to_delete.append((b.name, "Non-golden blob"))

        print(f"  • Test GCS Blobs to DELETE: {len(blobs_to_delete)}")
        for bname, reason in sorted(blobs_to_delete, key=lambda x: x[0]):
            print(f"      [DELETE BLOB] {bname} | Reason: {reason}")

    # Summary
    print("\n" + "=" * 80)
    print("CLEANUP TARGET SUMMARY:")
    print(f"  • Firestore Claims to delete:    {len(claims_to_delete)}")
    print(f"  • Firestore Dossiers to delete:  {len(dossiers_to_delete)}")
    print(f"  • Firestore Issuances to delete: {len(issuances_to_delete)}")
    print(f"  • GCS Blobs to delete:           {len(blobs_to_delete)}")
    print("=" * 80)

    if not args.apply:
        print("\n>>> DRY-RUN COMPLETE. NO DATA WAS MODIFIED OR DELETED. <<<")
        print("To execute these deletions, run this script with '--apply'.")
        return

    # Execute deletions
    print("\nExecuting deletions...")

    # Delete Firestore claims
    for cid, _, _ in claims_to_delete:
        doc_ref = fs_client.collection("claims").document(cid)
        delete_firestore_doc_and_subcollections(fs_client, doc_ref)
        print(f"  Deleted Firestore claim and subcollections: {cid}")

    # Delete Firestore dossiers
    for did, _ in dossiers_to_delete:
        fs_client.collection("dossiers").document(did).delete()
        print(f"  Deleted Firestore dossier: {did}")

    # Delete Firestore issuances
    for doc_id, _, _ in issuances_to_delete:
        fs_client.collection("issuance_ledger").document(doc_id).delete()
        print(f"  Deleted Firestore issuance record: {doc_id}")

    # Delete GCS blobs
    for bname, _ in blobs_to_delete:
        blob = bucket.blob(bname)
        try:
            blob.delete()
            print(f"  Deleted GCS blob: {bname}")
        except Exception as e:
            print(f"  Warning: failed to delete blob {bname}: {e}")

    print("\n[SUCCESS] Cleanup applied successfully.")


if __name__ == "__main__":
    main()
