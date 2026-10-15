"""
Builds the Fraud Pattern Knowledge Base (Corpus 2) for Feature A4:
Retrieval-Augmented Fraud Pattern Discovery (finshield-patterns).

Reads labeled claims in BigQuery / data/claims.jsonl and emits 48 distinctive
fraud pattern cards (target: 40-60 cards, not one per claim).
Each card contains:
  - pattern_id
  - fraud_type
  - title
  - narrative (3-4 sentences describing how the scheme works)
  - signature (observable features: amount ratios, timing, document traits, entity links)
  - typical_severity
  - example_claim_ids (representative claims from dataset)

Saves to /data/patterns/fraud_patterns.json.
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

DATA_DIR = Path(__file__).resolve().parent
CLAIMS_PATH = DATA_DIR / "claims.jsonl"
PATTERNS_DIR = DATA_DIR / "patterns"
PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = PATTERNS_DIR / "fraud_patterns.json"

PATTERN_DEFINITIONS = [
    # -------------------------------------------------------------------------
    # 1. SHARED BANK ACCOUNT RING (6 variants)
    # -------------------------------------------------------------------------
    {
        "variant": 1,
        "fraud_type": "shared_bank_account_ring",
        "title": "Multi-Claimant Mule Account Ring across Distant Cities",
        "narrative": "An organized financial syndicate routes claim reimbursement payouts from multiple unrelated claimants across disparate cities into a single centralized bank account hash. The claimants report admissions in different private facilities but share an identical settlement account. Once funds are disbursed, the ring rapidly withdraws or funnels funds through peer-to-peer transfers.",
        "signature": "shared_bank_account_count >= 10, multiple claimant cities within 90d, distinct claimant surnames, normal billed hospital items",
        "typical_severity": "critical"
    },
    {
        "variant": 2,
        "fraud_type": "shared_bank_account_ring",
        "title": "Immediate Family Burst / Clustered Account Sharing",
        "narrative": "Multiple individuals with the same surname or residential PIN submit claims within a tight 30-day window directing payouts to one primary family member's account. While family sharing can occasionally occur, coordinated inpatient admissions at different facilities indicate fabricated episodes designed to maximize annual floater limits. The medical narratives frequently show identical diagnosis codes.",
        "signature": "shared_bank_account_count between 3 and 6, claim submission gap < 30 days, identical diagnosis code, shared bank account hash",
        "typical_severity": "high"
    },
    {
        "variant": 3,
        "fraud_type": "shared_bank_account_ring",
        "title": "Provider / Clinic Payroll Account Recycling Scheme",
        "narrative": "A corrupt hospital administrative desk routes patient reimbursement payouts to bank accounts belonging to clinic staff or administrative promoters. Claimants are reimbursed a small cash cut while the clinic retains the majority insurance payout. Cross-referencing reveals the account has appeared as both employee payout destination and claimant settlement target.",
        "signature": "shared_bank_account_count >= 5, claims concentrated at single provider_id, claimant phones with sequential numbers",
        "typical_severity": "critical"
    },
    {
        "variant": 4,
        "fraud_type": "shared_bank_account_ring",
        "title": "Cross-District Syndicate Operating in Tier-2/3 Towns",
        "narrative": "A syndicate recruits rural policyholders in Tier-2/3 districts, paying them nominal sums to sign blank reimbursement claim packets. Inpatient treatments for acute gastroenteritis or dengue are billed with genuine-looking invoices from local nursing homes. All claims funnel proceeds into an agent-controlled intermediary account.",
        "signature": "shared_bank_account_count between 7 and 15, claimant addresses in non-metro PIN codes, length_of_stay <= 3 days",
        "typical_severity": "critical"
    },
    {
        "variant": 5,
        "fraud_type": "shared_bank_account_ring",
        "title": "Rapid Account Recycling / Dormant Identity Wakeup",
        "narrative": "A bank account that sat dormant for over a year suddenly receives multiple substantial insurance reimbursements within a 14-day window. The claimants involved had continuous coverage but zero prior claims history before the burst. The swift cadence suggests acquired mule accounts being exhausted before freeze actions.",
        "signature": "claimant_prior_claims_90d == 0, shared_bank_account_count >= 4 within 14 days, sudden high claim amount",
        "typical_severity": "high"
    },
    {
        "variant": 6,
        "fraud_type": "shared_bank_account_ring",
        "title": "Micro-Claim High-Velocity Payout Churn",
        "narrative": "The syndicate intentionally keeps individual claim amounts below ₹30,000 to fly under automated human audit thresholds (Straight-Through Processing). By submitting dozens of low-value claims to the same account across several weeks, the cumulative loss exceeds several lakhs. Every claim features routine antibiotic or saline therapy.",
        "signature": "shared_bank_account_count >= 8, total_claimed < 30000, high submission velocity, identical medical management bills",
        "typical_severity": "medium"
    },

    # -------------------------------------------------------------------------
    # 2. IMPOSSIBLE TRAVEL (6 variants)
    # -------------------------------------------------------------------------
    {
        "variant": 1,
        "fraud_type": "impossible_travel",
        "title": "Interstate High-Speed Transit Impossibility (Delhi to Mumbai)",
        "narrative": "A treating physician or claimant is documented performing or receiving clinical procedures in two distant metropolitan centers separated by over 1,000 kilometers within a few hours. Minimum realistic transit time including commercial flight boarding and airport transit exceeds 4 hours. The impossible velocity proves that at least one documented procedure was fabricated in absentia.",
        "signature": "haversine distance > 1000 km, time gap < 3 hours, required_h > 4.0, available_h < 2.5",
        "typical_severity": "critical"
    },
    {
        "variant": 2,
        "fraud_type": "impossible_travel",
        "title": "Cross-Metro Procedure Teleportation (Bengaluru to Kolkata)",
        "narrative": "Surgeon or patient billed for concurrent surgical procedures in Southern and Eastern hubs within an unrealistic 90-minute elapsed window. Flight schedules between the cities require at least 2.5 hours of block flight time alone plus airport transit. Such overlap confirms ghost doctor billing where junior assistants or administrative clerks reuse a senior specialist's registration.",
        "signature": "haversine distance > 1500 km, time gap <= 2 hours, transit speed > 800 km/h, same doctor_id",
        "typical_severity": "critical"
    },
    {
        "variant": 3,
        "fraud_type": "impossible_travel",
        "title": "Intrastate Rapid Clinic Hopping (Speed > 180 km/h Road Travel)",
        "narrative": "A physician bills consultations and bedside rounds across multiple district nursing homes separated by 200–300 km within 45 to 60 minutes. State highway travel under realistic Indian road conditions cannot sustain speeds above 80 km/h. The physical timeline demonstrates phantom rounds recorded by hospital management.",
        "signature": "haversine distance between 150 km and 300 km, road travel duration < 1.0 hour, implied road speed > 180 km/h",
        "typical_severity": "high"
    },
    {
        "variant": 4,
        "fraud_type": "impossible_travel",
        "title": "Simultaneous Multi-Hospital Emergency Procedures",
        "narrative": "The treating doctor's state medical council registration is cited on concurrent active surgeries in two different accredited hospitals in the same city at the exact same minute. Even with short physical distance, an operating surgeon cannot simultaneously perform open or laparoscopic procedures in separate operating theaters.",
        "signature": "consecutive event time gap <= 15 minutes, distinct hospital_ids, active surgical line items, same doctor_id",
        "typical_severity": "critical"
    },
    {
        "variant": 5,
        "fraud_type": "impossible_travel",
        "title": "Patient Dual-Hospital Admission Overlap",
        "narrative": "Hospitalization records indicate the patient was simultaneously admitted as an inpatient in two distinct facilities across different cities. Admission and discharge logs confirm ongoing bed occupancy in both hospitals on the same calendar days. This pattern reflects dual-claiming where old hospital records are re-dated while the patient undergoes routine treatment elsewhere.",
        "signature": "overlapping admission_ts and discharge_ts for same claimant_id, different hospital_ids in different cities",
        "typical_severity": "critical"
    },
    {
        "variant": 6,
        "fraud_type": "impossible_travel",
        "title": "Midnight Ghost Rounds Across Distant Wards",
        "narrative": "A specialist physician records rounds between 23:00 and 03:00 at facilities separated by 100+ km without overnight rail or air connection. The timing represents retrospective computerized batch logging by hospital administrative staff rather than actual clinical encounters.",
        "signature": "haversine distance > 100 km, time gap < 1.5 hours, midnight timestamp window (23:00 - 04:00)",
        "typical_severity": "high"
    },

    # -------------------------------------------------------------------------
    # 3. CROSS-INSURER DUPLICATE (5 variants)
    # -------------------------------------------------------------------------
    {
        "variant": 1,
        "fraud_type": "cross_insurer_duplicate",
        "title": "Parallel Exact Reimbursement Submission to Competitor Insurers",
        "narrative": "A claimant submits the exact same hospital invoice, dates of admission, and total claim amount to two different general insurers (e.g. Star Health and HDFC ERGO). By exploiting the lack of real-time inter-insurer data sharing, the fraudster successfully secures duplicate 100% indemnification for a single medical event.",
        "signature": "identical hospital_name, identical admission_ts/discharge_ts, identical total_claimed (+- 1%), distinct insurer_id",
        "typical_severity": "critical"
    },
    {
        "variant": 2,
        "fraud_type": "cross_insurer_duplicate",
        "title": "Split-Claim Double Dipping (Cashless + Reimbursement Scheme)",
        "narrative": "The hospital settles the primary bill via cashless TPA with Insurer A, then hands the patient a 'final discharge bill' which the patient submits for full reimbursement to Insurer B without disclosing the prior settlement. This results in double recovery on a single inpatient stay.",
        "signature": "matching line_items, identical hospital_id and admission dates, filed across both cashless and reimbursement channels",
        "typical_severity": "critical"
    },
    {
        "variant": 3,
        "fraud_type": "cross_insurer_duplicate",
        "title": "Re-Dated Cross-Insurer Resubmission after Prior Denial",
        "narrative": "Following a fraud or pre-existing disease repudiation by Insurer A, the claimant adjusts the admission dates by 1–2 months and submits the claim to Insurer B under a newer policy. Warehouse cross-referencing exposes identical diagnosis codes, procedure charges, and physician notes.",
        "signature": "identical diagnosis_code, matching doctor_id and total_claimed, dates shifted by 30 to 90 days, distinct insurer_id",
        "typical_severity": "high"
    },
    {
        "variant": 4,
        "fraud_type": "cross_insurer_duplicate",
        "title": "Unbundled Package Double-Claim Across Policies",
        "narrative": "The claimant breaks an all-inclusive surgical package into room rent and surgeon charges, submitting room rent to their corporate group cover and surgeon fees to their individual retail health policy, while both insurers are billed for the full subtotal.",
        "signature": "matching claimant_id, overlapping hospitalization dates, complementary unbundled line item subsets",
        "typical_severity": "high"
    },
    {
        "variant": 5,
        "fraud_type": "cross_insurer_duplicate",
        "title": "Inter-TPA Duplicate Bill Re-Use",
        "narrative": "A crooked broker re-uses a legitimate discharged patient's billing package, changing only the policyholder name and policy number, and files it with a second TPA. The underlying medical details, pharmacy lot numbers, and doctor signatures are identical to an existing settled claim.",
        "signature": "identical bill line items, identical doctor_id and hospital_id, distinct claimant_id, different insurer_id",
        "typical_severity": "critical"
    },

    # -------------------------------------------------------------------------
    # 4. POLICY CAP BREACH (6 variants)
    # -------------------------------------------------------------------------
    {
        "variant": 1,
        "fraud_type": "policy_cap_breach",
        "title": "Deluxe Suite Room Rent Camouflage Over IRDAI 2% Cap",
        "narrative": "The hospital bills an executive luxury suite at ₹12,000–₹16,000 per day under a standard Arogya Sanjeevani policy that explicitly caps room rent at 2% of Sum Insured (max ₹5,000/day). The bill often labels the room as 'Special Care Unit' to evade standard room rent sub-limit filters.",
        "signature": "room_rent_vs_cap_ratio >= 2.0, billed room rent > 5000/day on Arogya Sanjeevani, policy Clause 3.1 breach",
        "typical_severity": "high"
    },
    {
        "variant": 2,
        "fraud_type": "policy_cap_breach",
        "title": "ICU Ceiling Inflation Beyond Statutory Limits",
        "narrative": "Intensive care charges are billed at ₹20,000–₹25,000 per day, vastly exceeding the statutory ₹10,000/day or 5% Sum Insured ceiling specified in IRDAI standard guidelines. The hospital packs nursing, monitor, and oxygen charges as separate line items on top of the already capped ICU rate.",
        "signature": "icu_rent_vs_cap_ratio >= 1.5, daily ICU billing > 10000, unbundled ICU equipment charges, policy Clause 3.2 breach",
        "typical_severity": "high"
    },
    {
        "variant": 3,
        "fraud_type": "policy_cap_breach",
        "title": "30-Day Initial Waiting Period Evasion via Fabricated Trauma",
        "narrative": "A policyholder hospitalized for acute medical management within 20 days of policy inception attempts to bypass the mandatory 30-day waiting period (Clause 4.1) by falsely documenting the illness as an acute accidental injury.",
        "signature": "days_policy_start_to_claim < 30, non-trauma diagnosis code billed with trauma narrative, policy Clause 4.1 breach",
        "typical_severity": "high"
    },
    {
        "variant": 4,
        "fraud_type": "policy_cap_breach",
        "title": "24-Month Specific Illness Waiting Period Evasion (Cholecystectomy)",
        "narrative": "A claimant undergoes elective cholecystectomy or hernia repair at month 14 of the policy, well within the 24-month specific ailment waiting period (Clause 4.2). The hospital clinical summary alters the diagnosis to 'Acute Abdomen / Sepsis Emergency' to circumvent the exclusion.",
        "signature": "days_policy_start_to_claim between 30 and 720, diagnosis_code in [K80.2, K40.9, N20.1], policy Clause 4.2 breach",
        "typical_severity": "high"
    },
    {
        "variant": 5,
        "fraud_type": "policy_cap_breach",
        "title": "Robotic / Advanced Technology Cap Evasion",
        "narrative": "Surgical charges for robotic or laser-assisted modern treatments are billed at ₹3,50,000, breaching the policy sub-limit of ₹1,50,000. The facility disguises the robotic console fees under miscellaneous OT consumable items.",
        "signature": "modern_treatment_amount > 150000, high OT consumable ratio, policy Clause 2.3 breach",
        "typical_severity": "medium"
    },
    {
        "variant": 6,
        "fraud_type": "policy_cap_breach",
        "title": "Cataract Surgical Expense Sub-Limit Evasion",
        "narrative": "A standard day-care cataract procedure with monofocal or toric IOL is billed at ₹75,000 per eye, ignoring the strict ₹40,000 per eye sub-limit set out under Clause 6.1 of the standard health product.",
        "signature": "cataract surgery cost > 40000 per eye, day care procedure, policy Clause 6.1 breach",
        "typical_severity": "medium"
    },

    # -------------------------------------------------------------------------
    # 5. ARITHMETIC MISMATCH (5 variants)
    # -------------------------------------------------------------------------
    {
        "variant": 1,
        "fraud_type": "arithmetic_mismatch",
        "title": "Fabricated Gross Total Payable Over-Billing",
        "narrative": "The printed Grand Total Payable on the invoice exceeds the mathematical sum of the individual line items plus GST by tens of thousands of rupees. Human reviewers scanning only the summary block approve the inflated number, while an automated paise-accurate sum reveals an intentional upward discrepancy.",
        "signature": "printed_total > (line_items_sum + tax), discrepancy > 5000 rupees, clean visual document appearance",
        "typical_severity": "critical"
    },
    {
        "variant": 2,
        "fraud_type": "arithmetic_mismatch",
        "title": "Quantity / Unit Rate Multiplication Distortion",
        "narrative": "Individual line item totals do not equal quantity multiplied by unit rate (e.g. 3 days room rent at ₹4,000 billed as ₹18,000 instead of ₹12,000). The line item text obscures the calculation so the subtotal carries compounded inflated padding.",
        "signature": "any(item.amount != item.qty * item.unit_price), total mismatch propagates into grand total",
        "typical_severity": "high"
    },
    {
        "variant": 3,
        "fraud_type": "arithmetic_mismatch",
        "title": "Tax Base Inflation / Phantom Surcharge Injection",
        "narrative": "GST (5%) is calculated against an arbitrary inflated base rather than the printed subtotal, or an undocumented hospital surcharge is slipped into the tax line to artificially expand the claim reimbursement value.",
        "signature": "abs(tax - subtotal * 0.05) > 100 rupees, printed total reflects artificial surcharge",
        "typical_severity": "medium"
    },
    {
        "variant": 4,
        "fraud_type": "arithmetic_mismatch",
        "title": "Pharmacy Annexure Subtotal Reconciliation Failure",
        "narrative": "The gross invoice lists an in-patient pharmacy total of ₹45,000, but summing the attached detailed pharmacy dispensary receipts yields only ₹18,500. The mismatch represents unspent or fictional medication charges billed directly to the insurer.",
        "signature": "pharmacy_line_item > pharmacy_detail_receipt_sum, discrepancy > 10000 rupees",
        "typical_severity": "high"
    },
    {
        "variant": 5,
        "fraud_type": "arithmetic_mismatch",
        "title": "Negative Advance Payment Subtraction Tampering",
        "narrative": "The patient made an advance cash deposit during admission, but the hospital invoice omits subtracting the deposit from the final balance payable, attempting to collect the full treatment cost from the insurer while retaining the cash.",
        "signature": "uncredited advance deposit on bill, net payable equals gross total despite advance receipt",
        "typical_severity": "medium"
    },

    # -------------------------------------------------------------------------
    # 6. FORGED DOCUMENT (6 variants)
    # -------------------------------------------------------------------------
    {
        "variant": 1,
        "fraud_type": "forged_document",
        "title": "Typography Tampering (Courier-Bold Font Insertion on Total Row)",
        "narrative": "The total payable row on the medical bill is edited post-generation. While the entire hospital invoice is composed in clean Helvetica or Arial, the total row displays Courier-Bold or Liberation Mono font with mismatched vertical point size, revealing digital raster or vector substitution.",
        "signature": "font mismatch on total row (Courier-Bold vs Helvetica body), font size delta > 2pt, altered total text run",
        "typical_severity": "critical"
    },
    {
        "variant": 2,
        "fraud_type": "forged_document",
        "title": "Digital Image Editor Producer Footprint (Photoshop / Canva / GIMP)",
        "narrative": "The PDF metadata headers reveal that an alleged computerized hospital billing export was generated or modified using consumer image editors such as Adobe Photoshop, Canva, or CorelDraw, rather than a Hospital Information System (HIS) or ERP export engine.",
        "signature": "producer in ['Adobe Photoshop', 'Canva', 'GIMP', 'CorelDraw', 'ILovePDF'], suspicious metadata stream",
        "typical_severity": "critical"
    },
    {
        "variant": 3,
        "fraud_type": "forged_document",
        "title": "Post-Issuance Metadata ModDate / CreateDate Discrepancy",
        "narrative": "The PDF creation date corresponds to the genuine date of discharge, but the modification timestamp (ModDate) shows modifications occurring 30 to 60 days later just prior to insurance submission. The delta points to forensic tampering with amounts or dates.",
        "signature": "abs(ModDate - CreateDate) > 7 days, suspicious editing software in PDF trailer",
        "typical_severity": "high"
    },
    {
        "variant": 4,
        "fraud_type": "forged_document",
        "title": "Cloned Digital Stamp and Signature Overlay",
        "narrative": "The official hospital seal and doctor's signature are graphic PNG layers pasted across multiple documents with exact identical pixel coordinates and transparent alpha boundaries, proving synthetic document assembly rather than authentic clinical execution.",
        "signature": "identical signature image hash across multiple documents, digital overlay layers in PDF stream",
        "typical_severity": "critical"
    },
    {
        "variant": 5,
        "fraud_type": "forged_document",
        "title": "Text Vector Layer Overlaid on Erased Raster Background",
        "narrative": "A scanned bill has had its original numeric charges erased using white rectangular annotations, over which crisp new vector text numbers have been rendered to inflate the claim value.",
        "signature": "vector text runs positioned directly over white fill rectangles, background color delta <= 0.08",
        "typical_severity": "critical"
    },
    {
        "variant": 6,
        "fraud_type": "forged_document",
        "title": "Missing Embedded Font Stream & Synthetic PDF Generator",
        "narrative": "The document structure lacks embedded standard hospital font tables, exhibiting synthetic PDF generator artifacts commonly generated by online fake invoice creation websites (e.g. Invoice-Generator.com, PDFKit without font embedding).",
        "signature": "producer matches online invoice generator, missing font descriptors, generic invoice template layout",
        "typical_severity": "high"
    },

    # -------------------------------------------------------------------------
    # 7. INFLATED LINE ITEMS (7 variants)
    # -------------------------------------------------------------------------
    {
        "variant": 1,
        "fraud_type": "inflated_line_items",
        "title": "Severe Outlier Claim Amount vs. District Diagnosis Median",
        "narrative": "The total billed claim exceeds 2.5 times the statistical median billed cost for the identical ICD-10 diagnosis code across all accredited hospitals within the same metropolitan district. Investigation reveals padded consumable lines and bloated doctor visit charges.",
        "signature": "amount_vs_diagnosis_median_ratio >= 2.5, diagnosis_code in [A09, J18.9, K35.8], elevated total_claimed",
        "typical_severity": "high"
    },
    {
        "variant": 2,
        "fraud_type": "inflated_line_items",
        "title": "Excessive Diagnostic Workup for Minor Ailment",
        "narrative": "A patient admitted for routine viral gastroenteritis is billed for comprehensive 2D-Echo, Brain MRI, and intensive cardiology panels exceeding ₹40,000. The clinical justification for these high-cost tertiary investigations is entirely absent from the physician notes.",
        "signature": "diagnosis_code in ['A09', 'R50.9'], high lab/radiology charges ratio (> 40% of subtotal), amount_vs_diagnosis_median_ratio > 1.8",
        "typical_severity": "medium"
    },
    {
        "variant": 3,
        "fraud_type": "inflated_line_items",
        "title": "Unjustified Prolonged Length of Stay (Bed Padding Scheme)",
        "narrative": "The patient is kept admitted for 7–10 days for an acute condition that clinical guidelines universally manage within 48–72 hours. Daily bed charges and physician visit fees compound daily to inflate the total reimbursement volume.",
        "signature": "length_of_stay >= 7 days for minor diagnosis, repetitive daily visit charges, amount_vs_diagnosis_median_ratio > 2.0",
        "typical_severity": "medium"
    },
    {
        "variant": 4,
        "fraud_type": "inflated_line_items",
        "title": "Pharmacy Consumable Markup Exceeding Drug Price Control (NPPA)",
        "narrative": "Surgical sutures, IV sets, and high-volume antibiotics are billed at 3x–4x the maximum retail price (MRP) mandated by the National Pharmaceutical Pricing Authority. The hospital inflates unit costs knowing TPAs often approve pharmacy lines automatically.",
        "signature": "unit_price for standard antibiotics or consumables > 3x retail benchmark, pharmacy ratio > 35%",
        "typical_severity": "high"
    },
    {
        "variant": 5,
        "fraud_type": "inflated_line_items",
        "title": "Unbundled Package Surgical Surcharges",
        "narrative": "While a laparoscopic appendectomy or cholecystectomy is agreed under a packaged rate of ₹45,000, the bill includes separate line items for surgeon fees, anesthesia, theater consumables, and monitor charges, inflating the gross amount to ₹85,000.",
        "signature": "surgical diagnosis with unbundled separate theater, anesthesia, and surgeon charges exceeding package standard",
        "typical_severity": "high"
    },
    {
        "variant": 6,
        "fraud_type": "inflated_line_items",
        "title": "Excessive Consultation Rounds Billing (Multiple Visits Daily)",
        "narrative": "Senior consultants are billed as conducting 4 to 5 separate bedside visits every 24 hours at ₹2,000 per visit, resulting in ₹10,000 daily purely in consultation fees for a stable, non-critical ward patient.",
        "signature": "physician visit count >= 4 per day for ward stay, consultant visit charges > 30% of total bill",
        "typical_severity": "medium"
    },
    {
        "variant": 7,
        "fraud_type": "inflated_line_items",
        "title": "Fictional Blood Component & Transfusion Billing",
        "narrative": "The hospital bill includes multiple units of Fresh Frozen Plasma or Packed Red Blood Cells with processing charges for a minor elective surgery without corresponding cross-match records or blood bank issue numbers.",
        "signature": "blood product line items without blood bank certificate or transfusion notes, high consumable total",
        "typical_severity": "high"
    },

    # -------------------------------------------------------------------------
    # 8. DUPLICATE BILL (7 variants)
    # -------------------------------------------------------------------------
    {
        "variant": 1,
        "fraud_type": "duplicate_bill",
        "title": "Identical Invoice Number & Billed Line-Items Re-Submission",
        "narrative": "The identical invoice number with matching line items and total amount is submitted a second time for a different claimant or under a different policy number within the same network database.",
        "signature": "exact invoice number match in warehouse, identical subtotal and line items, different claim_id",
        "typical_severity": "critical"
    },
    {
        "variant": 2,
        "fraud_type": "duplicate_bill",
        "title": "Re-Dated Prior Settled Claim from Same Hospital",
        "narrative": "A claim that was settled 6 months ago is reprinted with updated admission and discharge dates. The line items, rates, and physician signatures match the settled claim verbatim, representing recycled clinical documentation.",
        "signature": "identical line item descriptions and unit prices, matching hospital_id and doctor_id, dates shifted by months",
        "typical_severity": "critical"
    },
    {
        "variant": 3,
        "fraud_type": "duplicate_bill",
        "title": "Family Floater Identity Substitution on Settled Bill",
        "narrative": "A settled bill for a father's hospitalization is re-submitted under the mother's name on a family floater policy to exhaust the remaining family annual coverage before policy expiry.",
        "signature": "identical total_claimed, hospital_id, and diagnosis, claimant surname matches but distinct claimant_id",
        "typical_severity": "high"
    },
    {
        "variant": 4,
        "fraud_type": "duplicate_bill",
        "title": "Dual-Claimant Carbon Copy Inpatient Bill",
        "narrative": "Two unrelated patients treated at the same nursing home present bills that are exact carbon copies down to the exact rupee and item descriptions, indicating template fabrication by the hospital billing desk.",
        "signature": "identical item descriptions and line amounts across distinct claimants at same hospital_id",
        "typical_severity": "critical"
    },
    {
        "variant": 5,
        "fraud_type": "duplicate_bill",
        "title": "Partial Bill Recycling / Re-Submitted Pharmacy Annexures",
        "narrative": "The claimant re-attaches pharmacy bills and lab reports from an earlier settled claim to a new, smaller inpatient claim to pad the admissible total.",
        "signature": "matching pharmacy invoice numbers or lab report IDs across multiple distinct claims",
        "typical_severity": "high"
    },
    {
        "variant": 6,
        "fraud_type": "duplicate_bill",
        "title": "Same-Day Duplicate Submission Glitch or Exploitation",
        "narrative": "Two identical claim files are submitted within minutes of each other across web portal and mobile app endpoints, attempting to trigger concurrent straight-through automated approval before deduplication indexers lock.",
        "signature": "submission timestamp delta < 10 minutes, identical claim payload and PDF sha256 hash",
        "typical_severity": "high"
    },
    {
        "variant": 7,
        "fraud_type": "duplicate_bill",
        "title": "Cross-Doctor Duplicate Bill Split Scheme",
        "narrative": "The same hospital stay is billed by two different consultant physicians claiming independent primary inpatient management, resulting in double professional fees and overlapping bed days.",
        "signature": "matching admission_ts, same hospital_id, distinct doctor_ids billing primary physician visits",
        "typical_severity": "medium"
    }
]


def load_claims_by_fraud_type() -> Dict[str, List[Dict[str, Any]]]:
    """Loads labeled claims from claims.jsonl grouped by fraud_type."""
    grouped = defaultdict(list)
    if not CLAIMS_PATH.exists():
        print(f"Warning: {CLAIMS_PATH} not found.")
        return grouped

    with open(CLAIMS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                claim = json.loads(line)
                ft = claim.get("fraud_type", "clean")
                grouped[ft].append(claim)
            except Exception:
                continue
    return grouped


def build_pattern_cards() -> List[Dict[str, Any]]:
    """Builds 48 structured fraud pattern cards with representative example claim IDs."""
    claims_by_type = load_claims_by_fraud_type()
    cards = []

    for idx, pdef in enumerate(PATTERN_DEFINITIONS, 1):
        ft = pdef["fraud_type"]
        sample_claims = claims_by_type.get(ft, [])

        # Pick 2-3 representative claim IDs for this variant
        # Stride through sample claims so each variant gets distinct example claims
        v = pdef["variant"]
        stride_start = (v - 1) * 3
        selected_claims = sample_claims[stride_start : stride_start + 3]
        example_ids = [c["claim_id"] for c in selected_claims] if selected_claims else [f"CLM-SYNTH-{ft[:4].upper()}-{v}"]

        pattern_id = f"PAT-{ft.upper()[:10]}-{v:02d}"

        card = {
            "pattern_id": pattern_id,
            "fraud_type": ft,
            "title": pdef["title"],
            "narrative": pdef["narrative"],
            "signature": pdef["signature"],
            "typical_severity": pdef["typical_severity"],
            "example_claim_ids": example_ids
        }
        cards.append(card)

    return cards


def main():
    print(f"🔍 Compiling Fraud Pattern Cards from {CLAIMS_PATH}...")
    cards = build_pattern_cards()
    print(f"✅ Generated {len(cards)} distinctive pattern cards across all fraud types (target: 40-60).")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2)

    print(f"💾 Saved fraud pattern catalog to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
