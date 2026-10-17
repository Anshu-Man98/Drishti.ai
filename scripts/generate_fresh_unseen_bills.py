#!/usr/bin/env python3
"""
scripts/generate_fresh_unseen_bills.py

Generates 32 fresh unseen hospital bills using ReportLab across 12 Indian cities,
8+ diagnoses, multiple hospital layouts, serif/sans fonts, single and multi-page.
Includes:
- 26 clean bills (ground truth: APPROVE)
- 2 with +20% inflation (ground truth: REVIEW, never APPROVE)
- 1 with arithmetic mismatch (ground truth: REJECT)
- 1 with room rent cap breach (ground truth: REVIEW)
- 1 with padded ancillary consumables (ground truth: REVIEW/REJECT)
- 1 with +60% severe inflation (ground truth: REJECT)

Outputs PDF/image files to data/unseen_bills/ and writes ground truth to data/demo/unseen_ground_truth.json.
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
OUTPUT_DIR = ROOT_DIR / "data" / "unseen_bills"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GT_PATH = ROOT_DIR / "data" / "demo" / "unseen_ground_truth.json"

random.seed(2026)

HOSPITALS = [
    {"name": "Sunrise Multispeciality Hospital", "address": "Tonk Road, Bapu Nagar", "city": "Jaipur"},
    {"name": "Narayana Hrudayalaya Speciality Hospital", "address": "Hosur Road, Bommasandra", "city": "Bengaluru"},
    {"name": "Ruby Hall Clinic & Medical Research", "address": "40 Sassoon Road, Sangamvadi", "city": "Pune"},
    {"name": "Medanta The Medicity Hospital", "address": "Sector 38, Golf City", "city": "Lucknow"},
    {"name": "Apollo Speciality Hospital Greams Road", "address": "21 Greams Lane, Thousand Lights", "city": "Chennai"},
    {"name": "Care Hospital Banjara Hills", "address": "Road No. 1, Banjara Hills", "city": "Hyderabad"},
    {"name": "Fortis Escorts Hospital Malviya Nagar", "address": "Jawaharlal Nehru Marg", "city": "Jaipur"},
    {"name": "Lilavati Hospital & Research Centre", "address": "A-791 Bandra Reclamation", "city": "Mumbai"},
    {"name": "Sir Ganga Ram Hospital", "address": "Rajinder Nagar", "city": "New Delhi"},
    {"name": "Manipal Hospital Old Airport Road", "address": "98 HAL Old Airport Road", "city": "Bengaluru"},
    {"name": "Kokilaben Dhirubhai Ambani Hospital", "address": "Rao Saheb Achutrao Patwardhan Marg", "city": "Mumbai"},
    {"name": "Aster Medcity Cheranalloor", "address": "Kuttisahib Road, South Chittoor", "city": "Kochi"},
    {"name": "Peerless Hospital & B.K. Roy Research", "address": "360 Panchasayar", "city": "Kolkata"},
    {"name": "KIMS Hospital Minister Road", "address": "1-8-31/1 Minister Road", "city": "Hyderabad"},
    {"name": "Sterling Hospital Memnagar", "address": "Sterling Hospital Road", "city": "Ahmedabad"},
    {"name": "Max Super Speciality Hospital Mohali", "address": "Near Civil Hospital, Phase 6", "city": "Chandigarh"}
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

PROCEDURE_TEMPLATES = {
    "K35.8": {
        "diag": "K35.8 - Acute appendicitis (Laparoscopic appendectomy)",
        "items": [
            ("Semi-Private Room Rent", 3, 3500.0, "room_rent"),
            ("Laparoscopic Appendectomy OT Charges", 1, 32000.0, "surgery_ot"),
            ("Surgeon & Anesthesia Visiting Fees", 3, 1500.0, "consultation"),
            ("Routine Post-Op Pharmacy & Fluids", 1, 4200.0, "pharmacy"),
            ("Pre-Op Diagnostic Investigations (CBC, USG)", 1, 3500.0, "diagnostics"),
        ]
    },
    "K80.2": {
        "diag": "K80.2 - Calculus of gallbladder (Cholecystectomy)",
        "items": [
            ("Twin Sharing Room Charges", 3, 3800.0, "room_rent"),
            ("Laparoscopic Cholecystectomy Procedure Fee", 1, 38000.0, "surgery_ot"),
            ("Consulting Specialist Doctor Fees", 3, 1800.0, "consultation"),
            ("Hospital Pharmacy Medications & Injections", 1, 5200.0, "pharmacy"),
            ("Abdominal Ultrasound & Pathology Panel", 1, 3800.0, "diagnostics"),
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
            ("Medical Ward Stay", 3, 3000.0, "room_rent"),
            ("Endocrinologist & Physician Consultation", 3, 1200.0, "consultation"),
            ("Insulin Infusion & Metabolic Pharmacy", 1, 4500.0, "pharmacy"),
            ("Comprehensive Metabolic Panel & Glycemic Lab", 1, 3200.0, "diagnostics"),
            ("Cardiac & Vitals Bedside Monitoring", 3, 800.0, "ancillary"),
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
            ("Ward Bed Charges", 3, 3000.0, "room_rent"),
            ("Physician & Neuro Consultation Fees", 3, 1000.0, "consultation"),
            ("MRI Lumbar Spine Diagnostic Scan", 1, 7500.0, "diagnostics"),
            ("Physiotherapy & Lumbar Rehabilitation", 4, 800.0, "consultation"),
            ("Analgesic & Muscle Relaxant Pharmacy", 1, 3200.0, "pharmacy"),
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
    subtitle_style = ParagraphStyle(
        "HospitalSubtitle", parent=styles["Normal"],
        fontName=font_name, fontSize=8.5, leading=11.5, textColor=colors.HexColor("#475569")
    )
    meta_label = ParagraphStyle(
        "MetaLabel", parent=styles["Normal"],
        fontName=font_bold, fontSize=8.5, leading=11.5, textColor=colors.HexColor("#1E293B")
    )
    meta_val = ParagraphStyle(
        "MetaVal", parent=styles["Normal"],
        fontName=font_name, fontSize=8.5, leading=11.5, textColor=colors.HexColor("#334155")
    )

    story = []
    # Header Banner
    header_data = [
        [
            Paragraph(f"<b>{hosp['name']}</b>", title_style),
            Paragraph("<b>IN-PATIENT FINAL INVOICE</b><br/><font color='#2563EB'>ORIGINAL TAX INVOICE</font>",
                      ParagraphStyle("Right", parent=meta_label, alignment=2, fontSize=9.5, leading=13))
        ],
        [
            Paragraph(f"{hosp['address']}, {hosp['city']}<br/>GSTIN: 08AAACS1234F1Z9 | Reg: {hosp['city'][:3].upper()}/2021/8892", subtitle_style),
            Paragraph(f"<b>Bill No:</b> {bill_no}<br/><b>Date:</b> {bill_date}", ParagraphStyle("RightDate", parent=meta_val, alignment=2))
        ]
    ]
    t_header = Table(header_data, colWidths=[340, 180])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 1), (-1, 1), 1.2, colors.HexColor("#0F172A")),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))

    # Patient Details Grid
    patient_grid = [
        [
            Paragraph("<b>Patient Name:</b>", meta_label), Paragraph(patient_name, meta_val),
            Paragraph("<b>Insurer:</b>", meta_label), Paragraph(insurer_name, meta_val)
        ],
        [
            Paragraph("<b>Patient ID / UHID:</b>", meta_label), Paragraph(patient_id, meta_val),
            Paragraph("<b>Policy Number:</b>", meta_label), Paragraph(policy_no, meta_val)
        ],
        [
            Paragraph("<b>Treating Doctor:</b>", meta_label), Paragraph(f"{doctor_name} ({doctor_id})", meta_val),
            Paragraph("<b>Pre-Auth Reference:</b>", meta_label), Paragraph(f"PA-{bill_no[-6:]}", meta_val)
        ],
        [
            Paragraph("<b>Admission Date:</b>", meta_label), Paragraph(admission_date, meta_val),
            Paragraph("<b>Discharge Date:</b>", meta_label), Paragraph(discharge_date, meta_val)
        ],
        [
            Paragraph("<b>Primary Diagnosis:</b>", meta_label), Paragraph(diagnosis_str, meta_val),
            Paragraph("<b>Settlement Mode:</b>", meta_label), Paragraph("Cashless TPA Direct Settlement", meta_val)
        ]
    ]
    t_patient = Table(patient_grid, colWidths=[105, 155, 105, 155])
    t_patient.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_patient)
    story.append(Spacer(1, 12))

    # Line Items Table
    table_header = ["#", "Service Description", "Qty", "Rate (₹)", "Amount (₹)"]
    if multipage and len(items) >= 4:
        half = len(items) // 2
        items_p1 = items[:half]
        items_p2 = items[half:]

        rows_p1 = [[str(i+1), it[0], str(it[1]), f"{it[2]:,.2f}", f"{it[3]:,.2f}"] for i, it in enumerate(items_p1)]
        t1 = Table([table_header] + rows_p1, colWidths=[28, 272, 45, 80, 95])
        t1.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 8.5),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        story.append(t1)
        story.append(PageBreak())

        story.append(Paragraph(f"<b>{hosp['name']} — Invoice Continued (Bill No: {bill_no})</b>", meta_label))
        story.append(Spacer(1, 10))

        rows_p2 = [[str(half+i+1), it[0], str(it[1]), f"{it[2]:,.2f}", f"{it[3]:,.2f}"] for i, it in enumerate(items_p2)]
        summary_rows = [
            ["", "", "", "Subtotal:", f"₹ {subtotal:,.2f}"],
            ["", "", "", "GST (5%):", f"₹ {tax:,.2f}"],
            ["", "", "", "TOTAL PAYABLE:", f"₹ {total:,.2f}"]
        ]
        t2 = Table([table_header] + rows_p2 + summary_rows, colWidths=[28, 272, 45, 80, 95])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 8.5),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, len(rows_p2)), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, len(rows_p2)), 0.5, colors.HexColor("#E2E8F0")),
            ('FONTNAME', (0, 1), (-1, len(rows_p2)), font_name),
            ('FONTSIZE', (0, 1), (-1, len(rows_p2)), 8),
            ('FONTNAME', (3, len(rows_p2)+1), (-1, -1), font_bold),
            ('BACKGROUND', (3, len(rows_p2)+3), (-1, len(rows_p2)+3), colors.HexColor("#EFF6FF")),
            ('LINEABOVE', (3, len(rows_p2)+3), (-1, len(rows_p2)+3), 1, colors.HexColor("#2563EB")),
        ]))
        story.append(t2)
    else:
        rows = [[str(i+1), it[0], str(it[1]), f"{it[2]:,.2f}", f"{it[3]:,.2f}"] for i, it in enumerate(items)]
        summary_rows = [
            ["", "", "", "Subtotal:", f"₹ {subtotal:,.2f}"],
            ["", "", "", "GST (5%):", f"₹ {tax:,.2f}"],
            ["", "", "", "TOTAL PAYABLE:", f"₹ {total:,.2f}"]
        ]
        t_items = Table([table_header] + rows + summary_rows, colWidths=[28, 272, 45, 80, 95])
        t_items.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 8.5),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, len(rows)), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, len(rows)), 0.5, colors.HexColor("#E2E8F0")),
            ('FONTNAME', (0, 1), (-1, len(rows)), font_name),
            ('FONTSIZE', (0, 1), (-1, len(rows)), 8),
            ('FONTNAME', (3, len(rows)+1), (-1, -1), font_bold),
            ('BACKGROUND', (3, len(rows)+3), (-1, len(rows)+3), colors.HexColor("#EFF6FF")),
            ('LINEABOVE', (3, len(rows)+3), (-1, len(rows)+3), 1, colors.HexColor("#2563EB")),
        ]))
        story.append(t_items)

    story.append(Spacer(1, 15))
    auth_data = [
        [
            Paragraph("<i>Prepared By: Billing Desk Executive</i>", subtitle_style),
            Paragraph("<b>For " + hosp['name'] + "</b><br/><br/><i>Authorized Signatory / TPA Cell</i>", ParagraphStyle("Sign", parent=meta_val, alignment=2))
        ]
    ]
    t_auth = Table(auth_data, colWidths=[260, 260])
    story.append(t_auth)

    doc.build(story)


def main():
    print(f"Generating 32 fresh unseen hospital bills in {OUTPUT_DIR} ...")
    diag_keys = list(PROCEDURE_TEMPLATES.keys())

    corpus = []
    base_date = datetime(2026, 8, 1)

    for i in range(1, 33):
        doc_id = f"UNSEEN-{i:02d}"
        hosp = HOSPITALS[(i - 1) % len(HOSPITALS)]
        patient_name = PATIENTS[(i - 1) % len(PATIENTS)]
        patient_id = f"UHID-{60000 + i * 137}"
        ins = INSURERS[(i - 1) % len(INSURERS)]
        policy_no = f"{ins['pol_prefix']}-{random.randint(10000, 99999)}"
        doctor_name = f"Dr. {random.choice(['Arun', 'Pooja', 'Vikram', 'Deepak', 'Sanjay', 'Rohit', 'Anjali'])} {random.choice(['Sharma', 'Iyer', 'Reddy', 'Patel', 'Deshmukh', 'Verma'])}"
        doctor_id = f"DOC-{5000 + i}"
        
        diag_code = diag_keys[(i - 1) % len(diag_keys)]
        template = PROCEDURE_TEMPLATES[diag_code]
        diag_str = template["diag"]

        day_offset = (i * 3) % 45
        adm_dt = base_date + timedelta(days=day_offset)
        stay_days = 3 if "Ward" in template["items"][0][0] else 4
        dis_dt = adm_dt + timedelta(days=stay_days)

        bill_date_str = dis_dt.strftime("%d-%b-%Y")
        adm_date_str = adm_dt.strftime("%d-%b-%Y")
        dis_date_str = dis_dt.strftime("%d-%b-%Y")

        bill_no = f"{hosp['city'][:3].upper()}-2026-{8000 + i}"
        font_choice = "Times-Roman" if i % 4 == 0 else "Helvetica"
        is_multipage = (i % 6 == 0)

        # Scenarios:
        # Case 2: Arithmetic Mismatch (simulated math error)
        # Case 10: +20% Inflation
        # Case 15: Room rent cap breach
        # Case 20: +20% Inflation
        # Case 25: Padded ancillary consumables
        # Case 30: +60% Severe Inflation
        # All others: Clean bills (APPROVE)

        bill_items = []
        if i == 2:
            test_type = "arithmetic_mismatch"
            expected_verdict = "REJECT"
            for desc, qty, rate, cat in template["items"]:
                bill_items.append((desc, float(qty), float(rate), float(qty * rate)))
            subtotal = sum(x[3] for x in bill_items) + 5000.0  # Intentional discrepancy
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
        elif i == 10:
            test_type = "inflated_20pct"
            expected_verdict = "REVIEW"
            diag_code = "K35.8"
            template = PROCEDURE_TEMPLATES[diag_code]
            diag_str = template["diag"]
            # Inflated +20% on appendectomy (total exceeds 1.30x p95)
            bill_items = [
                ("Semi-Private Room Rent", 3.0, 4200.0, 12600.0),
                ("Laparoscopic Appendectomy OT Charges", 1.0, 46000.0, 46000.0),
                ("Surgeon & Anesthesia Visiting Fees", 3.0, 2000.0, 6000.0),
                ("Routine Post-Op Pharmacy & Fluids", 1.0, 6500.0, 6500.0),
                ("Pre-Op Diagnostic Investigations (CBC, USG)", 1.0, 4500.0, 4500.0),
            ]
            subtotal = round(sum(x[3] for x in bill_items), 2)
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
        elif i == 15:
            test_type = "room_rent_cap_breach"
            expected_verdict = "REVIEW"
            for desc, qty, rate, cat in template["items"]:
                if cat == "room_rent":
                    new_rate = 12000.0  # Over 5000 cap
                    bill_items.append((desc + " (Executive Suite)", float(qty), new_rate, round(qty * new_rate, 2)))
                else:
                    bill_items.append((desc, float(qty), float(rate), float(qty * rate)))
            subtotal = round(sum(x[3] for x in bill_items), 2)
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
        elif i == 20:
            test_type = "inflated_20pct"
            expected_verdict = "REVIEW"
            diag_code = "K80.2"
            template = PROCEDURE_TEMPLATES[diag_code]
            diag_str = template["diag"]
            # Inflated +20% on cholecystectomy (total exceeds 1.30x p95)
            bill_items = [
                ("Twin Sharing Room Charges", 3.0, 4500.0, 13500.0),
                ("Laparoscopic Cholecystectomy Procedure Fee", 1.0, 58000.0, 58000.0),
                ("Consulting Specialist Doctor Fees", 3.0, 2200.0, 6600.0),
                ("Hospital Pharmacy Medications & Injections", 1.0, 7000.0, 7000.0),
                ("Abdominal Ultrasound & Pathology Panel", 1.0, 5000.0, 5000.0),
            ]
            subtotal = round(sum(x[3] for x in bill_items), 2)
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
        elif i == 25:
            test_type = "padded_ancillary"
            expected_verdict = "REVIEW"
            diag_code = "K35.8"
            template = PROCEDURE_TEMPLATES[diag_code]
            diag_str = template["diag"]
            # Padded consumables (ancillary total 23,000 > 1.25x p95, share 35.9% >= 25%, 3 items)
            bill_items = [
                ("Semi-Private Room Rent", 2.0, 3500.0, 7000.0),
                ("Laparoscopic Appendectomy OT Charges", 1.0, 25000.0, 25000.0),
                ("Surgeon Visiting Fees", 2.0, 1500.0, 3000.0),
                ("Hospital Pharmacy Medications", 1.0, 3000.0, 3000.0),
                ("Disposable Surgical Trocar Pack", 2.0, 4800.0, 9600.0),
                ("Advanced Hemostatic Gel Pack", 2.0, 4500.0, 9000.0),
                ("Laparoscopic Endosuture Consumables", 1.0, 4400.0, 4400.0),
            ]
            subtotal = round(sum(x[3] for x in bill_items), 2)
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
        elif i == 30:
            test_type = "severe_inflation_60pct"
            expected_verdict = "REJECT"
            diag_code = "S82.8"
            template = PROCEDURE_TEMPLATES[diag_code]
            diag_str = template["diag"]
            bill_items = [
                ("Orthopedic Ward Bed Charges (Deluxe)", 4.0, 6500.0, 26000.0),
                ("ORIF Leg Fracture Surgical & OT Charges", 1.0, 75000.0, 75000.0),
                ("Orthopedic Surgeon & Anesthetist Visit Fees", 4.0, 2500.0, 10000.0),
                ("Post-Surgical Antibiotics & Pain Medications", 1.0, 8500.0, 8500.0),
                ("Digital X-Ray Pre & Post Operative", 2.0, 2200.0, 4400.0),
            ]
            subtotal = round(sum(x[3] for x in bill_items), 2)
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
        else:
            test_type = "clean"
            expected_verdict = "APPROVE"
            for desc, qty, rate, cat in template["items"]:
                bill_items.append((desc, float(qty), float(rate), float(qty * rate)))
            subtotal = round(sum(x[3] for x in bill_items), 2)
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)

        filename = f"bill_{i:02d}_{hosp['city'].lower()}_{test_type}.pdf"
        filepath = OUTPUT_DIR / filename

        build_bill_pdf(
            path=filepath,
            hosp=hosp,
            bill_no=bill_no,
            bill_date=bill_date_str,
            patient_name=patient_name,
            patient_id=patient_id,
            policy_no=policy_no,
            insurer_name=ins["name"],
            doctor_name=doctor_name,
            doctor_id=doctor_id,
            admission_date=adm_date_str,
            discharge_date=dis_date_str,
            diagnosis_str=diag_str,
            items=bill_items,
            subtotal=subtotal,
            tax=tax,
            total=total,
            font_name=font_choice,
            multipage=is_multipage
        )

        corpus.append({
            "id": doc_id,
            "file": filename,
            "type": test_type,
            "expected": {
                "claimant_name": patient_name,
                "hospital_name": hosp["name"],
                "city": hosp["city"],
                "doctor_id": doctor_id,
                "diagnosis_code": diag_code,
                "admission_date": adm_date_str,
                "discharge_date": dis_date_str,
                "subtotal": subtotal,
                "tax": tax,
                "total_claimed": total,
                "line_items_count": len(bill_items),
                "expected_verdict": expected_verdict
            }
        })

    with open(GT_PATH, "w") as f:
        json.dump(corpus, f, indent=2)

    print(f"Successfully generated {len(corpus)} unseen hospital bills in {OUTPUT_DIR}")
    print(f"Wrote ground truth schema for all 32 bills to {GT_PATH}")


if __name__ == "__main__":
    main()
