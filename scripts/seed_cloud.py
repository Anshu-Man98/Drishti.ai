#!/usr/bin/env python3
"""
FinShield (Drishti.ai) — Cloud Seeding & Diagnostic Script.

Supports:
  --check:   Pre-flight connectivity and permission tests across all 6 GCP services
             (Firestore, GCS, BigQuery, Document AI, Secret Manager, Gemini API).
             Reports PASS/FAIL with explicit remediation steps.
  --dry-run: Reports all actions that would be executed without mutating cloud resources.
  --apply:   (Default) Idempotently uploads PDFs to GCS, seeds Firestore golden claims,
             seeds BigQuery data warehouse tables, and compiles BQML fraud models.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings

DATA_DIR = PROJECT_ROOT / "data"
DEMO_DIR = DATA_DIR / "demo"
INFRA_DIR = PROJECT_ROOT / "infra"

# 9 Golden Claims Definition
GOLDEN_CLAIMS = [
    {
        "key": "G1",
        "claim_id": "CLM-G1-CLEAN-DEMO",
        "file": "G1_clean_claim.pdf",
        "policy_id": "POL-AROGYA-88124",
        "insurer_id": "INS-HDFC",
        "claimant": {
            "claimant_id": "CLMNT-8921",
            "name": "Rohan Verma",
            "phone": "+91-9876543210",
            "bank_account_hash": "a1b2c3d4e5f60718"
        },
        "provider": {
            "hospital_id": "HOSP-101",
            "name": "Max Super Speciality Hospital",
            "city": "New Delhi",
            "lat": 28.5284,
            "lng": 77.2185
        },
        "doctor_id": "DOC-2045",
        "admission_ts": "2026-03-12T09:30:00",
        "discharge_ts": "2026-03-15T11:00:00",
        "diagnosis_code": "K35.8",
        "subtotal": 71000.0,
        "tax": 3550.0,
        "total_claimed": 74550.0,
        "line_items": [
            {"description": "Semi-Private Room Rent (3 days)", "qty": 3, "unit_price": 4000.0, "amount": 12000.0},
            {"description": "Laparoscopic Appendectomy Surgery & OT", "qty": 1, "unit_price": 45000.0, "amount": 45000.0},
            {"description": "Consultant Surgeon & Anesthetist Visit Fees", "qty": 3, "unit_price": 2000.0, "amount": 6000.0},
            {"description": "Post-Op Pharmacy & Antibiotic Consumables", "qty": 1, "unit_price": 8000.0, "amount": 8000.0}
        ]
    },
    {
        "key": "G2",
        "claim_id": "CLM-G2-ARITHMETIC-DEMO",
        "file": "G2_arithmetic_mismatch.pdf",
        "policy_id": "POL-CARE-55192",
        "insurer_id": "INS-STAR",
        "claimant": {
            "claimant_id": "CLMNT-3310",
            "name": "Sunita Sharma",
            "phone": "+91-9820123456",
            "bank_account_hash": "f9e8d7c6b5a41234"
        },
        "provider": {
            "hospital_id": "HOSP-102",
            "name": "Lifeline Super Speciality Hospital",
            "city": "Mumbai",
            "lat": 19.0596,
            "lng": 72.8295
        },
        "doctor_id": "DOC-2089",
        "admission_ts": "2026-04-14T10:00:00",
        "discharge_ts": "2026-04-18T15:00:00",
        "diagnosis_code": "I20.9",
        "subtotal": 107142.86,
        "tax": 5357.14,
        "total_claimed": 112500.0,
        "line_items": [
            {"description": "Hospital Room Rent (4 days)", "qty": 4, "unit_price": 4500.0, "amount": 18000.0},
            {"description": "ICU Nursing & Critical Care Monitoring", "qty": 1, "unit_price": 25000.0, "amount": 25000.0},
            {"description": "Cardiology Workup, ECG & 2D-Echo", "qty": 1, "unit_price": 32000.0, "amount": 32000.0},
            {"description": "In-Patient Pharmacy & Cardiac Infusions", "qty": 1, "unit_price": 15500.0, "amount": 15500.0}
        ]
    },
    {
        "key": "G3",
        "claim_id": "CLM-G3-POLICYCAP-DEMO",
        "file": "G3_policy_cap_breach.pdf",
        "policy_id": "POL-AROGYA-33219",
        "insurer_id": "INS-ICICI",
        "claimant": {
            "claimant_id": "CLMNT-6520",
            "name": "Vikram Patel",
            "phone": "+91-9845098765",
            "bank_account_hash": "1122334455667788"
        },
        "provider": {
            "hospital_id": "HOSP-103",
            "name": "Metro Healthcare Institute",
            "city": "Bengaluru",
            "lat": 12.9784,
            "lng": 77.6408
        },
        "doctor_id": "DOC-2031",
        "admission_ts": "2026-05-18T08:00:00",
        "discharge_ts": "2026-05-22T12:00:00",
        "diagnosis_code": "K80.2",
        "subtotal": 126500.0,
        "tax": 6325.0,
        "total_claimed": 132825.0,
        "line_items": [
            {"description": "Super Deluxe Executive Suite Room (4 days)", "qty": 4, "unit_price": 14500.0, "amount": 58000.0},
            {"description": "Cholecystectomy Laparoscopic Procedure", "qty": 1, "unit_price": 42000.0, "amount": 42000.0},
            {"description": "Surgeon & Anesthesia Professional Charges", "qty": 1, "unit_price": 15000.0, "amount": 15000.0},
            {"description": "OT Consumables & Surgical Disposables", "qty": 1, "unit_price": 11500.0, "amount": 11500.0}
        ]
    },
    {
        "key": "G4",
        "claim_id": "CLM-G4-CROSSINS-DEMO",
        "file": "G4_cross_insurer_duplicate.pdf",
        "policy_id": "POL-OPTIMA-44102",
        "insurer_id": "INS-NIVA",
        "claimant": {
            "claimant_id": "CLMNT-9901",
            "name": "Ananya Gupta",
            "phone": "+91-9988776655",
            "bank_account_hash": "9988776655443322"
        },
        "provider": {
            "hospital_id": "HOSP-104",
            "name": "Apex Super Speciality Hospital",
            "city": "Hyderabad",
            "lat": 17.4156,
            "lng": 78.4357
        },
        "doctor_id": "DOC-2067",
        "admission_ts": "2026-06-07T11:00:00",
        "discharge_ts": "2026-06-10T16:00:00",
        "diagnosis_code": "S82.8",
        "subtotal": 77000.0,
        "tax": 3850.0,
        "total_claimed": 80850.0,
        "line_items": [
            {"description": "Twin-Sharing Room Rent (3 days)", "qty": 3, "unit_price": 3500.0, "amount": 10500.0},
            {"description": "ORIF Tibia Plating & Fixation Surgery", "qty": 1, "unit_price": 48000.0, "amount": 48000.0},
            {"description": "Orthopedic Surgeon Charges & Visits", "qty": 3, "unit_price": 2000.0, "amount": 6000.0},
            {"description": "Implants & Antibiotics Consumables", "qty": 1, "unit_price": 12500.0, "amount": 12500.0}
        ]
    },
    {
        "key": "G5",
        "claim_id": "CLM-G5-TRAVEL-DEMO",
        "file": "G5_impossible_travel.pdf",
        "policy_id": "POL-CARE-99812",
        "insurer_id": "INS-CARE",
        "claimant": {
            "claimant_id": "CLMNT-7788",
            "name": "Pooja Bhat",
            "phone": "+91-9123456780",
            "bank_account_hash": "aabbccddeeff0011"
        },
        "provider": {
            "hospital_id": "HOSP-105",
            "name": "Apex Super Speciality Hospital",
            "city": "New Delhi",
            "lat": 28.6448,
            "lng": 77.1878
        },
        "doctor_id": "DOC-9021",
        "admission_ts": "2026-07-20T13:30:00",
        "discharge_ts": "2026-07-22T14:00:00",
        "diagnosis_code": "I20.9",
        "subtotal": 142000.0,
        "tax": 7100.0,
        "total_claimed": 149100.0,
        "line_items": [
            {"description": "ICU Room Rent (2 days)", "qty": 2, "unit_price": 6000.0, "amount": 12000.0},
            {"description": "Emergency Angioplasty by Interventional Cardiologist", "qty": 1, "unit_price": 75000.0, "amount": 75000.0},
            {"description": "Lead Cardiologist Procedure & Consultation", "qty": 1, "unit_price": 20000.0, "amount": 20000.0},
            {"description": "Cardiac Stent & Drug-Eluting Catheter", "qty": 1, "unit_price": 35000.0, "amount": 35000.0}
        ]
    },
    {
        "key": "G6",
        "claim_id": "CLM-G6-FORGERY-DEMO",
        "file": "G6_forged_document.pdf",
        "policy_id": "POL-AROGYA-77112",
        "insurer_id": "INS-HDFC",
        "claimant": {
            "claimant_id": "CLMNT-1200",
            "name": "Amit Kulkarni",
            "phone": "+91-9890123456",
            "bank_account_hash": "556677889900aabb"
        },
        "provider": {
            "hospital_id": "HOSP-106",
            "name": "CarePlus Medical Center",
            "city": "Pune",
            "lat": 18.5283,
            "lng": 73.8402
        },
        "doctor_id": "DOC-2051",
        "admission_ts": "2026-08-02T10:00:00",
        "discharge_ts": "2026-08-05T13:00:00",
        "diagnosis_code": "A09",
        "subtotal": 85238.10,
        "tax": 4261.90,
        "total_claimed": 89500.0,
        "line_items": [
            {"description": "General Ward Bed Charges (3 days)", "qty": 3, "unit_price": 2500.0, "amount": 7500.0},
            {"description": "Conservative Medical Management for Colitis", "qty": 1, "unit_price": 12000.0, "amount": 12000.0},
            {"description": "Consultant Physician Daily Visits", "qty": 3, "unit_price": 1500.0, "amount": 4500.0},
            {"description": "IV Fluids & Injectable Antibiotics", "qty": 1, "unit_price": 6000.0, "amount": 6000.0}
        ]
    },
    {
        "key": "G7",
        "claim_id": "CLM-G7-INJECTION-DEMO",
        "file": "G7_prompt_injection.pdf",
        "policy_id": "POL-AROGYA-88124",
        "insurer_id": "INS-HDFC",
        "claimant": {
            "claimant_id": "CLMNT-9081",
            "name": "Rajesh Kumar",
            "phone": "+91-9811098124",
            "bank_account_hash": "c3d4e5f6a1b29988"
        },
        "provider": {
            "hospital_id": "HOSP-101",
            "name": "Max Super Speciality Hospital",
            "city": "New Delhi",
            "lat": 28.5284,
            "lng": 77.2185
        },
        "doctor_id": "DOC-2045",
        "admission_ts": "2026-03-12T09:30:00",
        "discharge_ts": "2026-03-15T11:00:00",
        "diagnosis_code": "K35.8",
        "subtotal": 71000.0,
        "tax": 3550.0,
        "total_claimed": 74550.0,
        "line_items": [
            {"description": "Semi-Private Room Rent (3 days)", "qty": 3, "unit_price": 4000.0, "amount": 12000.0},
            {"description": "Laparoscopic Appendectomy Surgery & OT", "qty": 1, "unit_price": 45000.0, "amount": 45000.0},
            {"description": "Consultant Surgeon & Anesthetist Visit Fees", "qty": 3, "unit_price": 2000.0, "amount": 6000.0},
            {"description": "Post-Op Pharmacy & Antibiotic Consumables", "qty": 1, "unit_price": 8000.0, "amount": 8000.0}
        ]
    },
    {
        "key": "G8",
        "claim_id": "CLM-G8-ALTERED-DEMO",
        "file": "G8_altered_approval.pdf",
        "policy_id": "POL-AROGYA-SANJEEVANI-001",
        "insurer_id": "INS-FINSHIELD",
        "claimant": {
            "claimant_id": "CLMNT-8819",
            "name": "Deepak Mehta",
            "phone": "+91-9876548819",
            "bank_account_hash": "hash_deepak_mehta_8819"
        },
        "provider": {
            "hospital_id": "HOSP-101",
            "name": "Max Super Speciality Hospital",
            "city": "New Delhi",
            "lat": 28.5284,
            "lng": 77.2185
        },
        "doctor_id": "DOC-2045",
        "admission_ts": "2026-03-12T09:30:00",
        "discharge_ts": "2026-03-15T11:00:00",
        "diagnosis_code": "K80.2",
        "subtotal": 476190.48,
        "tax": 23809.52,
        "total_claimed": 500000.0,
        "line_items": [
            {"description": "Sanctioned In-Patient Hospitalization Treatment", "qty": 1, "unit_price": 500000.0, "amount": 500000.0}
        ]
    },
    {
        "key": "G9",
        "claim_id": "CLM-G9-PATTERN-DEMO",
        "file": "G9_pattern_match.pdf",
        "policy_id": "POL-AROGYA-99120",
        "insurer_id": "INS-STAR",
        "claimant": {
            "claimant_id": "CLMNT-5501",
            "name": "Kavita Rao",
            "phone": "+91-9849055012",
            "bank_account_hash": "bank_ring_shared_hash_9999"
        },
        "provider": {
            "hospital_id": "HOSP-110",
            "name": "Apollo Hospitals",
            "city": "Hyderabad",
            "lat": 17.4265,
            "lng": 78.4144
        },
        "doctor_id": "DOC-2033",
        "admission_ts": "2026-05-10T10:00:00",
        "discharge_ts": "2026-05-13T14:00:00",
        "diagnosis_code": "K80.2",
        "subtotal": 71000.0,
        "tax": 3550.0,
        "total_claimed": 74550.0,
        "line_items": [
            {"description": "Semi-Private Room Rent (3 days)", "qty": 3, "unit_price": 4000.0, "amount": 12000.0},
            {"description": "Laparoscopic Cholecystectomy Procedure", "qty": 1, "unit_price": 45000.0, "amount": 45000.0},
            {"description": "Consultant Surgeon & Anesthetist Visit Fees", "qty": 3, "unit_price": 2000.0, "amount": 6000.0},
            {"description": "Post-Op Pharmacy & Surgical Consumables", "qty": 1, "unit_price": 8000.0, "amount": 8000.0}
        ]
    }
]


def run_checks() -> int:
    """Pre-flight check for all 6 Google Cloud services."""
    print("=" * 70)
    print("🔍 FINSHIELD CLOUD CONNECTIVITY & PRE-FLIGHT DIAGNOSTICS")
    print("=" * 70)
    print(f"Project ID:       {settings.GCP_PROJECT}")
    print(f"Region:           {settings.GCP_REGION}")
    print(f"GCS Bucket:       {settings.GCS_BUCKET_NAME}")
    print(f"Firestore DB:     {settings.FIRESTORE_DATABASE}")
    print(f"BigQuery Dataset: {settings.BIGQUERY_DATASET}")
    print(f"Gemini Model:     {settings.GEMINI_FLASH_MODEL}")
    print("-" * 70)

    all_passed = True

    # 1. Cloud Firestore Check
    try:
        from google.cloud import firestore
        fs_client = firestore.Client(
            project=settings.GCP_PROJECT,
            database=settings.FIRESTORE_DATABASE
        )
        # Ping test: get non-existent test document
        fs_client.collection("_ping_check").document("health").get()
        print("✅ [PASS] Cloud Firestore: Connected and authenticated")
    except Exception as e:
        all_passed = False
        print(f"❌ [FAIL] Cloud Firestore: {e}")
        print("   👉 Remediation: Run 'gcloud auth application-default login' and verify")
        print(f"      'gcloud firestore databases create --location={settings.GCP_REGION} --type=firestore-native'")

    # 2. Cloud Storage Check
    try:
        from google.cloud import storage
        gcs_client = storage.Client(project=settings.GCP_PROJECT)
        bucket = gcs_client.lookup_bucket(settings.GCS_BUCKET_NAME)
        if bucket:
            print(f"✅ [PASS] Cloud Storage: Bucket 'gs://{settings.GCS_BUCKET_NAME}' verified and accessible")
        else:
            all_passed = False
            print(f"❌ [FAIL] Cloud Storage: Bucket 'gs://{settings.GCS_BUCKET_NAME}' not found")
            print(f"   👉 Remediation: Run 'gcloud storage buckets create gs://{settings.GCS_BUCKET_NAME} --location={settings.GCP_REGION} --uniform-bucket-level-access'")
    except Exception as e:
        all_passed = False
        print(f"❌ [FAIL] Cloud Storage: {e}")
        print("   👉 Remediation: Run 'gcloud auth application-default login' and ensure storage permissions.")

    # 3. BigQuery Check
    try:
        from google.cloud import bigquery
        bq_client = bigquery.Client(project=settings.GCP_PROJECT, location=settings.GCP_REGION)
        # Check dataset exists
        try:
            bq_client.get_dataset(settings.BIGQUERY_DATASET)
            print(f"✅ [PASS] BigQuery: Dataset '{settings.BIGQUERY_DATASET}' accessible")
        except Exception:
            all_passed = False
            print(f"❌ [FAIL] BigQuery: Dataset '{settings.BIGQUERY_DATASET}' does not exist")
            print(f"   👉 Remediation: Run 'bq mk --location={settings.GCP_REGION} --dataset {settings.GCP_PROJECT}:{settings.BIGQUERY_DATASET}'")
            print(f"      and run DDL: 'bq query --use_legacy_sql=false < infra/bigquery.sql'")
        # Quick query test
        query_job = bq_client.query("SELECT 1 AS health_check")
        rows = list(query_job.result())
        if rows and rows[0].health_check == 1:
            print("✅ [PASS] BigQuery: Query engine functional")
    except Exception as e:
        all_passed = False
        print(f"❌ [FAIL] BigQuery: {e}")
        print("   👉 Remediation: Verify BigQuery API is enabled and roles/bigquery.admin is assigned.")

    # 4. Document AI Check
    try:
        from google.cloud import documentai
        docai_client = documentai.DocumentProcessorServiceClient()
        proc_id = settings.DOCUMENTAI_PROCESSOR_ID
        if proc_id:
            try:
                proc_name = f"projects/{settings.GCP_PROJECT}/locations/us/processors/{proc_id}"
                docai_client.get_processor(name=proc_name)
                print(f"✅ [PASS] Document AI: Processor '{proc_id}' verified (location: us)")
            except Exception as pe:
                all_passed = False
                print(f"❌ [FAIL] Document AI Processor '{proc_id}': {pe}")
                print("   👉 Remediation: Verify processor ID exists in Google Cloud Document AI Console (location: us or eu).")
        else:
            all_passed = False
            print("⚠️ [FAIL] Document AI: DOCUMENTAI_PROCESSOR_ID not configured in .env")
            print("   👉 Remediation: Run 'gcloud documentai processors create --location=us --type=INVOICE_PROCESSOR --display-name=finshield-invoice-parser'")
            print("      and set DOCUMENTAI_PROCESSOR_ID=<id> in .env")
    except Exception as e:
        all_passed = False
        print(f"❌ [FAIL] Document AI: {e}")
        print("   👉 Remediation: Ensure documentai.googleapis.com is enabled and ADC is logged in.")

    # 5. Secret Manager Check
    try:
        from google.cloud import secretmanager
        sm_client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{settings.GCP_PROJECT}/secrets/finshield-provenance-signing-key/versions/latest"
        try:
            resp = sm_client.access_secret_version(name=secret_name)
            key_val = resp.payload.data.decode("utf-8")
            if len(key_val) >= 32:
                print("✅ [PASS] Secret Manager: 'finshield-provenance-signing-key' accessible")
            else:
                print("⚠️ [WARN] Secret Manager: Secret found but length < 32 chars")
        except Exception as se:
            all_passed = False
            print(f"❌ [FAIL] Secret Manager 'finshield-provenance-signing-key': {se}")
            print("   👉 Remediation: Run 'openssl rand -hex 32 | gcloud secrets create finshield-provenance-signing-key --data-file=-'")
    except Exception as e:
        all_passed = False
        print(f"❌ [FAIL] Secret Manager: {e}")
        print("   👉 Remediation: Verify secretmanager.googleapis.com is enabled.")

    # 6. Gemini Live API Check
    try:
        from google import genai
        key = settings.GOOGLE_API_KEY
        if not key:
            all_passed = False
            print("❌ [FAIL] Gemini API: GOOGLE_API_KEY is not set in environment or .env")
            print("   👉 Remediation: Set GOOGLE_API_KEY in .env (from Google AI Studio or Vertex AI)")
        else:
            ai_client = genai.Client(api_key=key)
            resp = ai_client.models.generate_content(
                model=settings.GEMINI_FLASH_MODEL,
                contents="Ping test. Respond with OK."
            )
            if resp and resp.text:
                print(f"✅ [PASS] Gemini API: Live connection verified with model '{settings.GEMINI_FLASH_MODEL}'")
            else:
                all_passed = False
                print(f"❌ [FAIL] Gemini API: Empty response from model '{settings.GEMINI_FLASH_MODEL}'")
    except Exception as e:
        all_passed = False
        print(f"❌ [FAIL] Gemini API: {e}")
        print(f"   👉 Remediation: Check that model '{settings.GEMINI_FLASH_MODEL}' is active and API key has quota.")

    print("-" * 70)
    if all_passed:
        print("🎉 ALL 6 CLOUD SERVICES PASSED PRE-FLIGHT VERIFICATION!")
        return 0
    else:
        print("⚠️ SOME PRE-FLIGHT CHECKS FAILED. Review remediation steps above.")
        return 1


def run_dry_run() -> int:
    """Inspects files and prints actions that would be taken without mutating cloud state."""
    print("=" * 70)
    print("📋 FINSHIELD CLOUD SEEDING — DRY RUN MODE (NO MUTATIONS)")
    print("=" * 70)
    print(f"Target Project:   {settings.GCP_PROJECT}")
    print(f"Target Bucket:    gs://{settings.GCS_BUCKET_NAME}")
    print(f"Target BigQuery:  {settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}")
    print(f"Target Firestore: {settings.FIRESTORE_DATABASE} / collection 'claims'")
    print("-" * 70)

    # 1. Check local demo PDFs
    print("\n[1/4] Inspecting Local Golden Claim PDFs:")
    missing_files = []
    for claim in GOLDEN_CLAIMS:
        pdf_path = DEMO_DIR / claim["file"]
        status = "FOUND" if pdf_path.exists() else "MISSING"
        size = f"({pdf_path.stat().st_size:,} bytes)" if pdf_path.exists() else ""
        pdf_bytes = pdf_path.read_bytes() if pdf_path.exists() else b""
        real_sha256 = hashlib.sha256(pdf_bytes).hexdigest() if pdf_bytes else "unknown"
        target_gcs = f"gs://{settings.GCS_BUCKET_NAME}/uploads/{claim['claim_id']}/{real_sha256}.pdf"
        print(f"  • {claim['key']} [{claim['claim_id']}]: {claim['file']} -> {status} {size}")
        print(f"    Target GCS: {target_gcs}")
        if not pdf_path.exists():
            missing_files.append(claim["file"])

    # 2. Inspect Firestore Documents to be written
    print(f"\n[2/4] Planned Firestore Writes (Collection: 'claims'):")
    print(f"  • Total Golden Claims to Seed: {len(GOLDEN_CLAIMS)}")
    for claim in GOLDEN_CLAIMS:
        print(f"    - Doc ID: {claim['claim_id']} (Key: {claim['key']}, Claimant: {claim['claimant']['name']}, Claimed: ₹{claim['total_claimed']:,.2f})")

    # 3. Inspect BigQuery Data Sources
    print("\n[3/4] Inspecting BigQuery Data Warehouse Sources:")
    bq_sources = [
        ("finshield.claims", DATA_DIR / "claims.jsonl", "JSONL"),
        ("finshield.line_items", DATA_DIR / "line_items.jsonl", "JSONL"),
        ("finshield.doctor_events", DATA_DIR / "doctor_events.jsonl", "JSONL"),
        ("finshield.ext_provider_fraud", DATA_DIR / "external" / "kaggle_provider_fraud" / "ext_provider_fraud.csv", "CSV")
    ]
    for table_name, src_path, fmt in bq_sources:
        if src_path.exists():
            with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = sum(1 for _ in f)
            print(f"  • Table '{table_name}': {src_path.name} ({lines:,} records, {fmt}) -> READY TO LOAD")
        else:
            print(f"  • Table '{table_name}': {src_path} -> MISSING")
            missing_files.append(str(src_path))

    # 4. Inspect BQML Models
    print("\n[4/4] Planned BigQuery ML Models (from infra/bqml.sql):")
    bqml_sql_path = INFRA_DIR / "bqml.sql"
    if bqml_sql_path.exists():
        print(f"  • DDL Script: {bqml_sql_path} ({bqml_sql_path.stat().st_size:,} bytes)")
        print(f"    - Model 1: `{settings.BIGQUERY_DATASET}.fraud_model` (BOOSTED_TREE_CLASSIFIER on finshield.claims)")
        print(f"    - Model 2: `{settings.BIGQUERY_DATASET}.provider_fraud_model` (BOOSTED_TREE_CLASSIFIER on Medicare provider dataset)")
    else:
        print(f"  • DDL Script: {bqml_sql_path} -> MISSING")
        missing_files.append(str(bqml_sql_path))

    print("\n" + "-" * 70)
    if missing_files:
        print(f"⚠️ DRY RUN FOUND {len(missing_files)} MISSING LOCAL ASSETS:")
        for mf in missing_files:
            print(f"   - {mf}")
        return 1
    else:
        print("✅ DRY RUN VERIFICATION COMPLETED: All 9 PDFs and data sources are valid and ready for seeding.")
        print("   To execute real cloud writes, run: python scripts/seed_cloud.py --apply")
        return 0


def run_apply() -> int:
    """Executes live idempotent seeding of GCS, Firestore, BigQuery, and BQML."""
    print("=" * 70)
    print("🚀 FINSHIELD LIVE CLOUD SEEDING (PURE CLOUD MODE)")
    print("=" * 70)
    print(f"GCP Project:      {settings.GCP_PROJECT}")
    print(f"GCS Bucket:       {settings.GCS_BUCKET_NAME}")
    print(f"Firestore DB:     {settings.FIRESTORE_DATABASE}")
    print(f"BigQuery Dataset: {settings.BIGQUERY_DATASET}")
    print("-" * 70)

    summary = {
        "gcs_uploaded": 0,
        "gcs_existing": 0,
        "firestore_written": 0,
        "bigquery_loaded": [],
        "bqml_models": [],
        "errors": []
    }

    # Step 1: Upload 9 Golden PDFs to GCS
    # Step 1: Upload 9 Golden PDFs to GCS & Pre-render Page Images
    print("\n[1/4] Uploading Golden PDFs to Google Cloud Storage & Pre-rendering Page Previews...")
    try:
        import hashlib
        import io
        import pypdf
        from google.cloud import storage
        from backend.tools.docai import render_pdf_to_page_images

        gcs_client = storage.Client(project=settings.GCP_PROJECT)
        bucket = gcs_client.get_bucket(settings.GCS_BUCKET_NAME)

        for claim in GOLDEN_CLAIMS:
            pdf_path = DEMO_DIR / claim["file"]
            if not pdf_path.exists():
                err = f"PDF {claim['file']} missing on disk"
                print(f"  ❌ {err}")
                summary["errors"].append(err)
                continue

            pdf_bytes = pdf_path.read_bytes()
            real_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

            # Upload primary original PDF
            blob_name = f"claims/{claim['claim_id']}/original.pdf"
            blob = bucket.blob(blob_name)
            if blob.exists():
                print(f"  ℹ️ GCS: {blob_name} already exists")
                summary["gcs_existing"] += 1
            else:
                blob.upload_from_string(pdf_bytes, content_type="application/pdf")
                print(f"  ✅ GCS: Uploaded {pdf_path.name} -> gs://{settings.GCS_BUCKET_NAME}/{blob_name}")
                summary["gcs_uploaded"] += 1

            # Upload hash-addressed blob for sha256 lookups
            hash_blob_name = f"uploads/{claim['claim_id']}/{real_sha256}.pdf"
            hash_blob = bucket.blob(hash_blob_name)
            if not hash_blob.exists():
                hash_blob.upload_from_string(pdf_bytes, content_type="application/pdf")

            # Upload canonical uploads/{claim_id}/original.pdf
            upload_orig_name = f"uploads/{claim['claim_id']}/original.pdf"
            upload_orig_blob = bucket.blob(upload_orig_name)
            if not upload_orig_blob.exists():
                upload_orig_blob.upload_from_string(pdf_bytes, content_type="application/pdf")

            # Pre-render 150 DPI page preview images into GCS
            try:
                render_pdf_to_page_images(pdf_bytes, claim["claim_id"])
                print(f"  🖼️ GCS: Pre-rendered page preview images for {claim['claim_id']}")
            except Exception as pe:
                print(f"  ⚠️ Warning rendering page preview for {claim['claim_id']}: {pe}")

    except Exception as e:
        err = f"GCS Upload failed: {e}"
        print(f"  ❌ {err}")
        summary["errors"].append(err)

    # Step 2: Seed 9 Golden Claims into Cloud Firestore
    print("\n[2/4] Seeding Golden Claims into Cloud Firestore...")
    try:
        from google.cloud import firestore
        fs_client = firestore.Client(
            project=settings.GCP_PROJECT,
            database=settings.FIRESTORE_DATABASE
        )

        for claim in GOLDEN_CLAIMS:
            claim_id = claim["claim_id"]
            doc_ref = fs_client.collection("claims").document(claim_id)

            pdf_path = DEMO_DIR / claim["file"]
            pdf_bytes = pdf_path.read_bytes() if pdf_path.exists() else b""
            real_sha256 = hashlib.sha256(pdf_bytes).hexdigest() if pdf_bytes else "unknown"
            page_count = 1
            if pdf_bytes:
                try:
                    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                    page_count = max(1, len(reader.pages))
                except Exception:
                    page_count = 1

            # Build full Claim schema dictionary
            doc_payload = {
                "claim_id": claim_id,
                "policy_id": claim["policy_id"],
                "insurer_id": claim["insurer_id"],
                "claimant": claim["claimant"],
                "provider": claim["provider"],
                "doctor_id": claim["doctor_id"],
                "admission_ts": claim["admission_ts"],
                "discharge_ts": claim["discharge_ts"],
                "diagnosis_code": claim["diagnosis_code"],
                "subtotal": claim["subtotal"],
                "tax": claim["tax"],
                "total_claimed": claim["total_claimed"],
                "line_items": [
                    {
                        "description": item["description"],
                        "qty": float(item["qty"]),
                        "unit_price": float(item["unit_price"]),
                        "amount": float(item["amount"]),
                        "page": 1,
                        "source": "docai"
                    }
                    for item in claim["line_items"]
                ],
                "documents": [
                    {
                        "doc_id": f"DOC-{claim_id}-ORIGINAL",
                        "gcs_uri": f"gs://{settings.GCS_BUCKET_NAME}/uploads/{claim_id}/{real_sha256}.pdf",
                        "doc_type": "approval_letter" if claim["key"] == "G8" else "bill",
                        "sha256": real_sha256,
                        "filename": claim["file"],
                        "page_count": page_count
                    }
                ],
                "extracted_entities": [],
                "field_sources": {
                    "claimant_name": "docai",
                    "total_claimed": "docai",
                    "line_items": "docai"
                },
                "created_at": datetime.utcnow().isoformat(),
                "golden_key": claim["key"]
            }

            doc_ref.set(doc_payload, merge=True)
            print(f"  ✅ Firestore: Seeded {claim_id} ({claim['key']} - {claim['claimant']['name']})")
            summary["firestore_written"] += 1

        # Seed genuine issuance ledger entry for G8 (both demo ID and test alias)
        fs_client.collection("issuance_ledger").document("SANCTION-G8-GENUINE").set({
            "doc_id": "SANCTION-G8-GENUINE",
            "claim_id": "CLM-G8-ALTERED-DEMO",
            "claimant_id": "CLMNT-8819",
            "amount_paise": 5000000,
            "doc_type": "approval_letter",
            "carrier": "xmp",
            "issuer": "FINSHIELD-DEMO",
            "issued_at": "2026-03-12T09:30:00Z"
        }, merge=True)
        fs_client.collection("issuance_ledger").document("SANCTION-G8-TEST-ALIAS").set({
            "doc_id": "SANCTION-G8-GENUINE",
            "claim_id": "CLM-SANCTION-G8",
            "claimant_id": "CLMNT-8819",
            "amount_paise": 5000000,
            "doc_type": "approval_letter",
            "carrier": "xmp",
            "issuer": "FINSHIELD-DEMO",
            "issued_at": "2026-03-12T09:30:00Z"
        }, merge=True)
        print(f"  ✅ Firestore: Seeded genuine issuance ledger for SANCTION-G8-GENUINE")

    except Exception as e:
        err = f"Firestore write failed: {e}"
        print(f"  ❌ {err}")
        summary["errors"].append(err)

    # Step 3: BigQuery DDL & Data Population
    print("\n[3/4] Seeding BigQuery Data Warehouse Tables...")
    try:
        from google.cloud import bigquery
        bq_client = bigquery.Client(project=settings.GCP_PROJECT, location=settings.GCP_REGION)

        # Ensure schema DDL has been applied
        bq_ddl_path = INFRA_DIR / "bigquery.sql"
        if bq_ddl_path.exists():
            with open(bq_ddl_path, "r", encoding="utf-8") as f:
                ddl_statements = f.read()
            bq_client.query(ddl_statements).result()
            print(f"  ✅ BigQuery: Executed schema DDL from {bq_ddl_path.name}")

        # Helper to load table if empty
        def load_if_empty(table_name: str, file_path: Path, is_jsonl: bool):
            full_table_id = f"{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.{table_name}"
            # Check row count
            count_query = f"SELECT COUNT(1) AS cnt FROM `{full_table_id}`"
            try:
                result = list(bq_client.query(count_query).result())
                cnt = result[0].cnt if result else 0
            except Exception:
                cnt = 0

            if cnt > 0:
                print(f"  ℹ️ BigQuery table '{table_name}' already contains {cnt:,} rows (skipping load)")
                summary["bigquery_loaded"].append(f"{table_name}: already had {cnt} rows")
                return

            if not file_path.exists():
                print(f"  ⚠️ BigQuery source file {file_path} missing")
                return

            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON if is_jsonl else bigquery.SourceFormat.CSV,
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND
            )
            if not is_jsonl:
                job_config.skip_leading_rows = 1
                job_config.autodetect = False

            with open(file_path, "rb") as source_file:
                job = bq_client.load_table_from_file(source_file, full_table_id, job_config=job_config)
                job.result()  # Wait for job completion

            print(f"  ✅ BigQuery: Loaded data from {file_path.name} into '{table_name}' ({job.output_rows} rows)")
            summary["bigquery_loaded"].append(f"{table_name}: loaded {job.output_rows} rows")

        load_if_empty("claims", DATA_DIR / "claims.jsonl", is_jsonl=True)
        load_if_empty("line_items", DATA_DIR / "line_items.jsonl", is_jsonl=True)
        load_if_empty("doctor_events", DATA_DIR / "doctor_events.jsonl", is_jsonl=True)
        load_if_empty("ext_provider_fraud", DATA_DIR / "external" / "kaggle_provider_fraud" / "ext_provider_fraud.csv", is_jsonl=False)

    except Exception as e:
        err = f"BigQuery seeding failed: {e}"
        print(f"  ❌ {err}")
        summary["errors"].append(err)

    # Step 4: BigQuery ML Model Compilation
    print("\n[4/4] Training / Replacing BigQuery ML Models...")
    try:
        from google.cloud import bigquery
        bq_client = bigquery.Client(project=settings.GCP_PROJECT, location=settings.GCP_REGION)

        # Check if BQML models already exist to keep script fast and idempotent
        fraud_model_id = f"{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.fraud_model"
        prov_model_id = f"{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.provider_fraud_model"
        models_exist = False
        try:
            m1 = bq_client.get_model(fraud_model_id)
            m2 = bq_client.get_model(prov_model_id)
            if m1 and m2:
                models_exist = True
                print(f"  ℹ️ BigQuery ML: Models 'fraud_model' and 'provider_fraud_model' already exist (skipping redundant training)")
                summary["bqml_models"].append("finshield.fraud_model (existing)")
                summary["bqml_models"].append("finshield.provider_fraud_model (existing)")
        except Exception:
            models_exist = False

        if not models_exist:
            bqml_sql_path = INFRA_DIR / "bqml.sql"
            if bqml_sql_path.exists():
                with open(bqml_sql_path, "r", encoding="utf-8") as f:
                    bqml_script = f.read()

                print("  ⏳ Submitting BigQuery ML training queries (this may take 1-2 minutes)...")
                job = bq_client.query(bqml_script)
                job.result()
                print(f"  ✅ BigQuery ML: Successfully created fraud_model and provider_fraud_model")
                summary["bqml_models"].append("finshield.fraud_model")
                summary["bqml_models"].append("finshield.provider_fraud_model")
            else:
                print(f"  ⚠️ BQML script missing at {bqml_sql_path}")

    except Exception as e:
        err = f"BQML training failed: {e}"
        print(f"  ❌ {err}")
        summary["errors"].append(err)

    # Final Summary
    print("\n" + "=" * 70)
    print("📊 CLOUD SEEDING DIAGNOSTIC SUMMARY")
    print("=" * 70)
    print(f"• GCS Uploads:        {summary['gcs_uploaded']} uploaded, {summary['gcs_existing']} already existed")
    print(f"• Firestore Claims:   {summary['firestore_written']} claims written / updated")
    print(f"• BigQuery Tables:    {len(summary['bigquery_loaded'])} tables seeded/checked")
    print(f"• BQML Models:        {len(summary['bqml_models'])} models compiled")
    print(f"• Errors Encountered: {len(summary['errors'])}")
    if summary["errors"]:
        print("\nErrors:")
        for err in summary["errors"]:
            print(f"  ❌ {err}")
        return 1

    print("\n🎉 LIVE CLOUD SEEDING COMPLETED SUCCESSFULLY!")
    return 0


def main():
    parser = argparse.ArgumentParser(description="FinShield Cloud Seeding & Diagnostic Utility")
    parser.add_argument("--check", action="store_true", help="Perform pre-flight connectivity checks across all 6 GCP services")
    parser.add_argument("--dry-run", action="store_true", help="Inspect local assets and preview cloud actions without mutating cloud resources")
    parser.add_argument("--apply", action="store_true", help="Execute live cloud seeding (idempotent)")

    args = parser.parse_args()

    if args.check:
        sys.exit(run_checks())
    elif args.dry_run:
        sys.exit(run_dry_run())
    else:
        # Default is --apply if neither --check nor --dry-run
        sys.exit(run_apply())


if __name__ == "__main__":
    main()
