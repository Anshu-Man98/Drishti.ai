#!/usr/bin/env python3
"""
scripts/generate_eval_bills.py

Generates 32 fresh evaluation hospital bills using ReportLab across 12 Indian cities,
9 diagnoses, multiple hospital layouts, serif/sans fonts, single and multi-page.
Realistic price variance modeling Indian private hospital tiers (metro vs tier-2, ward vs deluxe).

Categories of bills:
- 25 clean bills across normal price bands (ground truth: APPROVE)
- 2 with +20% moderate inflation (ground truth: REVIEW, never APPROVE)
- 1 with +40% high inflation (ground truth: REVIEW or REJECT, never APPROVE)
- 1 with +60% severe inflation (ground truth: REJECT)
- 1 with arithmetic mismatch (ground truth: REJECT)
- 1 with policy room rent cap breach (ground truth: REVIEW)
- 1 with unbundled/padded surgical consumables (ground truth: REVIEW)

Outputs PDF files to data/eval_bills/ and writes ground truth to data/eval_bills/ground_truth.json.
"""

import os
import json
import random
from pathlib import Path
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "data" / "eval_bills"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GT_PATH = OUTPUT_DIR / "ground_truth.json"

random.seed(4242)

HOSPITALS = [
    {"name": "Sunrise Multispeciality Hospital", "address": "Tonk Road, Bapu Nagar", "city": "Jaipur", "tier": "tier2"},
    {"name": "Narayana Hrudayalaya Speciality Hospital", "address": "Hosur Road, Bommasandra", "city": "Bengaluru", "tier": "metro"},
    {"name": "Ruby Hall Clinic & Medical Research", "address": "40 Sassoon Road, Sangamvadi", "city": "Pune", "tier": "tier2"},
    {"name": "Medanta The Medicity Hospital", "address": "Sector 38, Golf City", "city": "Lucknow", "tier": "tier2"},
    {"name": "Apollo Speciality Hospital Greams Road", "address": "21 Greams Lane, Thousand Lights", "city": "Chennai", "tier": "metro"},
    {"name": "Care Hospital Banjara Hills", "address": "Road No. 1, Banjara Hills", "city": "Hyderabad", "tier": "metro"},
    {"name": "Fortis Escorts Hospital Malviya Nagar", "address": "Jawaharlal Nehru Marg", "city": "Jaipur", "tier": "tier2"},
    {"name": "Lilavati Hospital & Research Centre", "address": "A-791 Bandra Reclamation", "city": "Mumbai", "tier": "metro"},
    {"name": "Sir Ganga Ram Hospital", "address": "Rajinder Nagar", "city": "New Delhi", "tier": "metro"},
    {"name": "Manipal Hospital Old Airport Road", "address": "98 HAL Old Airport Road", "city": "Bengaluru", "tier": "metro"},
    {"name": "Kokilaben Dhirubhai Ambani Hospital", "address": "Rao Saheb Achutrao Patwardhan Marg", "city": "Mumbai", "tier": "metro"},
    {"name": "Aster Medcity Cheranalloor", "address": "Kuttisahib Road, South Chittoor", "city": "Kochi", "tier": "tier2"},
    {"name": "Peerless Hospital & B.K. Roy Research", "address": "360 Panchasayar", "city": "Kolkata", "tier": "tier2"},
    {"name": "KIMS Hospital Minister Road", "address": "1-8-31/1 Minister Road", "city": "Hyderabad", "tier": "metro"},
    {"name": "Sterling Hospital Memnagar", "address": "Sterling Hospital Road", "city": "Ahmedabad", "tier": "tier2"},
    {"name": "Max Super Speciality Hospital Mohali", "address": "Near Civil Hospital, Phase 6", "city": "Chandigarh", "tier": "tier2"}
]

PATIENTS = [
    "Meera Nair", "Suresh Menon", "Sunita Kulkarni", "Amit Saxena", "Pooja Hegde",
    "Lakshmi Rao", "Vikram Rathore", "Kavita Deshmukh", "Rajesh Pillai", "Sneha Iyer",
    "Deepak Sharma", "Priyanka Joshi", "Ananya Bose", "Aarav Gupta", "Diya Mehta",
    "Arjun Verma", "Saanvi Reddy", "Aadhya Chatterjee", "Vivaan Bhat", "Riya Choudhury",
    "Ishaan Saxena", "Navya Nair", "Reyansh Kapoor", "Pari Patel", "Sai Krishna",
    "Ayaan Mishra", "Chiara Menon", "Myra Deshmukh", "Anika Kulkarni", "Aditya Sharma",
    "Vihaan Reddy", "Nikhil Bansal"
]

INSURERS = [
    {"id": "INS-STAR", "name": "Star Health and Allied Insurance", "pol_prefix": "POL-STAR"},
    {"id": "INS-HDFC", "name": "HDFC ERGO General Insurance", "pol_prefix": "POL-HDFC"},
    {"id": "INS-CARE", "name": "Care Health Insurance", "pol_prefix": "POL-CARE"},
    {"id": "INS-NIVA", "name": "Niva Bupa Health Insurance", "pol_prefix": "POL-NIVA"},
    {"id": "INS-ICICI", "name": "ICICI Lombard Health Insurance", "pol_prefix": "POL-ICICI"}
]

DIAGNOSIS_TEMPLATES = {
    "K35.8": {
        "diag": "K35.8 - Acute appendicitis (Laparoscopic appendectomy)",
        "items": [
            ("Semi-Private Room Rent", 3, 3500.0, "room_rent"),
            ("Laparoscopic Appendectomy OT Charges", 1, 35000.0, "surgery_ot"),
            ("Surgeon & Anesthesia Visiting Fees", 3, 1800.0, "consultation"),
            ("Routine Post-Op Pharmacy & Fluids", 1, 4500.0, "pharmacy"),
            ("Pre-Op Diagnostic Investigations (CBC, USG)", 1, 3500.0, "diagnostics"),
        ]
    },
    "K80.2": {
        "diag": "K80.2 - Calculus of gallbladder (Cholecystectomy)",
        "items": [
            ("Twin Sharing Room Charges", 3, 4000.0, "room_rent"),
            ("Laparoscopic Cholecystectomy Procedure Fee", 1, 42000.0, "surgery_ot"),
            ("Consulting Specialist Doctor Fees", 3, 2000.0, "consultation"),
            ("Hospital Pharmacy Medications & Injections", 1, 5500.0, "pharmacy"),
            ("Abdominal Ultrasound & Pathology Panel", 1, 4000.0, "diagnostics"),
        ]
    },
    "J18.9": {
        "diag": "J18.9 - Pneumonia, unspecified (Inpatient medical management)",
        "items": [
            ("General Ward Hospital Bed", 4, 2800.0, "room_rent"),
            ("Pulmonologist Daily Rounds", 4, 1200.0, "consultation"),
            ("Chest X-Ray & Sputum Culture Diagnostics", 1, 4500.0, "diagnostics"),
            ("IV Antibiotic Therapy & Respiratory Medications", 1, 6200.0, "pharmacy"),
            ("Nebulization & Oxygen Support Services", 4, 600.0, "ancillary"),
        ]
    },
    "S82.8": {
        "diag": "S82.8 - Fracture of lower leg (ORIF surgery)",
        "items": [
            ("Orthopedic Ward Bed Charges", 4, 3800.0, "room_rent"),
            ("ORIF Leg Fracture Surgical & OT Charges", 1, 42000.0, "surgery_ot"),
            ("Orthopedic Surgeon & Anesthetist Visit Fees", 4, 1500.0, "consultation"),
            ("Post-Surgical Antibiotics & Pain Medications", 1, 5500.0, "pharmacy"),
            ("Digital X-Ray Pre & Post Operative", 2, 1200.0, "diagnostics"),
        ]
    },
    "E11.9": {
        "diag": "E11.9 - Type 2 diabetes with acute complications",
        "items": [
            ("Medical Ward Stay", 3, 4000.0, "room_rent"),
            ("Endocrinologist & Physician Consultation", 3, 2000.0, "consultation"),
            ("Insulin Infusion & Metabolic Pharmacy", 1, 8500.0, "pharmacy"),
            ("Comprehensive Metabolic Panel & Glycemic Lab", 1, 5500.0, "diagnostics"),
            ("Bedside Nursing Care & Vitals Monitoring", 3, 1200.0, "ancillary"),
        ]
    },
    "N39.0": {
        "diag": "N39.0 - Urinary tract infection, acute inpatient",
        "items": [
            ("Inpatient Semi-Private Bed", 3, 3000.0, "room_rent"),
            ("Urologist & Medical Officer Visits", 3, 1200.0, "consultation"),
            ("Targeted IV Antibiotic Pharmacy", 1, 4800.0, "pharmacy"),
            ("Renal Ultrasound & Urine Culture Testing", 1, 3600.0, "diagnostics"),
        ]
    },
    "A09": {
        "diag": "A09 - Infectious gastroenteritis and colitis",
        "items": [
            ("Hospital Ward Bed", 2, 2800.0, "room_rent"),
            ("Attending Physician Visit Fees", 2, 1000.0, "consultation"),
            ("Electrolyte Replacement & Anti-infective Pharmacy", 1, 3500.0, "pharmacy"),
            ("Stool Routine & Blood Investigation Lab", 1, 2400.0, "diagnostics"),
            ("IV Infusion Administration & Nursing Care", 2, 800.0, "ancillary"),
        ]
    },
    "M54.5": {
        "diag": "M54.5 - Low back pain with acute radiculopathy",
        "items": [
            ("Ward Bed Charges", 4, 3000.0, "room_rent"),
            ("Physiotherapy session", 6, 1200.0, "consultation"),
            ("MRI lumbar spine", 1, 9500.0, "diagnostics"),
            ("Consultation", 4, 1000.0, "consultation"),
        ]
    },
    "I20.9": {
        "diag": "I20.9 - Angina pectoris, unspecified",
        "items": [
            ("Cardiac Care Ward Stay", 4, 4500.0, "room_rent"),
            ("Coronary Angiography Procedure Fee", 1, 45000.0, "surgery_ot"),
            ("Senior Cardiologist Inpatient Fees", 4, 2000.0, "consultation"),
            ("Cardiovascular Injectables & Medications", 1, 7500.0, "pharmacy"),
            ("2D Echo & Cardiac Biomarker Panel", 1, 5500.0, "diagnostics"),
        ]
    }
}


def build_bill_pdf(
    path: Path,
    hosp: dict,
    bill_no: str,
    bill_date: str,
    patient_name: str,
    patient_id: str,
    policy_no: str,
    insurer_name: str,
    doctor_name: str,
    doctor_id: str,
    admission_date: str,
    discharge_date: str,
    diagnosis_str: str,
    items: list,
    subtotal: float,
    tax: float,
    total: float,
    font_name: str = "Helvetica",
    multipage: bool = False
):
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=38,
        rightMargin=38,
        topMargin=38,
        bottomMargin=38
    )
    styles = getSampleStyleSheet()
    font_bold = f"{font_name}-Bold" if font_name != "Times-Roman" else "Times-Bold"

    title_style = ParagraphStyle(
        "HospitalTitle", parent=styles["Heading1"],
        fontName=font_bold, fontSize=16, leading=20, textColor=colors.HexColor("#0F172A")
    )
    sub_style = ParagraphStyle(
        "HospitalSub", parent=styles["Normal"],
        fontName=font_name, fontSize=8.5, leading=12, textColor=colors.HexColor("#475569")
    )
    section_style = ParagraphStyle(
        "SectionHeader", parent=styles["Heading3"],
        fontName=font_bold, fontSize=10, leading=14, textColor=colors.HexColor("#1E293B")
    )
    cell_style = ParagraphStyle(
        "CellNormal", parent=styles["Normal"],
        fontName=font_name, fontSize=8.5, leading=11, textColor=colors.HexColor("#1E293B")
    )
    cell_bold = ParagraphStyle(
        "CellBold", parent=styles["Normal"],
        fontName=font_bold, fontSize=8.5, leading=11, textColor=colors.HexColor("#0F172A")
    )
    cell_num = ParagraphStyle(
        "CellNum", parent=styles["Normal"],
        fontName=font_name, fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor("#1E293B")
    )
    cell_num_bold = ParagraphStyle(
        "CellNumBold", parent=styles["Normal"],
        fontName=font_bold, fontSize=9, leading=12, alignment=2, textColor=colors.HexColor("#0F172A")
    )

    story = []

    # Header
    header_data = [
        [Paragraph(hosp["name"], title_style), Paragraph(f"<b>FINAL INPATIENT BILL</b><br/>Bill No: {bill_no}<br/>Date: {bill_date}", cell_num)],
        [Paragraph(f"{hosp['address']}, {hosp['city']} | Phone: +91-11-4000-8800 | GSTIN: 07AAAAA1234A1Z5", sub_style), ""]
    ]
    t_header = Table(header_data, colWidths=[360, 160])
    t_header.setStyle(TableStyle([
        ("SPAN", (0, 1), (1, 1)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))

    # Meta
    meta_data = [
        [
            Paragraph("<b>Patient Name:</b> " + patient_name, cell_style),
            Paragraph("<b>UHID / IP No:</b> " + patient_id, cell_style),
            Paragraph("<b>Admission:</b> " + admission_date, cell_style),
        ],
        [
            Paragraph("<b>Policy No:</b> " + policy_no, cell_style),
            Paragraph("<b>TPA / Insurer:</b> " + insurer_name, cell_style),
            Paragraph("<b>Discharge:</b> " + discharge_date, cell_style),
        ],
        [
            Paragraph("<b>Consulting Doctor:</b> " + doctor_name, cell_style),
            Paragraph("<b>Doctor Reg No:</b> " + doctor_id, cell_style),
            Paragraph("<b>Length of Stay:</b> 3-4 Days", cell_style),
        ],
        [
            Paragraph("<b>Primary Diagnosis:</b> " + diagnosis_str, cell_style),
            "",
            ""
        ]
    ]
    t_meta = Table(meta_data, colWidths=[180, 180, 160])
    t_meta.setStyle(TableStyle([
        ("SPAN", (0, 3), (2, 3)),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # Items table
    story.append(Paragraph("ITEMIZED HOSPITAL CHARGES", section_style))
    story.append(Spacer(1, 4))

    table_data = [
        [
            Paragraph("#", cell_bold),
            Paragraph("Description of Services / Consumables", cell_bold),
            Paragraph("Qty", cell_num_bold),
            Paragraph("Rate (₹)", cell_num_bold),
            Paragraph("Amount (₹)", cell_num_bold)
        ]
    ]

    for idx, itm in enumerate(items, 1):
        desc, qty, rate, amt = itm[0], itm[1], itm[2], itm[3]
        table_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(desc, cell_style),
            Paragraph(f"{qty:.1f}" if isinstance(qty, float) and not qty.is_integer() else str(int(qty)), cell_num),
            Paragraph(f"{rate:,.2f}", cell_num),
            Paragraph(f"{amt:,.2f}", cell_num),
        ])

    table_data.append([
        "", Paragraph("Subtotal", cell_bold), "", "",
        Paragraph(f"{subtotal:,.2f}", cell_num_bold)
    ])
    table_data.append([
        "", Paragraph("Taxes & Hospital Surcharge (5% GST)", cell_style), "", "",
        Paragraph(f"{tax:,.2f}", cell_num)
    ])
    table_data.append([
        "", Paragraph("<b>TOTAL AMOUNT PAYABLE (INR)</b>", cell_bold), "", "",
        Paragraph(f"<b>₹{total:,.2f}</b>", cell_num_bold)
    ])

    col_widths = [25, 265, 45, 90, 95]
    t_items = Table(table_data, colWidths=col_widths)
    t_items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -4), 0.5, colors.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, -4), (-1, -4), 1, colors.HexColor("#64748B")),
        ("LINEBELOW", (1, -1), (-1, -1), 1.5, colors.HexColor("#0F172A")),
        ("BACKGROUND", (1, -1), (-1, -1), colors.HexColor("#F1F5F9")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 14))

    if multipage:
        story.append(PageBreak())
        story.append(Paragraph("DISCHARGE SUMMARY & AUTHORIZATION", section_style))
        story.append(Spacer(1, 8))

    auth_data = [
        [
            Paragraph("<b>Terms & Conditions:</b><br/>1. All procedures were pre-authorized by TPA under corporate health cover.<br/>2. Discharged in stable hemodynamically normal state.<br/>3. Payment received via cashless TPA settlement counter.", sub_style),
            Paragraph(f"<b>Authorized Hospital Signatory</b><br/><br/><br/>___________________________<br/>{doctor_name} ({doctor_id})", cell_style)
        ]
    ]
    t_auth = Table(auth_data, colWidths=[340, 180])
    t_auth.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_auth)

    doc.build(story)


def generate_all():
    records = []
    bill_idx = 1

    # 32 bills: 25 clean, 2 inflated 20%, 1 inflated 40%, 1 inflated 60%, 1 arithmetic mismatch, 1 room rent breach, 1 padded ancillary
    diagnoses_keys = list(DIAGNOSIS_TEMPLATES.keys())

    for i in range(32):
        diag_code = diagnoses_keys[i % len(diagnoses_keys)]
        template = DIAGNOSIS_TEMPLATES[diag_code]
        hosp = HOSPITALS[i % len(HOSPITALS)]
        patient_name = PATIENTS[i % len(PATIENTS)]
        insurer = INSURERS[i % len(INSURERS)]
        font_name = "Times-Roman" if i % 3 == 0 else "Helvetica"
        multipage = (i % 5 == 0)

        bill_no = f"INV-2026-EVAL-{bill_idx:03d}"
        patient_id = f"UHID-EV-{1000 + bill_idx}"
        policy_no = f"{insurer['pol_prefix']}-{70000 + bill_idx}"
        doctor_name = f"Dr. {random.choice(['Arvind Deshmukh', 'Kavita Rao', 'Pooja Saxena', 'Sanjay Bhatt', 'Sunil Narang', 'Ananya Sengupta'])}"
        doctor_id = f"DOC-REG-{3000 + bill_idx}"
        adm_date = f"2026-03-{10 + (i % 15):02d}"
        dis_date = f"2026-03-{13 + (i % 15):02d}"

        # Determine fraud type
        if i == 1:
            fraud_type = "arithmetic_mismatch"
        elif i == 9:
            fraud_type = "inflated_20pct"
        elif i == 14:
            fraud_type = "room_rent_cap_breach"
        elif i == 19:
            fraud_type = "inflated_20pct"
        elif i == 24:
            fraud_type = "padded_ancillary"
        elif i == 28:
            fraud_type = "inflated_40pct"
        elif i == 31:
            fraud_type = "severe_inflation_60pct"
        else:
            fraud_type = "clean"

        # Multiplier modeling metro vs tier-2
        tier_mult = 1.15 if hosp["tier"] == "metro" else 0.95
        # Individual random jitter +/- 6%
        jitter = random.uniform(0.94, 1.06)

        raw_items = template["items"]
        generated_items = []
        subtotal = 0.0

        if fraud_type == "clean":
            for desc, qty, rate, cat in raw_items:
                adj_rate = round(rate * tier_mult * jitter, 2)
                amt = round(qty * adj_rate, 2)
                generated_items.append((desc, qty, adj_rate, amt, cat))
                subtotal += amt
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
            expected_verdict = "approve"
            description = f"Clean private hospital bill ({hosp['city']}, {diag_code})"

        elif fraud_type == "arithmetic_mismatch":
            for desc, qty, rate, cat in raw_items:
                adj_rate = round(rate * tier_mult, 2)
                amt = round(qty * adj_rate, 2)
                generated_items.append((desc, qty, adj_rate, amt, cat))
                subtotal += amt
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax + 15000.0, 2)  # Discrepancy of 15,000 INR
            expected_verdict = "reject"
            description = f"Arithmetic mismatch: total exceeds item sum by ₹15,000"

        elif fraud_type == "inflated_20pct":
            # Inflate each rate by +30%
            for desc, qty, rate, cat in raw_items:
                adj_rate = round(rate * 1.30, 2)
                amt = round(qty * adj_rate, 2)
                generated_items.append((desc, qty, adj_rate, amt, cat))
                subtotal += amt
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
            expected_verdict = "review"
            description = f"Systematic +20-25% price inflation across all line items"

        elif fraud_type == "inflated_40pct":
            # Inflate each rate by +45%
            for desc, qty, rate, cat in raw_items:
                adj_rate = round(rate * 1.45, 2)
                amt = round(qty * adj_rate, 2)
                generated_items.append((desc, qty, adj_rate, amt, cat))
                subtotal += amt
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
            expected_verdict = "review"
            description = f"Severe +40-45% price inflation across all line items"

        elif fraud_type == "severe_inflation_60pct":
            # Inflate each rate by +65%
            for desc, qty, rate, cat in raw_items:
                adj_rate = round(rate * 1.65, 2)
                amt = round(qty * adj_rate, 2)
                generated_items.append((desc, qty, adj_rate, amt, cat))
                subtotal += amt
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
            expected_verdict = "reject"
            description = f"Extreme +60-65% price inflation across all line items"

        elif fraud_type == "room_rent_cap_breach":
            for desc, qty, rate, cat in raw_items:
                if cat == "room_rent":
                    adj_rate = 14000.0  # Breaches standard room rent cap (e.g. ₹5,000)
                else:
                    adj_rate = round(rate * tier_mult, 2)
                amt = round(qty * adj_rate, 2)
                generated_items.append((desc, qty, adj_rate, amt, cat))
                subtotal += amt
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
            expected_verdict = "review"
            description = f"Room rent tariff cap overrun (₹14,000/day vs policy limit)"

        elif fraud_type == "padded_ancillary":
            # Add multiple padded surgical consumables totaling > ₹25,000 and > 35% of bill
            for desc, qty, rate, cat in raw_items:
                adj_rate = round(rate * 0.85, 2)
                amt = round(qty * adj_rate, 2)
                generated_items.append((desc, qty, adj_rate, amt, cat))
                subtotal += amt
            padded_ancillaries = [
                ("Disposable Surgical Consumables Kit", 1, 14500.0, 14500.0, "ancillary"),
                ("Sterile OT Drapes & Protective Packs", 2, 4500.0, 9000.0, "ancillary"),
                ("Specialized Suture & Hemostatic Clips Pack", 1, 8500.0, 8500.0, "ancillary"),
            ]
            for desc, qty, rate, amt, cat in padded_ancillaries:
                generated_items.append((desc, qty, rate, amt, cat))
                subtotal += amt
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
            expected_verdict = "review"
            description = f"Padded ancillary/consumables: ₹32,000 (> 35% of total bill)"

        pdf_filename = f"eval_bill_{bill_idx:02d}_{hosp['city'].lower().replace(' ', '_')}_{fraud_type}.pdf"
        pdf_path = OUTPUT_DIR / pdf_filename

        build_bill_pdf(
            path=pdf_path,
            hosp=hosp,
            bill_no=bill_no,
            bill_date=dis_date,
            patient_name=patient_name,
            patient_id=patient_id,
            policy_no=policy_no,
            insurer_name=insurer["name"],
            doctor_name=doctor_name,
            doctor_id=doctor_id,
            admission_date=adm_date,
            discharge_date=dis_date,
            diagnosis_str=template["diag"],
            items=[(itm[0], itm[1], itm[2], itm[3]) for itm in generated_items],
            subtotal=subtotal,
            tax=tax,
            total=total,
            font_name=font_name,
            multipage=multipage
        )

        records.append({
            "eval_id": f"EVAL-{bill_idx:02d}",
            "filename": pdf_filename,
            "pdf_path": str(pdf_path),
            "hospital": hosp["name"],
            "city": hosp["city"],
            "patient_name": patient_name,
            "patient_id": patient_id,
            "policy_no": policy_no,
            "insurer_id": insurer["id"],
            "insurer_name": insurer["name"],
            "doctor_id": doctor_id,
            "doctor_name": doctor_name,
            "admission_date": adm_date,
            "discharge_date": dis_date,
            "diagnosis_code": diag_code,
            "diagnosis_name": template["diag"],
            "line_items": [
                {
                    "description": itm[0],
                    "qty": itm[1],
                    "unit_price": itm[2],
                    "amount": itm[3],
                    "category": itm[4]
                }
                for itm in generated_items
            ],
            "subtotal": subtotal,
            "tax": tax,
            "total_claimed": total,
            "fraud_type": fraud_type,
            "expected_verdict": expected_verdict,
            "description": description
        })
        bill_idx += 1

    with open(GT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print(f"Generated {len(records)} fresh evaluation bills in {OUTPUT_DIR}")
    print(f"Ground truth written to {GT_PATH}")


if __name__ == "__main__":
    generate_all()
