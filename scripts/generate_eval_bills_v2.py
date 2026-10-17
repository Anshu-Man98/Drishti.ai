#!/usr/bin/env python3
"""
scripts/generate_eval_bills_v2.py

Generates evaluation test bills in data/eval_bills_v2/ using ReportLab and Pillow.
Produces clean bills, specific fraud detector triggers, and ground-truth metadata in ground_truth.json.
"""

import io
import json
import os
from pathlib import Path
import pypdf
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image, ImageFilter
import numpy as np

EVAL_DIR = Path(__file__).resolve().parent.parent / "data" / "eval_bills_v2"
EVAL_DIR.mkdir(parents=True, exist_ok=True)


def build_hospital_bill_pdf(
    out_path: Path,
    hospital_name: str,
    hospital_address: str,
    patient_name: str,
    patient_id: str,
    policy_id: str,
    diagnosis_code: str,
    diagnosis_desc: str,
    admission_str: str,
    discharge_str: str,
    bill_date_str: str,
    line_items: list,  # [(desc, qty, unit_price, amt), ...]
    subtotal: float,
    tax_rate_pct: float,
    tax_amount: float,
    total_amount: float,
    bill_no: str = "INV-2026-9042",
    producer_metadata: str = None,
    omit_totals: bool = False
):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "HospTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0F172A")
    )
    subtitle_style = ParagraphStyle(
        "HospSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569")
    )
    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B")
    )
    meta_bold = ParagraphStyle(
        "MetaBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0F172A")
    )

    story = []

    # Header
    story.append(Paragraph(hospital_name, title_style))
    story.append(Paragraph(hospital_address, subtitle_style))
    story.append(Paragraph("INPATIENT FINAL TAX INVOICE / HOSPITAL BILL", ParagraphStyle("BillType", parent=meta_bold, fontSize=11, leading=14, textColor=colors.HexColor("#0284C7"))))
    story.append(Spacer(1, 10))

    # Meta Table (2 columns)
    meta_data = [
        [
            Paragraph(f"<b>Bill Number:</b> {bill_no}", meta_style),
            Paragraph(f"<b>Bill Date:</b> {bill_date_str}", meta_style)
        ],
        [
            Paragraph(f"<b>Patient Name:</b> {patient_name}", meta_style),
            Paragraph(f"<b>Patient ID / UHID:</b> {patient_id}", meta_style)
        ],
        [
            Paragraph(f"<b>Policy / TPA ID:</b> {policy_id}", meta_style),
            Paragraph(f"<b>Insurer:</b> Star Health / FinShield Network", meta_style)
        ],
        [
            Paragraph(f"<b>Admission:</b> {admission_str}", meta_style),
            Paragraph(f"<b>Discharge:</b> {discharge_str}", meta_style)
        ],
        [
            Paragraph(f"<b>Primary Diagnosis:</b> {diagnosis_desc} ({diagnosis_code})", meta_style),
            Paragraph(f"<b>Ward / Bed:</b> Semi-Private Room W-204", meta_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Itemized Table
    item_header = [
        Paragraph("<b>#</b>", meta_bold),
        Paragraph("<b>Description of Service / Medicines</b>", meta_bold),
        Paragraph("<b>Qty</b>", meta_bold),
        Paragraph("<b>Rate (₹)</b>", meta_bold),
        Paragraph("<b>Amount (₹)</b>", meta_bold),
    ]
    table_rows = [item_header]
    for idx, (desc, qty, rate, amt) in enumerate(line_items, 1):
        table_rows.append([
            Paragraph(str(idx), meta_style),
            Paragraph(desc, meta_style),
            Paragraph(str(qty), meta_style),
            Paragraph(f"{rate:,.2f}", meta_style),
            Paragraph(f"{amt:,.2f}", meta_style),
        ])

    if not omit_totals:
        table_rows.append([
            "",
            Paragraph("<b>Subtotal (Excl. Tax)</b>", meta_bold),
            "",
            "",
            Paragraph(f"<b>{subtotal:,.2f}</b>", meta_bold)
        ])
        tax_label = f"<b>GST ({tax_rate_pct:g}%)</b>" if tax_rate_pct > 0 else "<b>GST (0% - Exempt)</b>"
        table_rows.append([
            "",
            Paragraph(tax_label, meta_bold),
            "",
            "",
            Paragraph(f"<b>{tax_amount:,.2f}</b>", meta_bold)
        ])
        table_rows.append([
            "",
            Paragraph("<b>Total Amount Payable (INR)</b>", ParagraphStyle("Tot", parent=meta_bold, fontSize=10, textColor=colors.HexColor("#0F172A"))),
            "",
            "",
            Paragraph(f"<b>₹ {total_amount:,.2f}</b>", ParagraphStyle("TotVal", parent=meta_bold, fontSize=10, textColor=colors.HexColor("#0F172A")))
        ])

    item_table = Table(table_rows, colWidths=[25, 275, 50, 95, 95])
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]
    if not omit_totals:
        t_style.extend([
            ('LINEABOVE', (0, -3), (-1, -3), 1, colors.HexColor("#64748B")),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
        ])
    item_table.setStyle(TableStyle(t_style))
    story.append(item_table)
    story.append(Spacer(1, 20))

    # Footer
    story.append(Paragraph("Authorized Signatory: Dr. Rajesh Nair, Medical Superintendent", subtitle_style))
    story.append(Paragraph("This is a computer-generated tax invoice issued by hospital administration.", subtitle_style))

    doc.build(story)
    raw_pdf = buf.getvalue()

    if producer_metadata:
        reader = pypdf.PdfReader(io.BytesIO(raw_pdf))
        writer = pypdf.PdfWriter()
        writer.append(reader)
        writer.add_metadata({
            "/Producer": producer_metadata,
            "/Creator": producer_metadata
        })
        out_buf = io.BytesIO()
        writer.write(out_buf)
        raw_pdf = out_buf.getvalue()

    with open(out_path, "wb") as f:
        f.write(raw_pdf)
    print(f"Generated {out_path.name} ({len(raw_pdf):,} bytes)")


def generate_restaurant_invoice(out_path: Path):
    """Generates non-medical restaurant bill to test NOT_A_MEDICAL_BILL gate."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>Spice Garden Bistro & Cafe</b>", styles["Heading1"]),
        Paragraph("14, Marine Drive, Churchgate, Mumbai - 400020", styles["Normal"]),
        Paragraph("GSTIN: 27AABCS1429B1Z8 | FSSAI: 11518005000291", styles["Normal"]),
        Spacer(1, 10),
        Paragraph("Table: T-12 | Steward: Ramesh | Date: 12-Oct-2026 21:15", styles["Normal"]),
        Spacer(1, 10),
    ]
    rows = [
        ["#", "Item Description", "Qty", "Price", "Amount"],
        ["1", "Paneer Tikka Masala", "1", "340.00", "340.00"],
        ["2", "Butter Garlic Naan", "4", "65.00", "260.00"],
        ["3", "Dum Biryani (Veg)", "2", "280.00", "560.00"],
        ["4", "Gulab Jamun with Ice Cream", "2", "120.00", "240.00"],
        ["", "Subtotal", "", "", "1,400.00"],
        ["", "CGST (2.5%)", "", "", "35.00"],
        ["", "SGST (2.5%)", "", "", "35.00"],
        ["", "Total Amount (INR)", "", "", "₹ 1,470.00"]
    ]
    t = Table(rows, colWidths=[30, 280, 50, 90, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#FEF3C7")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#F59E0B")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#FDE68A")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t)
    doc.build(story)
    with open(out_path, "wb") as f:
        f.write(buf.getvalue())
    print(f"Generated {out_path.name}")


def generate_noisy_rotated_png(pdf_path: Path, out_path: Path):
    """Converts PDF page 1 to PIL image, slightly rotates, adds light noise, saves as PNG."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf_path))
    page = doc.get_page(0)
    pil_img = page.render(scale=150/72).to_pil()
    page.close()
    doc.close()

    # Rotate 2 degrees with white background
    rotated = pil_img.rotate(2.0, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    
    # Add subtle gaussian blur and noise
    arr = np.array(rotated).astype(np.float32)
    noise = np.random.normal(0, 3, arr.shape)
    noisy_arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    final_img = Image.fromarray(noisy_arr)

    final_img.save(out_path, "PNG")
    print(f"Generated {out_path.name}")


def main():
    ground_truth = {}

    # 1. Base Clean Bill
    base_items = [
        ("Consultation charges (Dr. R. Nair)", 2, 800.0, 1600.0),
        ("HbA1c Glycated Hemoglobin Test", 1, 450.0, 450.0),
        ("Lipid Profile Serum Panel", 1, 700.0, 700.0),
        ("Insulin therapy & Administration", 3, 1200.0, 3600.0),
        ("Ward bed charges (Semi-Private)", 2, 2500.0, 5000.0),
    ]
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "clean_base_bill.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="10-Sep-2026 09:00",
        discharge_str="12-Sep-2026 12:00",
        bill_date_str="12-Sep-2026",
        line_items=base_items,
        subtotal=11350.0,
        tax_rate_pct=5.0,
        tax_amount=567.50,
        total_amount=11917.50
    )
    ground_truth["clean_base_bill"] = {
        "file": "clean_base_bill.pdf",
        "expected_verdict": "approve",
        "expected_risk_max": 29,
        "required_findings": [],
        "forbidden_findings": ["DUPLICATE_LINE_ITEM", "ROOM_DAYS_EXCEED_STAY", "TAX_RATE_MISMATCH", "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK"]
    }

    # 2. Clean Expensive Bill
    sahyadri_items = [
        ("Ward bed charges (3 nights)", 3, 4500.0, 13500.0),
        ("Operation Theatre (OT) Charges", 1, 20000.0, 20000.0),
        ("Surgeon Professional Fee", 1, 22000.0, 22000.0),
        ("Anaesthesia Administration Fee", 1, 6000.0, 6000.0),
        ("Inpatient Pharmacy & Consumables", 1, 3500.0, 3500.0)
    ]
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "clean_expensive_bill.pdf",
        hospital_name="Sahyadri Multispeciality Hospital",
        hospital_address="Plot 30, Karve Road, Deccan Gymkhana, Pune, Maharashtra - 411004",
        patient_name="Vijay Joshi",
        patient_id="UHID-SAHY-4109",
        policy_id="POL-HDFC-99120",
        diagnosis_code="K80.2",
        diagnosis_desc="Calculus of gallbladder without cholecystitis",
        admission_str="15-Aug-2026 08:00",
        discharge_str="18-Aug-2026 11:00",
        bill_date_str="18-Aug-2026",
        line_items=sahyadri_items,
        subtotal=65000.0,
        tax_rate_pct=5.0,
        tax_amount=3250.0,
        total_amount=68250.0
    )
    ground_truth["clean_expensive_bill"] = {
        "file": "clean_expensive_bill.pdf",
        "expected_verdict": "approve",
        "expected_risk_max": 29,
        "required_findings": [],
        "forbidden_findings": ["LINE_ITEM_PRICE_ABOVE_BENCHMARK", "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK", "TAX_RATE_MISMATCH"]
    }

    # 3. Clean Rotated Noisy Photo
    generate_noisy_rotated_png(
        EVAL_DIR / "clean_base_bill.pdf",
        EVAL_DIR / "clean_rotated_noisy_photo.png"
    )
    ground_truth["clean_rotated_noisy_photo"] = {
        "file": "clean_rotated_noisy_photo.png",
        "expected_verdict": "approve",
        "expected_risk_max": 29,
        "required_findings": [],
        "forbidden_findings": ["document_unreadable_manual_review"]
    }

    # 4. Duplicate Line Item Bill
    dup_items = list(base_items)
    dup_items.insert(4, ("Insulin therapy & Administration", 3, 1200.0, 3600.0))  # Duplicate Insulin therapy
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "duplicate_line_item.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="10-Sep-2026 09:00",
        discharge_str="12-Sep-2026 12:00",
        bill_date_str="12-Sep-2026",
        line_items=dup_items,
        subtotal=14950.0,
        tax_rate_pct=5.0,
        tax_amount=747.50,
        total_amount=15697.50
    )
    ground_truth["duplicate_line_item"] = {
        "file": "duplicate_line_item.pdf",
        "expected_verdict": "review",
        "required_findings": ["DUPLICATE_LINE_ITEM"]
    }

    # 5. Room Days Exceed Stay Bill
    exceed_stay_items = [
        ("Consultation charges (Dr. R. Nair)", 2, 800.0, 1600.0),
        ("HbA1c Glycated Hemoglobin Test", 1, 450.0, 450.0),
        ("Lipid Profile Serum Panel", 1, 700.0, 700.0),
        ("Insulin therapy & Administration", 3, 1200.0, 3600.0),
        ("Ward bed charges (Semi-Private)", 9, 2500.0, 22500.0),  # 9 days billed for 2 nights stay
    ]
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "room_days_exceed_stay.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="10-Sep-2026 09:00",
        discharge_str="12-Sep-2026 12:00",
        bill_date_str="12-Sep-2026",
        line_items=exceed_stay_items,
        subtotal=28850.0,
        tax_rate_pct=5.0,
        tax_amount=1442.50,
        total_amount=30292.50
    )
    ground_truth["room_days_exceed_stay"] = {
        "file": "room_days_exceed_stay.pdf",
        "expected_verdict": "review",
        "required_findings": ["ROOM_DAYS_EXCEED_STAY"]
    }

    # 6. Future Date Bill
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "future_date_bill.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="12-Mar-2031 09:00",
        discharge_str="14-Mar-2031 12:00",
        bill_date_str="14-Mar-2031",
        line_items=base_items,
        subtotal=11350.0,
        tax_rate_pct=5.0,
        tax_amount=567.50,
        total_amount=11917.50
    )
    ground_truth["future_date_bill"] = {
        "file": "future_date_bill.pdf",
        "expected_verdict": "reject",
        "required_findings": ["FUTURE_OR_IMPLAUSIBLE_DATE"]
    }

    # 7. Tax Rate Mismatch Bill (18% GST on Hospital Inpatient Bill)
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "tax_rate_mismatch.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="10-Sep-2026 09:00",
        discharge_str="12-Sep-2026 12:00",
        bill_date_str="12-Sep-2026",
        line_items=base_items,
        subtotal=11350.0,
        tax_rate_pct=18.0,
        tax_amount=2043.0,
        total_amount=13393.0
    )
    ground_truth["tax_rate_mismatch"] = {
        "file": "tax_rate_mismatch.pdf",
        "expected_verdict": "review",
        "required_findings": ["TAX_RATE_MISMATCH"]
    }

    # 8. Price Inflated Bill (A09 Gastroenteritis, 3x unit prices)
    inflated_items = [
        ("Ward bed charges (3 nights)", 3, 6000.0, 18000.0),  # was 2000
        ("Consultation charges", 3, 1800.0, 5400.0),         # was 600
        ("IV fluids & Electrolytes", 4, 1050.0, 4200.0),       # was 350
        ("Diagnostic lab tests (Stool/CBC)", 1, 2700.0, 2700.0), # was 900
        ("Medicines & Antibiotics", 1, 4500.0, 4500.0),      # was 1500
    ]
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "price_inflated_bill.pdf",
        hospital_name="Sahyadri Multispeciality Hospital",
        hospital_address="Plot 30, Karve Road, Deccan Gymkhana, Pune, Maharashtra - 411004",
        patient_name="Suresh Kulkarni",
        patient_id="UHID-SAHY-8199",
        policy_id="POL-STAR-77182",
        diagnosis_code="A09",
        diagnosis_desc="Infectious gastroenteritis and colitis",
        admission_str="05-Sep-2026 10:00",
        discharge_str="08-Sep-2026 14:00",
        bill_date_str="08-Sep-2026",
        line_items=inflated_items,
        subtotal=34800.0,
        tax_rate_pct=5.0,
        tax_amount=1740.0,
        total_amount=36540.0
    )
    ground_truth["price_inflated_bill"] = {
        "file": "price_inflated_bill.pdf",
        "expected_verdict": "review",
        "expected_risk_min": 45,
        "required_findings": ["LINE_ITEM_PRICE_ABOVE_BENCHMARK", "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK"]
    }

    # 9. Reversed Hospitalization Dates
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "reversed_dates_bill.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="12-Sep-2026 12:00",
        discharge_str="10-Sep-2026 09:00",
        bill_date_str="12-Sep-2026",
        line_items=base_items,
        subtotal=11350.0,
        tax_rate_pct=5.0,
        tax_amount=567.50,
        total_amount=11917.50
    )
    ground_truth["reversed_dates_bill"] = {
        "file": "reversed_dates_bill.pdf",
        "expected_verdict": "reject",
        "expected_risk_min": 85,
        "required_findings": ["REVERSED_HOSPITALIZATION_DATES"]
    }

    # 10. Subtle Arithmetic Mismatch Bill (Subtotal printed 500 too high)
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "subtle_arithmetic_mismatch.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="10-Sep-2026 09:00",
        discharge_str="12-Sep-2026 12:00",
        bill_date_str="12-Sep-2026",
        line_items=base_items,
        subtotal=11850.0,  # 500 too high vs 11,350 true sum
        tax_rate_pct=5.0,
        tax_amount=592.50,
        total_amount=12442.50
    )
    ground_truth["subtle_arithmetic_mismatch"] = {
        "file": "subtle_arithmetic_mismatch.pdf",
        "expected_verdict": "review",
        "required_findings": ["SUBTOTAL_SUM_MISMATCH"]
    }

    # 11. Canva Clean Amounts Bill
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "canva_clean_amounts.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="10-Sep-2026 09:00",
        discharge_str="12-Sep-2026 12:00",
        bill_date_str="12-Sep-2026",
        line_items=base_items,
        subtotal=11350.0,
        tax_rate_pct=5.0,
        tax_amount=567.50,
        total_amount=11917.50,
        producer_metadata="Canva (www.canva.com)"
    )
    ground_truth["canva_clean_amounts"] = {
        "file": "canva_clean_amounts.pdf",
        "expected_verdict": "review",  # Step 3: Suspicious producer metadata alone is REVIEW at most, never REJECT
        "expected_risk_max": 65,
        "required_findings": ["SUSPICIOUS_PRODUCER_METADATA"]
    }

    # 12. Missing Total Line Bill
    build_hospital_bill_pdf(
        out_path=EVAL_DIR / "missing_total_bill.pdf",
        hospital_name="Lotus Care Hospital",
        hospital_address="MG Road, Ernakulam, Kochi, Kerala - 682016",
        patient_name="Kavita Menon",
        patient_id="UHID-KOCH-8821",
        policy_id="POL-STAR-55219",
        diagnosis_code="E11.9",
        diagnosis_desc="Type 2 Diabetes Mellitus without complications",
        admission_str="10-Sep-2026 09:00",
        discharge_str="12-Sep-2026 12:00",
        bill_date_str="12-Sep-2026",
        line_items=base_items,
        subtotal=11350.0,
        tax_rate_pct=5.0,
        tax_amount=567.50,
        total_amount=11917.50,
        omit_totals=True
    )
    ground_truth["missing_total_bill"] = {
        "file": "missing_total_bill.pdf",
        "expected_verdict": "review",  # Step 3: missing total is extraction/incomplete, not total payable mismatch fraud
        "expected_status": "incomplete",
        "forbidden_findings": ["TOTAL_PAYABLE_MISMATCH"]
    }

    # 13. Restaurant Invoice (Not a medical bill)
    generate_restaurant_invoice(EVAL_DIR / "restaurant_invoice.pdf")
    ground_truth["restaurant_invoice"] = {
        "file": "restaurant_invoice.pdf",
        "expected_verdict": "review",
        "expected_status": "incomplete",
        "required_findings": ["NOT_A_MEDICAL_BILL"],
        "forbidden_findings": ["SUBTOTAL_SUM_MISMATCH", "TOTAL_PAYABLE_MISMATCH"]
    }

    # Save ground_truth.json
    gt_file = EVAL_DIR / "ground_truth.json"
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"\nSaved {gt_file.name} with {len(ground_truth)} evaluation entries.")


if __name__ == "__main__":
    main()
