"""
Seed script to load the 6 Golden Demo Claims into FinShield via the FastAPI API.
Runs against local API or deployed Cloud Run API (configured via FINSHIELD_API_URL).
"""

import os
import json
from pathlib import Path
import httpx

API_BASE_URL = os.getenv("FINSHIELD_API_URL", "http://127.0.0.1:8000")
DATA_DIR = Path(__file__).resolve().parent
DEMO_DIR = DATA_DIR / "demo"

GOLDEN_CLAIMS = [
    {
        "key": "G1",
        "file": "G1_clean_claim.pdf",
        "policy_id": "POL-AROGYA-88124",
        "insurer_id": "INS-HDFC",
        "claimant_id": "CLMNT-8921",
        "claimant_name": "Rohan Verma",
        "claimant_phone": "+91-9876543210",
        "bank_account_hash": "a1b2c3d4e5f60718",
        "hospital_id": "HOSP-101",
        "hospital_name": "Max Super Speciality Hospital",
        "city": "New Delhi",
        "lat": 28.5284,
        "lng": 77.2185,
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
        "file": "G2_arithmetic_mismatch.pdf",
        "policy_id": "POL-CARE-55192",
        "insurer_id": "INS-STAR",
        "claimant_id": "CLMNT-3310",
        "claimant_name": "Sunita Sharma",
        "claimant_phone": "+91-9820123456",
        "bank_account_hash": "f9e8d7c6b5a41234",
        "hospital_id": "HOSP-102",
        "hospital_name": "Lifeline Super Speciality Hospital",
        "city": "Mumbai",
        "lat": 19.0596,
        "lng": 72.8295,
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
        "file": "G3_policy_cap_breach.pdf",
        "policy_id": "POL-AROGYA-33219",
        "insurer_id": "INS-ICICI",
        "claimant_id": "CLMNT-6520",
        "claimant_name": "Vikram Patel",
        "claimant_phone": "+91-9845098765",
        "bank_account_hash": "1122334455667788",
        "hospital_id": "HOSP-103",
        "hospital_name": "Metro Healthcare Institute",
        "city": "Bengaluru",
        "lat": 12.9784,
        "lng": 77.6408,
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
        "file": "G4_cross_insurer_duplicate.pdf",
        "policy_id": "POL-OPTIMA-44102",
        "insurer_id": "INS-NIVA",
        "claimant_id": "CLMNT-9901",
        "claimant_name": "Ananya Gupta",
        "claimant_phone": "+91-9988776655",
        "bank_account_hash": "9988776655443322",
        "hospital_id": "HOSP-104",
        "hospital_name": "Apex Super Speciality Hospital",
        "city": "Hyderabad",
        "lat": 17.4156,
        "lng": 78.4357,
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
        "file": "G5_impossible_travel.pdf",
        "policy_id": "POL-CARE-99812",
        "insurer_id": "INS-CARE",
        "claimant_id": "CLMNT-7788",
        "claimant_name": "Pooja Bhat",
        "claimant_phone": "+91-9123456780",
        "bank_account_hash": "aabbccddeeff0011",
        "hospital_id": "HOSP-105",
        "hospital_name": "Apex Super Speciality Hospital",
        "city": "New Delhi",
        "lat": 28.6448,
        "lng": 77.1878,
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
        "file": "G6_forged_document.pdf",
        "policy_id": "POL-AROGYA-77112",
        "insurer_id": "INS-HDFC",
        "claimant_id": "CLMNT-1200",
        "claimant_name": "Amit Kulkarni",
        "claimant_phone": "+91-9890123456",
        "bank_account_hash": "556677889900aabb",
        "hospital_id": "HOSP-106",
        "hospital_name": "CarePlus Medical Center",
        "city": "Pune",
        "lat": 18.5283,
        "lng": 73.8402,
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
        "file": "G7_prompt_injection.pdf",
        "policy_id": "POL-AROGYA-88124",
        "insurer_id": "INS-HDFC",
        "claimant_id": "CLMNT-9081",
        "claimant_name": "Rajesh Kumar",
        "claimant_phone": "+91-9811098124",
        "bank_account_hash": "c3d4e5f6a1b29988",
        "hospital_id": "HOSP-101",
        "hospital_name": "Max Super Speciality Hospital",
        "city": "New Delhi",
        "lat": 28.5284,
        "lng": 77.2185,
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
        "key": "G9",
        "file": "G9_pattern_match.pdf",
        "policy_id": "POL-AROGYA-99120",
        "insurer_id": "INS-STAR",
        "claimant_id": "CLMNT-5501",
        "claimant_name": "Kavita Rao",
        "claimant_phone": "+91-9849055012",
        "bank_account_hash": "bank_ring_shared_hash_9999",
        "hospital_id": "HOSP-110",
        "hospital_name": "Apollo Hospitals",
        "city": "Hyderabad",
        "lat": 17.4265,
        "lng": 78.4144,
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


def seed_claims():
    print(f"🚀 Seeding Golden Claims into {API_BASE_URL}...")
    seeded_ids = {}

    with httpx.Client(timeout=30.0) as client:
        # Check API health
        try:
            health = client.get(f"{API_BASE_URL}/health")
            if health.status_code != 200:
                print(f"❌ API not healthy: {health.status_code} {health.text}")
                return
        except Exception as e:
            print(f"❌ Cannot connect to API at {API_BASE_URL}: {e}")
            return

        for item in GOLDEN_CLAIMS:
            pdf_path = DEMO_DIR / item["file"]
            if not pdf_path.exists():
                print(f"❌ PDF file not found: {pdf_path}")
                continue

            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            files = [("files", (item["file"], pdf_bytes, "application/pdf"))]
            data = {
                "policy_id": item["policy_id"],
                "insurer_id": item["insurer_id"],
                "claimant_id": item["claimant_id"],
                "claimant_name": item["claimant_name"],
                "claimant_phone": item["claimant_phone"],
                "bank_account_hash": item["bank_account_hash"],
                "hospital_id": item["hospital_id"],
                "hospital_name": item["hospital_name"],
                "city": item["city"],
                "lat": str(item["lat"]),
                "lng": str(item["lng"]),
                "doctor_id": item["doctor_id"],
                "admission_ts": item["admission_ts"],
                "discharge_ts": item["discharge_ts"],
                "diagnosis_code": item["diagnosis_code"],
                "subtotal": str(item["subtotal"]),
                "tax": str(item["tax"]),
                "total_claimed": str(item["total_claimed"]),
                "line_items_json": json.dumps(item["line_items"])
            }

            resp = client.post(f"{API_BASE_URL}/claims", data=data, files=files)
            if resp.status_code == 200:
                claim_id = resp.json()["claim_id"]
                seeded_ids[item["key"]] = claim_id
                print(f"✅ Loaded {item['key']} ({item['file']}) -> Claim ID: {claim_id}")

                # Trigger analyze
                an_resp = client.post(f"{API_BASE_URL}/claims/{claim_id}/analyze")
                if an_resp.status_code == 200:
                    dossier = an_resp.json()
                    print(f"   Dossier initialized: verdict={dossier['verdict']}, risk_score={dossier['risk_score']}")
            else:
                print(f"❌ Failed to load {item['key']}: {resp.status_code} {resp.text}")

    # Save mapping
    with open(DATA_DIR / "seeded_golden_claims.json", "w") as f_out:
        json.dump(seeded_ids, f_out, indent=2)

    print(f"\n🎉 Successfully seeded {len(seeded_ids)} golden claims!")
    return seeded_ids


if __name__ == "__main__":
    seed_claims()
