"""
Generates a diverse test corpus of >= 8 unseen hospital bills:
- Different hospital templates & regions (Jaipur, Bengaluru, Pune, Lucknow, Chennai, Hyderabad)
- Multi-page bills (Narayana Hrudayalaya 2 pages)
- Different font families (Helvetica, Times-Roman)
- Raster images (PNG, scanned JPEG)
- Clean bills vs arithmetic discrepancy bill

Outputs files into data/unseen_bills/ and writes ground truth to data/demo/unseen_ground_truth.json.
"""

import io
import json
from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image, ImageFilter
import pypdfium2 as pdfium

OUTPUT_DIR = Path("data/unseen_bills")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GT_PATH = Path("data/demo/unseen_ground_truth.json")


def create_pdf(
    path: Path,
    hospital_name: str,
    hospital_address: str,
    city: str,
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
    diagnosis: str,
    items: list,
    subtotal: float,
    tax: float,
    total: float,
    multipage: bool = False,
    font_name: str = "Helvetica"
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
        "HospitalTitle",
        parent=styles["Heading1"],
        fontName=font_bold,
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0F172A")
    )
    subtitle_style = ParagraphStyle(
        "HospitalSubtitle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#475569")
    )
    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1E293B")
    )
    meta_val = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#334155")
    )

    story = []
    # Header Banner
    header_data = [
        [
            Paragraph(f"<b>{hospital_name}</b>", title_style),
            Paragraph("<b>IN-PATIENT FINAL INVOICE</b><br/><font color='#2563EB'>ORIGINAL TAX INVOICE</font>", ParagraphStyle("Right", parent=meta_label, alignment=2, fontSize=10, leading=14))
        ],
        [
            Paragraph(f"{hospital_address}, {city}<br/>GSTIN: 08AAACS1234F1Z9 | Registration: {hospital_name[:4].upper()}/2021/8892", subtitle_style),
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
            Paragraph("<b>Primary Diagnosis:</b>", meta_label), Paragraph(diagnosis, meta_val),
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
        # Split items across pages
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

        # Page 2 header continuation
        story.append(Paragraph(f"<b>{hospital_name} — Invoice Continued (Bill No: {bill_no})</b>", meta_label))
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
            ('LINEABOVE', (3, -1), (-1, -1), 1, colors.HexColor("#0F172A")),
            ('LINEBELOW', (3, -1), (-1, -1), 1.5, colors.HexColor("#0F172A")),
        ]))
        story.append(t2)
    else:
        table_rows = [[str(i+1), it[0], str(it[1]), f"{it[2]:,.2f}", f"{it[3]:,.2f}"] for i, it in enumerate(items)]
        summary_rows = [
            ["", "", "", "Subtotal:", f"₹ {subtotal:,.2f}"],
            ["", "", "", "GST (5%):", f"₹ {tax:,.2f}"],
            ["", "", "", "TOTAL PAYABLE:", f"₹ {total:,.2f}"]
        ]
        all_data = [table_header] + table_rows + summary_rows
        t = Table(all_data, colWidths=[28, 272, 45, 80, 95])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 8.5),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, len(table_rows)), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, len(table_rows)), 0.5, colors.HexColor("#E2E8F0")),
            ('FONTNAME', (0, 1), (-1, len(table_rows)), font_name),
            ('FONTSIZE', (0, 1), (-1, len(table_rows)), 8),
            ('FONTNAME', (3, len(table_rows)+1), (-1, -1), font_bold),
            ('LINEABOVE', (3, -1), (-1, -1), 1, colors.HexColor("#0F172A")),
            ('LINEBELOW', (3, -1), (-1, -1), 1.5, colors.HexColor("#0F172A")),
        ]))
        story.append(t)

    doc.build(story)


def convert_pdf_to_image(pdf_path: Path, out_path: Path, format: str = "PNG", add_noise: bool = False):
    doc = pdfium.PdfDocument(pdf_path.read_bytes())
    page = doc.get_page(0)
    pil_img = page.render(scale=150.0/72.0).to_pil()
    if add_noise:
        # Add slight scanner blur / rotation
        pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=0.4))
        pil_img = pil_img.rotate(0.3, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    pil_img.save(out_path, format=format)
    doc.close()


def generate_all():
    corpus = []

    # 1. Sunrise Clean Bill (Single-page PDF)
    b1_items = [
        ("Ward bed charges", 4.0, 3000.0, 12000.0),
        ("Physiotherapy session", 6.0, 1200.0, 7200.0),
        ("MRI lumbar spine", 1.0, 9500.0, 9500.0),
        ("Consultation", 4.0, 1000.0, 4000.0)
    ]
    p1 = OUTPUT_DIR / "bill_1_sunrise_jaipur_clean.pdf"
    create_pdf(
        p1, "Sunrise Multispeciality Hospital", "Plot 12, Tonk Road", "Jaipur",
        "SMH-2026-9041", "05-Sep-2026", "Meera Nair", "UHID-98210", "POL-STAR-8812",
        "Star Health and Allied Insurance", "Dr. Ananya Joshi", "DOC-7788",
        "02-Sep-2026 10:00 AM", "05-Sep-2026 04:00 PM", "M54.5 - Low back pain",
        b1_items, 32700.0, 1635.0, 34335.0
    )
    corpus.append({
        "id": "UNSEEN-01",
        "file": p1.name,
        "type": "clean",
        "expected": {
            "claimant_name": "Meera Nair",
            "hospital_name": "Sunrise Multispeciality Hospital",
            "city": "Jaipur",
            "doctor_id": "DOC-7788",
            "diagnosis_code": "M54.5",
            "admission_date": "02-Sep-2026",
            "discharge_date": "05-Sep-2026",
            "subtotal": 32700.0,
            "tax": 1635.0,
            "total_claimed": 34335.0,
            "line_items_count": 4,
            "expected_verdict": "APPROVE"
        }
    })

    # 2. Sunrise Padded Bill (Single-page PDF, Math error)
    p2 = OUTPUT_DIR / "bill_2_sunrise_jaipur_padded.pdf"
    create_pdf(
        p2, "Sunrise Multispeciality Hospital", "Plot 12, Tonk Road", "Jaipur",
        "SMH-2026-9042", "05-Sep-2026", "Meera Nair", "UHID-98210", "POL-STAR-8812",
        "Star Health and Allied Insurance", "Dr. Ananya Joshi", "DOC-7788",
        "02-Sep-2026 10:00 AM", "05-Sep-2026 04:00 PM", "M54.5 - Low back pain",
        b1_items, 50700.0, 2535.0, 53235.0
    )
    corpus.append({
        "id": "UNSEEN-02",
        "file": p2.name,
        "type": "padded_arithmetic",
        "expected": {
            "claimant_name": "Meera Nair",
            "hospital_name": "Sunrise Multispeciality Hospital",
            "city": "Jaipur",
            "doctor_id": "DOC-7788",
            "diagnosis_code": "M54.5",
            "admission_date": "02-Sep-2026",
            "discharge_date": "05-Sep-2026",
            "subtotal": 50700.0,
            "tax": 2535.0,
            "total_claimed": 53235.0,
            "line_items_count": 4,
            "expected_verdict": "REJECT"
        }
    })

    # 3. Narayana Hrudayalaya Multi-page Clean Bill (2 Pages PDF)
    b3_items = [
        ("Cardiac Monitoring ICU Bed", 2.0, 8500.0, 17000.0),
        ("Coronary Angiography", 1.0, 18000.0, 18000.0),
        ("Echocardiogram 2D", 1.0, 5000.0, 5000.0),
        ("Step-down Step Ward", 2.0, 4500.0, 9000.0),
        ("Cardiologist Specialist Consultation", 4.0, 1500.0, 6000.0),
        ("Medication and Consumables", 1.0, 33000.0, 33000.0)
    ]
    p3 = OUTPUT_DIR / "bill_3_narayana_bengaluru_multipage.pdf"
    create_pdf(
        p3, "Narayana Hrudayalaya Speciality Hospital", "258/A Bommasandra Industrial Area", "Bengaluru",
        "NH-2026-8812", "14-Aug-2026", "Suresh Menon", "UHID-66129", "POL-HDFC-9912",
        "HDFC ERGO General Insurance", "Dr. Ramesh Rao", "DOC-3312",
        "10-Aug-2026 08:30 AM", "14-Aug-2026 02:00 PM", "I25.1 - Atherosclerotic heart disease",
        b3_items, 88000.0, 4400.0, 92400.0, multipage=True
    )
    corpus.append({
        "id": "UNSEEN-03",
        "file": p3.name,
        "type": "clean_multipage",
        "expected": {
            "claimant_name": "Suresh Menon",
            "hospital_name": "Narayana Hrudayalaya Speciality Hospital",
            "city": "Bengaluru",
            "doctor_id": "DOC-3312",
            "diagnosis_code": "I25.1",
            "admission_date": "10-Aug-2026",
            "discharge_date": "14-Aug-2026",
            "subtotal": 88000.0,
            "tax": 4400.0,
            "total_claimed": 92400.0,
            "line_items_count": 6,
            "expected_verdict": "APPROVE"
        }
    })

    # 4. Ruby Hall Clinic Pune Clean Bill
    b4_items = [
        ("Deluxe Private Room Bed", 3.0, 5000.0, 15000.0),
        ("Laparoscopic Cholecystectomy Surgeon Fee", 1.0, 22000.0, 22000.0),
        ("Operating Theatre Equipment Charges", 1.0, 6000.0, 6000.0),
        ("Post-operative Nursing Care", 3.0, 1000.0, 3000.0),
        ("Diagnostic Ultrasound Abdomen", 1.0, 2500.0, 2500.0)
    ]
    p4 = OUTPUT_DIR / "bill_4_rubyhall_pune_clean.pdf"
    create_pdf(
        p4, "Ruby Hall Clinic, Pune", "40 Sassoon Road, Sangamvadi", "Pune",
        "RHC-2026-4410", "18-Jul-2026", "Sunita Kulkarni", "UHID-77180", "POL-ICICI-4011",
        "ICICI Lombard General Insurance", "Dr. Vivek Patil", "DOC-4491",
        "15-Jul-2026 11:00 AM", "18-Jul-2026 05:00 PM", "K80.2 - Calculus of gallbladder",
        b4_items, 48500.0, 2425.0, 50925.0
    )
    corpus.append({
        "id": "UNSEEN-04",
        "file": p4.name,
        "type": "clean",
        "expected": {
            "claimant_name": "Sunita Kulkarni",
            "hospital_name": "Ruby Hall Clinic",
            "city": "Pune",
            "doctor_id": "DOC-4491",
            "diagnosis_code": "K80.2",
            "admission_date": "15-Jul-2026",
            "discharge_date": "18-Jul-2026",
            "subtotal": 48500.0,
            "tax": 2425.0,
            "total_claimed": 50925.0,
            "line_items_count": 5,
            "expected_verdict": "APPROVE"
        }
    })

    # 5. Medanta The Medicity Lucknow Clean Bill (Times-Roman serif)
    b5_items = [
        ("Twin Sharing Ward Charges", 3.0, 3500.0, 10500.0),
        ("Pulmonology Specialist Rounds", 3.0, 1200.0, 3600.0),
        ("Chest CT Scan High Resolution", 1.0, 6500.0, 6500.0),
        ("Nebulization and Respiratory Therapy", 6.0, 900.0, 5400.0)
    ]
    p5 = OUTPUT_DIR / "bill_5_medanta_lucknow_clean.pdf"
    create_pdf(
        p5, "Medanta The Medicity Hospital, Lucknow", "Sector A, Pocket 1, Amar Shaheed Path", "Lucknow",
        "MED-2026-1192", "04-Oct-2026", "Amit Saxena", "UHID-22819", "POL-CARE-5521",
        "Care Health Insurance", "Dr. Rajiv Shukla", "DOC-5520",
        "01-Oct-2026 09:00 AM", "04-Oct-2026 03:00 PM", "J18.9 - Pneumonia unspecified",
        b5_items, 26000.0, 1300.0, 27300.0, font_name="Times-Roman"
    )
    corpus.append({
        "id": "UNSEEN-05",
        "file": p5.name,
        "type": "clean_serif",
        "expected": {
            "claimant_name": "Amit Saxena",
            "hospital_name": "Medanta The Medicity Hospital",
            "city": "Lucknow",
            "doctor_id": "DOC-5520",
            "diagnosis_code": "J18.9",
            "admission_date": "01-Oct-2026",
            "discharge_date": "04-Oct-2026",
            "subtotal": 26000.0,
            "tax": 1300.0,
            "total_claimed": 27300.0,
            "line_items_count": 4,
            "expected_verdict": "APPROVE"
        }
    })

    # 6. Apollo Specialty Hospital Chennai Clean Bill
    b6_items = [
        ("Semi Private Ward Stay", 2.0, 4000.0, 8000.0),
        ("Urology Laser Lithotripsy", 1.0, 22500.0, 22500.0),
        ("Urologist Procedure Charges", 1.0, 5000.0, 5000.0),
        ("Pre-procedure Blood Profile", 1.0, 3000.0, 3000.0)
    ]
    p6 = OUTPUT_DIR / "bill_6_apollo_chennai_clean.pdf"
    create_pdf(
        p6, "Apollo Specialty Hospital, Chennai", "21 Greams Lane, Thousand Lights", "Chennai",
        "AP-CHE-2026-559", "14-Sep-2026", "Priya Sundaram", "UHID-33918", "POL-NIVA-6622",
        "Niva Bupa Health Insurance", "Dr. S. Ranganathan", "DOC-6631",
        "12-Sep-2026 07:00 AM", "14-Sep-2026 01:00 PM", "N20.1 - Calculus of ureter",
        b6_items, 38500.0, 1925.0, 40425.0
    )
    corpus.append({
        "id": "UNSEEN-06",
        "file": p6.name,
        "type": "clean",
        "expected": {
            "claimant_name": "Priya Sundaram",
            "hospital_name": "Apollo Specialty Hospital",
            "city": "Chennai",
            "doctor_id": "DOC-6631",
            "diagnosis_code": "N20.1",
            "admission_date": "12-Sep-2026",
            "discharge_date": "14-Sep-2026",
            "subtotal": 38500.0,
            "tax": 1925.0,
            "total_claimed": 40425.0,
            "line_items_count": 4,
            "expected_verdict": "APPROVE"
        }
    })

    # 7. Fortis Escorts Jaipur Image Bill (High-res PNG image)
    b7_items = [
        ("General Medical Ward Stay", 2.0, 3500.0, 7000.0),
        ("Diabetic Ketoacidosis Management", 1.0, 8000.0, 8000.0),
        ("Endocrinologist Consultation", 3.0, 1000.0, 3000.0)
    ]
    temp_pdf7 = OUTPUT_DIR / "temp_bill_7.pdf"
    create_pdf(
        temp_pdf7, "Fortis Escorts Hospital, Jaipur", "Jawaharlal Nehru Marg, Malviya Nagar", "Jaipur",
        "FEH-2026-7719", "22-Aug-2026", "Vikram Rathore", "UHID-88190", "POL-STAR-7711",
        "Star Health and Allied Insurance", "Dr. Rohit Meena", "DOC-8819",
        "20-Aug-2026 10:00 AM", "22-Aug-2026 04:00 PM", "E11.9 - Type 2 diabetes",
        b7_items, 18000.0, 900.0, 18900.0
    )
    p7_png = OUTPUT_DIR / "bill_7_fortis_jaipur_image.png"
    convert_pdf_to_image(temp_pdf7, p7_png, format="PNG")
    temp_pdf7.unlink(missing_ok=True)
    corpus.append({
        "id": "UNSEEN-07",
        "file": p7_png.name,
        "type": "image_png",
        "expected": {
            "claimant_name": "Vikram Rathore",
            "hospital_name": "Fortis Escorts Hospital",
            "city": "Jaipur",
            "doctor_id": "DOC-8819",
            "diagnosis_code": "E11.9",
            "admission_date": "20-Aug-2026",
            "discharge_date": "22-Aug-2026",
            "subtotal": 18000.0,
            "tax": 900.0,
            "total_claimed": 18900.0,
            "line_items_count": 3,
            "expected_verdict": "APPROVE"
        }
    })

    # 8. Care Hospital Hyderabad Scanned JPEG Bill (Simulated scanned/noise)
    b8_items = [
        ("Orthopedic Private Room", 3.0, 4500.0, 13500.0),
        ("Knee Arthroscopy Surgeon Fee", 1.0, 24000.0, 24000.0),
        ("Anesthesia Specialty Care", 1.0, 6000.0, 6000.0),
        ("Post-op Physical Rehabilitation", 4.0, 1000.0, 4000.0)
    ]
    temp_pdf8 = OUTPUT_DIR / "temp_bill_8.pdf"
    create_pdf(
        temp_pdf8, "Care Hospital Banjara Hills, Hyderabad", "Road No. 1, Banjara Hills", "Hyderabad",
        "CARE-HYD-2026-904", "08-Sep-2026", "Lakshmi Rao", "UHID-55104", "POL-HDFC-8833",
        "HDFC ERGO General Insurance", "Dr. K. Srinivas", "DOC-9904",
        "05-Sep-2026 09:30 AM", "08-Sep-2026 03:00 PM", "M17.0 - Primary gonarthrosis",
        b8_items, 47500.0, 2375.0, 49875.0
    )
    p8_jpg = OUTPUT_DIR / "bill_8_care_hyderabad_scanned.jpg"
    convert_pdf_to_image(temp_pdf8, p8_jpg, format="JPEG", add_noise=True)
    temp_pdf8.unlink(missing_ok=True)
    corpus.append({
        "id": "UNSEEN-08",
        "file": p8_jpg.name,
        "type": "scanned_jpeg",
        "expected": {
            "claimant_name": "Lakshmi Rao",
            "hospital_name": "Care Hospital",
            "city": "Hyderabad",
            "doctor_id": "DOC-9904",
            "diagnosis_code": "M17.0",
            "admission_date": "05-Sep-2026",
            "discharge_date": "08-Sep-2026",
            "subtotal": 47500.0,
            "tax": 2375.0,
            "total_claimed": 49875.0,
            "line_items_count": 4,
            "expected_verdict": "APPROVE"
        }
    })

    with open(GT_PATH, "w") as f:
        json.dump(corpus, f, indent=2)
    print(f"Generated {len(corpus)} unseen test bills in {OUTPUT_DIR} and ground truth in {GT_PATH}")

if __name__ == "__main__":
    generate_all()
