"""
Synthetic claims, line items, and doctor events generator for FinShield (Drishti.ai).
Generates ~3,000 synthetic claims across 5 insurers, 40 fictional hospitals in 12 Indian cities,
150 fictional doctors, and 2,000 claimants with ~12% labeled fraud types and engineered ML features.
"""

import os
import json
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

random.seed(42)

DATA_DIR = Path(__file__).resolve().parent
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 12 Indian cities with authentic coordinates
CITIES = [
    {"city": "Mumbai", "lat": 18.9388, "lng": 72.8353},
    {"city": "New Delhi", "lat": 28.6139, "lng": 77.2090},
    {"city": "Bengaluru", "lat": 12.9716, "lng": 77.5946},
    {"city": "Hyderabad", "lat": 17.3850, "lng": 78.4867},
    {"city": "Chennai", "lat": 13.0827, "lng": 80.2707},
    {"city": "Kolkata", "lat": 22.5726, "lng": 88.3639},
    {"city": "Pune", "lat": 18.5204, "lng": 73.8567},
    {"city": "Ahmedabad", "lat": 23.0225, "lng": 72.5714},
    {"city": "Jaipur", "lat": 26.9124, "lng": 75.7873},
    {"city": "Chandigarh", "lat": 30.7333, "lng": 76.7794},
    {"city": "Lucknow", "lat": 26.8467, "lng": 80.9462},
    {"city": "Kochi", "lat": 9.9312, "lng": 76.2673},
]

INSURERS = [
    {"id": "INS-STAR", "name": "Star Health & Allied Insurance"},
    {"id": "INS-HDFC", "name": "HDFC ERGO General Insurance"},
    {"id": "INS-ICICI", "name": "ICICI Lombard Health"},
    {"id": "INS-CARE", "name": "Care Health Insurance"},
    {"id": "INS-NIVA", "name": "Niva Bupa Health Insurance"},
]

HOSPITAL_PREFIXES = ["Apex", "Lifeline", "Metro", "CarePlus", "Suraksha", "Heritage", "Medinova", "Global"]
HOSPITAL_TYPES = ["Hospital", "Healthcare Institute", "Super Speciality Hospital", "Medical Center"]

# Generate 40 fictional hospitals
HOSPITALS = []
for i in range(40):
    city_info = CITIES[i % len(CITIES)]
    prefix = HOSPITAL_PREFIXES[i % len(HOSPITAL_PREFIXES)]
    htype = HOSPITAL_TYPES[(i // len(HOSPITAL_PREFIXES)) % len(HOSPITAL_TYPES)]
    # jitter coordinates slightly (up to ~3-4 km)
    lat_jitter = random.uniform(-0.03, 0.03)
    lng_jitter = random.uniform(-0.03, 0.03)
    HOSPITALS.append({
        "hospital_id": f"HOSP-{100 + i}",
        "name": f"{prefix} {htype}",
        "city": city_info["city"],
        "lat": round(city_info["lat"] + lat_jitter, 5),
        "lng": round(city_info["lng"] + lng_jitter, 5)
    })

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Ananya", "Diya", "Saanvi", "Aadhya", "Pari", "Chiara", "Myra", "Anika", "Navya", "Riya",
    "Rajesh", "Suresh", "Amit", "Pooja", "Sunita", "Deepak", "Sneha", "Kavita", "Vikram", "Priyanka"
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Mehta", "Iyer", "Nair", "Kapoor", "Chatterjee", "Gupta",
    "Bose", "Joshi", "Choudhury", "Bhat", "Deshmukh", "Pillai", "Menon", "Saxena", "Mishra", "Kulkarni"
]

# Generate 150 fictional doctors
DOCTORS = []
for i in range(150):
    name = f"Dr. {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    primary_hospital = random.choice(HOSPITALS)
    DOCTORS.append({
        "doctor_id": f"DOC-{2000 + i}",
        "name": name,
        "primary_hospital_id": primary_hospital["hospital_id"],
        "city": primary_hospital["city"]
    })

# Generate 2,000 claimants
CLAIMANTS = []
for i in range(2000):
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    phone = f"+91-9{random.randint(100000000, 999999999)}"
    # some share bank accounts (fraud ring simulation)
    if i % 30 == 0:
        bank_hash = "bank_ring_shared_hash_9999"
    elif i % 45 == 0:
        bank_hash = "bank_ring_shared_hash_8888"
    else:
        bank_hash = hashlib.sha256(f"acc_{i}_{name}".encode()).hexdigest()[:16]

    CLAIMANTS.append({
        "claimant_id": f"CLMNT-{5000 + i}",
        "name": name,
        "phone": phone,
        "bank_account_hash": bank_hash
    })

DIAGNOSIS_CATALOG = {
    "I20.9": {"name": "Angina Pectoris / Ischemic Heart Disease", "median_cost": 120000, "stay": (3, 6)},
    "K35.8": {"name": "Acute Appendicitis (Laparoscopic)", "median_cost": 45000, "stay": (2, 4)},
    "J18.9": {"name": "Pneumonia, Unspecified", "median_cost": 35000, "stay": (3, 7)},
    "S82.8": {"name": "Fracture Lower Leg (ORIF Surgery)", "median_cost": 65000, "stay": (3, 5)},
    "E11.9": {"name": "Type 2 Diabetes with Acute Complications", "median_cost": 28000, "stay": (2, 5)},
    "N39.0": {"name": "Urinary Tract Infection, Acute", "median_cost": 22000, "stay": (1, 3)},
    "A09":   {"name": "Infectious Gastroenteritis & Colitis", "median_cost": 18000, "stay": (1, 3)},
    "K80.2": {"name": "Calculus of Gallbladder (Cholecystectomy)", "median_cost": 55000, "stay": (2, 4)},
}

FRAUD_TYPES = [
    "inflated_line_items",
    "arithmetic_mismatch",
    "policy_cap_breach",
    "duplicate_bill",
    "cross_insurer_duplicate",
    "impossible_travel",
    "shared_bank_account_ring",
    "forged_document"
]


def generate_claims(count: int = 3000):
    claims = []
    line_items_all = []
    doctor_events_all = []

    base_date = datetime(2026, 1, 1)

    print(f"Generating {count} synthetic claims...")
    for idx in range(count):
        claim_id = f"CLM-{100000 + idx}"
        policy_id = f"POL-{random.choice(['AROGYA', 'CARE', 'OPTIMA'])}-{random.randint(10000, 99999)}"
        insurer = random.choice(INSURERS)
        claimant = random.choice(CLAIMANTS)
        hospital = random.choice(HOSPITALS)
        doctor = random.choice(DOCTORS)
        
        diag_code = random.choice(list(DIAGNOSIS_CATALOG.keys()))
        diag_meta = DIAGNOSIS_CATALOG[diag_code]
        stay_days = random.randint(*diag_meta["stay"])
        
        admission_day_offset = random.randint(0, 240)
        admission_ts = base_date + timedelta(days=admission_day_offset, hours=random.randint(8, 14))
        discharge_ts = admission_ts + timedelta(days=stay_days, hours=random.randint(2, 6))

        # Check if fraud (~12% probability)
        is_fraud = 1 if random.random() < 0.12 else 0
        fraud_type = random.choice(FRAUD_TYPES) if is_fraud else "clean"

        # Pricing baseline
        base_cost = diag_meta["median_cost"] * random.uniform(0.85, 1.15)
        room_rent_cap = 5000.0  # standard policy cap per day

        if is_fraud and fraud_type == "inflated_line_items":
            base_cost *= random.uniform(2.2, 3.8)
        elif is_fraud and fraud_type == "policy_cap_breach":
            room_rent = 12000.0
        else:
            room_rent = random.choice([3000.0, 4000.0, 4800.0])

        if is_fraud and fraud_type == "shared_bank_account_ring":
            claimant["bank_account_hash"] = "bank_ring_shared_hash_9999"

        # Generate line items
        line_items = []
        # Room Rent
        room_total = room_rent * stay_days
        line_items.append({
            "claim_id": claim_id,
            "item_id": f"ITEM-{idx}-1",
            "description": f"Hospital Room Rent ({stay_days} days)",
            "qty": stay_days,
            "unit_price": room_rent,
            "amount": room_total
        })

        # Doctor Consultation
        consult_rate = random.choice([1500, 2000, 2500])
        consult_total = consult_rate * stay_days
        line_items.append({
            "claim_id": claim_id,
            "item_id": f"ITEM-{idx}-2",
            "description": f"Doctor Visiting Fees ({stay_days} visits)",
            "qty": stay_days,
            "unit_price": consult_rate,
            "amount": consult_total
        })

        # Procedure / Surgery / Treatment
        proc_cost = max(5000.0, base_cost - room_total - consult_total)
        line_items.append({
            "claim_id": claim_id,
            "item_id": f"ITEM-{idx}-3",
            "description": f"Treatment & OT Charges: {diag_meta['name']}",
            "qty": 1,
            "unit_price": round(proc_cost, 2),
            "amount": round(proc_cost, 2)
        })

        # Pharmacy
        pharmacy_cost = round(random.uniform(2000, 8000), 2)
        line_items.append({
            "claim_id": claim_id,
            "item_id": f"ITEM-{idx}-4",
            "description": "Prescription Medicines & Consumables",
            "qty": 1,
            "unit_price": pharmacy_cost,
            "amount": pharmacy_cost
        })

        subtotal = sum(item["amount"] for item in line_items)
        tax = round(subtotal * 0.05, 2)
        total_claimed = round(subtotal + tax, 2)

        if is_fraud and fraud_type == "arithmetic_mismatch":
            total_claimed += round(random.uniform(15000, 35000), 2)

        line_items_all.extend(line_items)

        # Engineered features for ML
        amount_vs_median = round(total_claimed / diag_meta["median_cost"], 3)
        prior_claims = random.choices([0, 1, 2, 3, 5], weights=[0.75, 0.15, 0.06, 0.03, 0.01])[0]
        if is_fraud and fraud_type in ["duplicate_bill", "cross_insurer_duplicate"]:
            prior_claims += 2

        provider_claims_day = round(random.uniform(1.2, 4.5), 2)
        doctor_cities_24h = 1
        if is_fraud and fraud_type == "impossible_travel":
            doctor_cities_24h = random.choice([2, 3])

        shared_bank_count = 1
        if claimant["bank_account_hash"] == "bank_ring_shared_hash_9999":
            shared_bank_count = 14
        elif claimant["bank_account_hash"] == "bank_ring_shared_hash_8888":
            shared_bank_count = 8

        days_policy_to_claim = random.randint(15, 700)
        if is_fraud and fraud_type == "policy_cap_breach":
            days_policy_to_claim = random.randint(15, 45)  # right after waiting period

        room_rent_vs_cap = round(room_rent / room_rent_cap, 3)

        claim_record = {
            "claim_id": claim_id,
            "policy_id": policy_id,
            "insurer_id": insurer["id"],
            "claimant_id": claimant["claimant_id"],
            "claimant_name": claimant["name"],
            "claimant_phone": claimant["phone"],
            "bank_account_hash": claimant["bank_account_hash"],
            "hospital_id": hospital["hospital_id"],
            "hospital_name": hospital["name"],
            "city": hospital["city"],
            "lat": hospital["lat"],
            "lng": hospital["lng"],
            "doctor_id": doctor["doctor_id"],
            "admission_ts": admission_ts.isoformat(),
            "discharge_ts": discharge_ts.isoformat(),
            "diagnosis_code": diag_code,
            "subtotal": round(subtotal, 2),
            "tax": tax,
            "total_claimed": total_claimed,
            "claim_amount": total_claimed,
            "amount_vs_diagnosis_median_ratio": amount_vs_median,
            "length_of_stay": stay_days,
            "claimant_prior_claims_90d": prior_claims,
            "provider_claims_per_day": provider_claims_day,
            "doctor_distinct_cities_24h": doctor_cities_24h,
            "shared_bank_account_count": shared_bank_count,
            "days_policy_start_to_claim": days_policy_to_claim,
            "line_item_count": len(line_items),
            "room_rent_vs_cap_ratio": room_rent_vs_cap,
            "is_fraud": is_fraud,
            "fraud_type": fraud_type,
            "created_at": (discharge_ts + timedelta(days=random.randint(1, 5))).isoformat()
        }
        claims.append(claim_record)

        # Generate doctor events
        event_ts = admission_ts + timedelta(hours=2)
        doctor_events_all.append({
            "event_id": f"EVT-{idx}-1",
            "doctor_id": doctor["doctor_id"],
            "ts": event_ts.isoformat(),
            "hospital_id": hospital["hospital_id"],
            "hospital_name": hospital["name"],
            "city": hospital["city"],
            "lat": hospital["lat"],
            "lng": hospital["lng"],
            "claim_id": claim_id
        })

        if is_fraud and fraud_type == "impossible_travel":
            # Add an impossible event 90 mins later in a distant city (e.g. Mumbai vs Delhi ~ 1,150 km)
            distant_city = next(c for c in CITIES if c["city"] != hospital["city"])
            impossible_ts = event_ts + timedelta(minutes=90)
            doctor_events_all.append({
                "event_id": f"EVT-IMP-{idx}",
                "doctor_id": doctor["doctor_id"],
                "ts": impossible_ts.isoformat(),
                "hospital_id": f"HOSP-EXT-{idx}",
                "hospital_name": f"Distant Care {distant_city['city']}",
                "city": distant_city["city"],
                "lat": distant_city["lat"],
                "lng": distant_city["lng"],
                "claim_id": f"CLM-EXT-{idx}"
            })

    # Save to JSONL and CSV
    claims_df = pd.DataFrame(claims)
    line_items_df = pd.DataFrame(line_items_all)
    doctor_events_df = pd.DataFrame(doctor_events_all)

    claims_df.to_csv(DATA_DIR / "claims.csv", index=False)
    claims_df.to_json(DATA_DIR / "claims.jsonl", orient="records", lines=True)
    line_items_df.to_json(DATA_DIR / "line_items.jsonl", orient="records", lines=True)
    doctor_events_df.to_json(DATA_DIR / "doctor_events.jsonl", orient="records", lines=True)

    print(f"✅ Generated {len(claims)} claims:")
    fraud_counts = claims_df["fraud_type"].value_counts().to_dict()
    for ft, cnt in fraud_counts.items():
        print(f"   - {ft}: {cnt} ({cnt/len(claims):.1%})")

    return claims_df, line_items_df, doctor_events_df


if __name__ == "__main__":
    generate_claims(3000)
