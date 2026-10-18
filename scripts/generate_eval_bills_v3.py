#!/usr/bin/env python3
"""
scripts/generate_eval_bills_v3.py

Generates independent clean evaluation test bills in data/eval_bills_v3/
using ReportLab canvas (plain text rows, no table borders, Helvetica/Times-Roman 10pt,
header row "Description / Qty / Price / Total" at x = 45 / 320 / 370 / 470),
plus 12 additional varied clean bills and 3 rotated/noisy PNG photos.
Generates ground_truth.json for calibration and verification.
"""

import io
import json
import os
import random
from pathlib import Path
from PIL import Image, ImageFilter
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "eval_bills_v3"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def draw_clean_bill_pdf(
    out_path: Path,
    hospital_name: str,
    hospital_address: str,
    bill_no: str,
    bill_date: str,
    patient_name: str,
    patient_id: str,
    policy_no: str,
    admission_str: str,
    discharge_str: str,
    diagnosis_code: str,
    diagnosis_desc: str,
    line_items: list,  # [(desc, qty, price, total)]
    subtotal: float,
    tax_rate_pct: float,
    tax_amount: float,
    total_amount: float,
    font_name: str = "Helvetica",
    col_x: tuple = (45, 320, 370, 470),
    col_headers: tuple = ("Description", "Qty", "Price", "Total"),
    subtotal_label: str = "Sub-total",
    tax_label: str = "GST @ 5%",
    total_label: str = "NET PAYABLE",
):
    """Draws a clean medical invoice using raw canvas positioning (no table borders)."""
    c = canvas.Canvas(str(out_path), pagesize=letter)
    width, height = letter

    # Header / Hospital info
    c.setFont(f"{font_name}-Bold" if f"{font_name}-Bold" in c.getAvailableFonts() else font_name, 14)
    c.drawString(45, 740, hospital_name)

    c.setFont(font_name, 9)
    c.drawString(45, 725, hospital_address)
    c.drawString(45, 712, "FINAL INPATIENT BILL & TAX INVOICE")

    # Metadata block
    c.setFont(f"{font_name}-Bold" if f"{font_name}-Bold" in c.getAvailableFonts() else font_name, 9)
    c.drawString(45, 680, f"Bill No: {bill_no}")
    c.drawString(320, 680, f"Bill Date: {bill_date}")

    c.setFont(font_name, 9)
    c.drawString(45, 665, f"Patient Name: {patient_name}")
    c.drawString(320, 665, f"UHID / IP No: {patient_id}")

    c.drawString(45, 650, f"Policy No: {policy_no}")
    c.drawString(320, 650, "Insurer: Star Health & Allied Insurance")

    c.drawString(45, 635, f"Admission: {admission_str}")
    c.drawString(320, 635, f"Discharge: {discharge_str}")

    c.drawString(45, 620, f"Diagnosis: {diagnosis_desc} ({diagnosis_code})")
    c.drawString(320, 620, "Category: Inpatient Medical Care")

    # Table Header Row (at specified x coordinates)
    x_desc, x_qty, x_price, x_total = col_x
    y = 580
    c.setFont(f"{font_name}-Bold" if f"{font_name}-Bold" in c.getAvailableFonts() else font_name, 10)
    c.drawString(x_desc, y, col_headers[0])
    c.drawString(x_qty, y, col_headers[1])
    c.drawString(x_price, y, col_headers[2])
    c.drawString(x_total, y, col_headers[3])

    # Plain text rows (no table borders, 10pt)
    c.setFont(font_name, 10)
    y -= 20
    for desc, qty, price, amt in line_items:
        c.drawString(x_desc, y, str(desc))
        # Format qty as integer if whole number
        qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.1f}"
        c.drawString(x_qty, y, qty_str)
        c.drawString(x_price, y, f"{price:,.2f}")
        c.drawString(x_total, y, f"{amt:,.2f}")
        y -= 18

    # Totals block
    y -= 10
    c.setFont(f"{font_name}-Bold" if f"{font_name}-Bold" in c.getAvailableFonts() else font_name, 10)
    c.drawString(x_desc, y, subtotal_label)
    c.drawString(x_total, y, f"{subtotal:,.2f}")

    y -= 18
    c.drawString(x_desc, y, tax_label)
    c.drawString(x_total, y, f"{tax_amount:,.2f}")

    if total_label:
        y -= 20
        c.setFont(f"{font_name}-Bold" if f"{font_name}-Bold" in c.getAvailableFonts() else font_name, 11)
        c.drawString(x_desc, y, total_label)
        c.drawString(x_total, y, f"{total_amount:,.2f}")

    # Footer note
    y -= 40
    c.setFont(font_name, 8)
    c.drawString(45, y, "This is a computer generated invoice and requires no physical signature.")
    c.drawString(45, y - 12, "All charges are verified and billed according to NABH hospital schedule of tariffs.")

    c.save()


def pdf_to_noisy_photo(pdf_path: Path, out_png_path: Path, angle: float = 2.0, blur: bool = True):
    """Renders a PDF to a realistic photo with slight tilt and image noise."""
    doc = pdfium.PdfDocument(str(pdf_path))
    page = doc.get_page(0)
    pil_image = page.render(scale=2.0).to_pil().convert("RGB")
    doc.close()

    # Rotate with white background
    rotated = pil_image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(250, 250, 248))

    if blur:
        rotated = rotated.filter(ImageFilter.GaussianBlur(radius=0.4))

    rotated.save(out_png_path, "PNG", quality=92)


def main():
    bills_meta = {}

    # 1. UTI bill (Dehradun, N39.0, Helvetica 10pt)
    uti_items = [
        ("Ward bed charges", 2, 2200.0, 4400.0),
        ("Consultation", 2, 500.0, 1000.0),
        ("Urine culture", 1, 700.0, 700.0),
        ("IV antibiotics", 6, 300.0, 1800.0),
        ("Ultrasound abdomen", 1, 1200.0, 1200.0),
    ]
    subtotal_1 = 9100.0
    tax_1 = 455.0
    tot_1 = 9555.0
    p1 = OUT_DIR / "bill_01_uti_dehradun.pdf"
    draw_clean_bill_pdf(
        out_path=p1,
        hospital_name="Doon Valley Hospital",
        hospital_address="Rajpur Road, Dehradun, Uttarakhand - 248001",
        bill_no="INV-DDN-2026-104",
        bill_date="17-Oct-2026",
        patient_name="Amit Sharma",
        patient_id="UHID-DDN-4012",
        policy_no="POL-STAR-88123",
        admission_str="15-Oct-2026 10:00",
        discharge_str="17-Oct-2026 11:00",
        diagnosis_code="N39.0",
        diagnosis_desc="Urinary tract infection, site not specified",
        line_items=uti_items,
        subtotal=subtotal_1,
        tax_rate_pct=5.0,
        tax_amount=tax_1,
        total_amount=tot_1,
        font_name="Helvetica",
        col_x=(45, 320, 370, 470),
        col_headers=("Description", "Qty", "Price", "Total"),
        subtotal_label="Sub-total",
        tax_label="GST @ 5%",
        total_label="NET PAYABLE",
    )
    bills_meta["bill_01_uti_dehradun.pdf"] = {
        "claim_id": "CLM-V3-01-UTI",
        "hospital_name": "Doon Valley Hospital",
        "city": "Dehradun",
        "diagnosis_code": "N39.0",
        "patient_name": "Amit Sharma",
        "subtotal": subtotal_1,
        "tax": tax_1,
        "total_amount": tot_1,
        "first_row_qty": 2,
        "first_row_price": 2200.0,
        "first_row_amount": 4400.0,
        "expected_verdict": "APPROVE",
        "expected_max_risk": 28,
        "is_photo": False
    }

    # 1b. UTI bill with NO printed total line (eval pair: with and without total)
    p1b = OUT_DIR / "bill_01b_uti_no_total.pdf"
    draw_clean_bill_pdf(
        out_path=p1b,
        hospital_name="Doon Valley Hospital",
        hospital_address="Rajpur Road, Dehradun, Uttarakhand - 248001",
        bill_no="INV-DDN-2026-104B",
        bill_date="17-Oct-2026",
        patient_name="Amit Sharma",
        patient_id="UHID-DDN-4012",
        policy_no="POL-STAR-88123",
        admission_str="15-Oct-2026 10:00",
        discharge_str="17-Oct-2026 11:00",
        diagnosis_code="N39.0",
        diagnosis_desc="Urinary tract infection, site not specified",
        line_items=uti_items,
        subtotal=subtotal_1,
        tax_rate_pct=5.0,
        tax_amount=tax_1,
        total_amount=tot_1,
        font_name="Helvetica",
        col_x=(45, 320, 370, 470),
        col_headers=("Description", "Qty", "Price", "Total"),
        subtotal_label="Sub-total",
        tax_label="GST @ 5%",
        total_label=None,  # NO printed total
    )
    bills_meta["bill_01b_uti_no_total.pdf"] = {
        "claim_id": "CLM-V3-01B-UTI-NO-TOTAL",
        "hospital_name": "Doon Valley Hospital",
        "city": "Dehradun",
        "diagnosis_code": "N39.0",
        "patient_name": "Amit Sharma",
        "subtotal": subtotal_1,
        "tax": tax_1,
        "total_amount": tot_1,
        "first_row_qty": 2,
        "first_row_price": 2200.0,
        "first_row_amount": 4400.0,
        "has_printed_total": False,
        "expected_verdict": "REVIEW",
        "expected_status": "incomplete",
        "expected_min_risk": 45,
        "is_photo": False
    }

    # 2. Fracture bill (Times-Roman, Indore, S82.8)
    frac_items = [
        ("Room rent", 4, 4000.0, 16000.0),
        ("OT charges", 1, 22000.0, 22000.0),
        ("Orthopaedic surgeon fee", 1, 20000.0, 20000.0),
        ("Implant (plate and screws)", 1, 28000.0, 28000.0),
        ("Anaesthesia fee", 1, 5000.0, 5000.0),
        ("Physiotherapy", 4, 800.0, 3200.0),
        ("Pharmacy", 1, 4500.0, 4500.0),
    ]
    subtotal_2 = 98700.0
    tax_2 = 4935.0
    tot_2 = 103635.0
    p2 = OUT_DIR / "bill_02_fracture_indore.pdf"
    draw_clean_bill_pdf(
        out_path=p2,
        hospital_name="Indore Ortho & Trauma Centre",
        hospital_address="AB Road, Indore, Madhya Pradesh - 452001",
        bill_no="INV-IND-2026-809",
        bill_date="12-Oct-2026",
        patient_name="Priya Verma",
        patient_id="UHID-IND-8091",
        policy_no="POL-HDFC-99321",
        admission_str="08-Oct-2026 09:00",
        discharge_str="12-Oct-2026 14:00",
        diagnosis_code="S82.8",
        diagnosis_desc="Fracture of other parts of lower leg",
        line_items=frac_items,
        subtotal=subtotal_2,
        tax_rate_pct=5.0,
        tax_amount=tax_2,
        total_amount=tot_2,
        font_name="Times-Roman",
        col_x=(45, 320, 370, 470),
        col_headers=("Description", "Qty", "Price", "Total"),
        subtotal_label="Sub-total",
        tax_label="GST @ 5%",
        total_label="NET PAYABLE",
    )
    bills_meta["bill_02_fracture_indore.pdf"] = {
        "claim_id": "CLM-V3-02-FRACTURE",
        "hospital_name": "Indore Ortho & Trauma Centre",
        "city": "Indore",
        "diagnosis_code": "S82.8",
        "patient_name": "Priya Verma",
        "subtotal": subtotal_2,
        "tax": tax_2,
        "total_amount": tot_2,
        "first_row_qty": 4,
        "first_row_price": 4000.0,
        "first_row_amount": 16000.0,
        "expected_verdict": "APPROVE",
        "expected_max_risk": 28,
        "is_photo": False
    }

    # 12 Additional Clean Bills with varied fonts, cities, diagnoses, column layouts
    additional_configs = [
        # 3
        {
            "filename": "bill_03_dengue_jaipur.pdf",
            "claim_id": "CLM-V3-03-DENGUE",
            "hospital": "SMS Lifeline Hospital",
            "address": "JLN Marg, Jaipur, Rajasthan - 302004",
            "city": "Jaipur",
            "bill_no": "INV-JAI-9011",
            "bill_date": "16-Oct-2026",
            "patient": "Ramesh Choudhary",
            "uhid": "UHID-JPR-201",
            "policy": "POL-STAR-7711",
            "adm": "13-Oct-2026 11:00",
            "dis": "16-Oct-2026 12:00",
            "diag_code": "A90",
            "diag_desc": "Dengue fever",
            "font": "Helvetica",
            "col_x": (45, 310, 365, 465),
            "headers": ("Item Description", "Qty", "Rate", "Amount"),
            "items": [
                ("ICU Bed Charges", 3, 3500.0, 10500.0),
                ("Platelet transfusion", 2, 2500.0, 5000.0),
                ("CBC blood tests", 4, 400.0, 1600.0),
                ("IV fluids & electrolytes", 6, 250.0, 1500.0),
                ("Nursing care", 3, 800.0, 2400.0),
            ],
            "subtotal": 21000.0,
            "tax": 1050.0,
            "total": 22050.0,
        },
        # 4
        {
            "filename": "bill_04_appendicitis_kochi.pdf",
            "claim_id": "CLM-V3-04-APPENDICITIS",
            "hospital": "Aster Medcity Care",
            "address": "Cheranalloor, Kochi, Kerala - 682027",
            "city": "Kochi",
            "bill_no": "INV-KOC-4412",
            "bill_date": "14-Oct-2026",
            "patient": "George Thomas",
            "uhid": "UHID-KOC-552",
            "policy": "POL-CARE-3321",
            "adm": "11-Oct-2026 08:00",
            "dis": "14-Oct-2026 11:00",
            "diag_code": "K35.8",
            "diag_desc": "Acute appendicitis, other",
            "font": "Times-Roman",
            "col_x": (50, 330, 380, 475),
            "headers": ("Particulars", "Days/Qty", "Price", "Net"),
            "items": [
                ("Semi-Private Room", 3, 2800.0, 8400.0),
                ("Laparoscopic Appendectomy", 1, 28000.0, 28000.0),
                ("Surgeon fee", 1, 15000.0, 15000.0),
                ("OT & Anaesthesia", 1, 12000.0, 12000.0),
                ("Pharmacy items", 1, 4200.0, 4200.0),
            ],
            "subtotal": 67600.0,
            "tax": 3380.0,
            "total": 70980.0,
        },
        # 5
        {
            "filename": "bill_05_gastro_lucknow.pdf",
            "claim_id": "CLM-V3-05-GASTRO",
            "hospital": "Sahara Grace Hospital",
            "address": "Gomti Nagar, Lucknow, Uttar Pradesh - 226010",
            "city": "Lucknow",
            "bill_no": "INV-LKO-7721",
            "bill_date": "15-Oct-2026",
            "patient": "Sunita Mishra",
            "uhid": "UHID-LKO-310",
            "policy": "POL-NIVA-6621",
            "adm": "13-Oct-2026 14:00",
            "dis": "15-Oct-2026 16:00",
            "diag_code": "A09",
            "diag_desc": "Infectious gastroenteritis",
            "font": "Helvetica",
            "col_x": (45, 320, 370, 470),
            "headers": ("Description", "Qty", "Price", "Total"),
            "items": [
                ("Deluxe Room", 2, 3000.0, 6000.0),
                ("Consultant visit", 3, 600.0, 1800.0),
                ("Stool routine & culture", 1, 500.0, 500.0),
                ("IV electrolytes", 8, 200.0, 1600.0),
                ("Nursing charges", 2, 700.0, 1400.0),
            ],
            "subtotal": 11300.0,
            "tax": 565.0,
            "total": 11865.0,
        },
        # 6
        {
            "filename": "bill_06_cataract_chennai.pdf",
            "claim_id": "CLM-V3-06-CATARACT",
            "hospital": "Sankara Eye Care",
            "address": "Pammal Main Road, Chennai, Tamil Nadu - 600075",
            "city": "Chennai",
            "bill_no": "INV-CHE-1190",
            "bill_date": "14-Oct-2026",
            "patient": "K. Venkatesh",
            "uhid": "UHID-CHE-441",
            "policy": "POL-STAR-4491",
            "adm": "13-Oct-2026 07:30",
            "dis": "14-Oct-2026 18:00",
            "diag_code": "H25.0",
            "diag_desc": "Senile cataract, cortical",
            "font": "Times-Roman",
            "col_x": (40, 315, 375, 475),
            "headers": ("Service Description", "Qty", "Unit Price", "Line Total"),
            "items": [
                ("Daycare Bed Charges", 2, 1500.0, 3000.0),
                ("Phacoemulsification with Foldable IOL", 1, 25000.0, 25000.0),
                ("Ophthalmic surgeon fee", 1, 10000.0, 10000.0),
                ("Pre-op diagnostics", 1, 2200.0, 2200.0),
                ("Post-op drops & supplies", 2, 450.0, 900.0),
            ],
            "subtotal": 41100.0,
            "tax": 2055.0,
            "total": 43155.0,
        },
        # 7
        {
            "filename": "bill_07_pneumonia_mumbai.pdf",
            "claim_id": "CLM-V3-07-PNEUMONIA",
            "hospital": "Lilavati Care Centre",
            "address": "Bandra Reclamation, Mumbai, Maharashtra - 400050",
            "city": "Mumbai",
            "bill_no": "INV-BOM-8831",
            "bill_date": "16-Oct-2026",
            "patient": "Farhan Merchant",
            "uhid": "UHID-BOM-902",
            "policy": "POL-ICICI-1102",
            "adm": "12-Oct-2026 09:30",
            "dis": "16-Oct-2026 14:00",
            "diag_code": "J18.9",
            "diag_desc": "Pneumonia, unspecified organism",
            "font": "Helvetica",
            "col_x": (45, 320, 370, 470),
            "headers": ("Description", "Qty", "Price", "Total"),
            "items": [
                ("High Dependency Unit", 4, 4500.0, 18000.0),
                ("Chest X-Ray digital", 2, 800.0, 1600.0),
                ("Pulmonologist visits", 4, 1200.0, 4800.0),
                ("IV Antibiotics", 10, 400.0, 4000.0),
                ("Nebulization sessions", 8, 250.0, 2000.0),
            ],
            "subtotal": 30400.0,
            "tax": 1520.0,
            "total": 31920.0,
        },
        # 8
        {
            "filename": "bill_08_gallstones_hyderabad.pdf",
            "claim_id": "CLM-V3-08-GALLSTONES",
            "hospital": "Yashoda Multispecialty",
            "address": "Raj Bhavan Road, Somajiguda, Hyderabad, Telangana - 500082",
            "city": "Hyderabad",
            "bill_no": "INV-HYD-5501",
            "bill_date": "15-Oct-2026",
            "patient": "Srinivas Rao",
            "uhid": "UHID-HYD-612",
            "policy": "POL-STAR-3301",
            "adm": "12-Oct-2026 10:00",
            "dis": "15-Oct-2026 12:00",
            "diag_code": "K80.2",
            "diag_desc": "Calculus of gallbladder without cholecystitis",
            "font": "Times-Roman",
            "col_x": (45, 325, 375, 470),
            "headers": ("Procedure / Service", "Qty", "Rate", "Amount"),
            "items": [
                ("Twin Sharing Room", 3, 3200.0, 9600.0),
                ("Laparoscopic Cholecystectomy", 1, 35000.0, 35000.0),
                ("Chief Surgeon Fee", 1, 18000.0, 18000.0),
                ("Anaesthesia services", 1, 6000.0, 6000.0),
                ("OT consumables & staples", 1, 5500.0, 5500.0),
            ],
            "subtotal": 74100.0,
            "tax": 3705.0,
            "total": 77805.0,
        },
        # 9
        {
            "filename": "bill_09_maternity_bengaluru.pdf",
            "claim_id": "CLM-V3-09-MATERNITY",
            "hospital": "Cloudnine Motherhood Hospital",
            "address": "Old Airport Road, Bengaluru, Karnataka - 560017",
            "city": "Bengaluru",
            "bill_no": "INV-BLR-3329",
            "bill_date": "16-Oct-2026",
            "patient": "Ananya Hegde",
            "uhid": "UHID-BLR-819",
            "policy": "POL-HDFC-5519",
            "adm": "13-Oct-2026 06:00",
            "dis": "16-Oct-2026 11:30",
            "diag_code": "O80",
            "diag_desc": "Single spontaneous delivery",
            "font": "Helvetica",
            "col_x": (45, 320, 370, 470),
            "headers": ("Description", "Qty", "Price", "Total"),
            "items": [
                ("Maternity Ward Suite", 3, 5000.0, 15000.0),
                ("Normal delivery charges", 1, 25000.0, 25000.0),
                ("Obstetric delivery procedure charge", 1, 15000.0, 15000.0),
                ("Paediatrician checkup", 2, 1500.0, 3000.0),
                ("Neonatal nursing care", 3, 1000.0, 3000.0),
            ],
            "subtotal": 61000.0,
            "tax": 3050.0,
            "total": 64050.0,
        },
        # 10
        {
            "filename": "bill_10_hernia_pune.pdf",
            "claim_id": "CLM-V3-10-HERNIA",
            "hospital": "Ruby Hall Medical Clinic",
            "address": "Sassoon Road, Pune, Maharashtra - 411001",
            "city": "Pune",
            "bill_no": "INV-PUN-6612",
            "bill_date": "15-Oct-2026",
            "patient": "Sanjay Kulkarni",
            "uhid": "UHID-PUN-711",
            "policy": "POL-CARE-9021",
            "adm": "13-Oct-2026 08:30",
            "dis": "15-Oct-2026 12:00",
            "diag_code": "K40.9",
            "diag_desc": "Unilateral inguinal hernia",
            "font": "Times-Roman",
            "col_x": (45, 320, 370, 470),
            "headers": ("Description", "Qty", "Price", "Total"),
            "items": [
                ("Standard Inpatient Room", 2, 3500.0, 7000.0),
                ("Hernioplasty with Mesh", 1, 30000.0, 30000.0),
                ("Surgeon operating fee", 1, 16000.0, 16000.0),
                ("OT theatre charges", 1, 10000.0, 10000.0),
                ("PAC & pre-op tests", 1, 1200.0, 1200.0),
            ],
            "subtotal": 64200.0,
            "tax": 3210.0,
            "total": 67410.0,
        },
        # 11
        {
            "filename": "bill_11_diabetes_kolkata.pdf",
            "claim_id": "CLM-V3-11-DIABETES",
            "hospital": "Apollo Gleneagles Hospital",
            "address": "Canal Circular Road, Kolkata, West Bengal - 700054",
            "city": "Kolkata",
            "bill_no": "INV-CCU-9921",
            "bill_date": "16-Oct-2026",
            "patient": "Subhashish Bose",
            "uhid": "UHID-CCU-102",
            "policy": "POL-STAR-1192",
            "adm": "13-Oct-2026 11:00",
            "dis": "16-Oct-2026 15:00",
            "diag_code": "E11.0",
            "diag_desc": "Type 2 diabetes with hyperosmolarity",
            "font": "Helvetica",
            "col_x": (45, 315, 365, 465),
            "headers": ("Medical Service", "Qty", "Unit Rate", "Total INR"),
            "items": [
                ("Step Down Care Unit", 3, 4000.0, 12000.0),
                ("Diabetologist consultation", 3, 1000.0, 3000.0),
                ("Blood glucose profiling", 12, 150.0, 1800.0),
                ("Insulin infusion management", 6, 350.0, 2100.0),
                ("Comprehensive renal panel", 2, 900.0, 1800.0),
            ],
            "subtotal": 20700.0,
            "tax": 1035.0,
            "total": 21735.0,
        },
        # 12
        {
            "filename": "bill_12_pyrexia_delhi.pdf",
            "claim_id": "CLM-V3-12-PYREXIA",
            "hospital": "Max Super Specialty Hospital",
            "address": "Saket, New Delhi, Delhi - 110017",
            "city": "New Delhi",
            "bill_no": "INV-DEL-8802",
            "bill_date": "16-Oct-2026",
            "patient": "Rajiv Khanna",
            "uhid": "UHID-DEL-551",
            "policy": "POL-NIVA-4401",
            "adm": "14-Oct-2026 12:00",
            "dis": "16-Oct-2026 14:00",
            "diag_code": "R50.9",
            "diag_desc": "Fever, unspecified",
            "font": "Times-Roman",
            "col_x": (45, 320, 370, 470),
            "headers": ("Description", "Qty", "Price", "Total"),
            "items": [
                ("General Ward bed", 2, 2000.0, 4000.0),
                ("Physician consultations", 2, 800.0, 1600.0),
                ("Fever panel diagnostic package", 1, 2500.0, 2500.0),
                ("IV antipyretics", 4, 300.0, 1200.0),
                ("Nursing charges", 2, 600.0, 1200.0),
            ],
            "subtotal": 10500.0,
            "tax": 525.0,
            "total": 11025.0,
        },
        # 13
        {
            "filename": "bill_13_sciatica_ahmedabad.pdf",
            "claim_id": "CLM-V3-13-SCIATICA",
            "hospital": "Zydus Hospital",
            "address": "SG Highway, Thaltej, Ahmedabad, Gujarat - 380054",
            "city": "Ahmedabad",
            "bill_no": "INV-AHM-4421",
            "bill_date": "16-Oct-2026",
            "patient": "Dipak Patel",
            "uhid": "UHID-AHM-991",
            "policy": "POL-HDFC-7712",
            "adm": "13-Oct-2026 10:00",
            "dis": "16-Oct-2026 11:30",
            "diag_code": "M51.2",
            "diag_desc": "Other specified intervertebral disc displacement",
            "font": "Helvetica",
            "col_x": (45, 320, 370, 470),
            "headers": ("Description", "Qty", "Price", "Total"),
            "items": [
                ("Special Inpatient Room", 3, 3800.0, 11400.0),
                ("Spine specialist review", 3, 1200.0, 3600.0),
                ("MRI Lumbar Spine with contrast", 1, 7500.0, 7500.0),
                ("Neuro-physiotherapy", 6, 600.0, 3600.0),
                ("Analgesic infusions & meds", 1, 2800.0, 2800.0),
            ],
            "subtotal": 28900.0,
            "tax": 1445.0,
            "total": 30345.0,
        },
        # 14
        {
            "filename": "bill_14_cad_mumbai.pdf",
            "claim_id": "CLM-V3-14-CAD",
            "hospital": "Fortis Hospital Mulund",
            "address": "Mulund Goregaon Link Road, Mumbai, Maharashtra - 400078",
            "city": "Mumbai",
            "bill_no": "INV-BOM-7710",
            "bill_date": "16-Oct-2026",
            "patient": "Kiran Shah",
            "uhid": "UHID-BOM-330",
            "policy": "POL-STAR-9921",
            "adm": "14-Oct-2026 08:00",
            "dis": "16-Oct-2026 13:00",
            "diag_code": "I25.1",
            "diag_desc": "Atherosclerotic heart disease",
            "font": "Times-Roman",
            "col_x": (45, 320, 370, 470),
            "headers": ("Description", "Qty", "Price", "Total"),
            "items": [
                ("Cardiac Care Unit (CCU)", 2, 6000.0, 12000.0),
                ("Coronary Angiography procedure", 1, 18000.0, 18000.0),
                ("Interventional Cardiologist Review", 1, 2000.0, 2000.0),
                ("Catheterization sheath & consumables", 1, 5500.0, 5500.0),
                ("Cardiac blood panel", 1, 3500.0, 3500.0),
            ],
            "subtotal": 41000.0,
            "tax": 2050.0,
            "total": 43050.0,
        },
    ]

    for cfg in additional_configs:
        out_f = OUT_DIR / cfg["filename"]
        draw_clean_bill_pdf(
            out_path=out_f,
            hospital_name=cfg["hospital"],
            hospital_address=cfg["address"],
            bill_no=cfg["bill_no"],
            bill_date=cfg["bill_date"],
            patient_name=cfg["patient"],
            patient_id=cfg["uhid"],
            policy_no=cfg["policy"],
            admission_str=cfg["adm"],
            discharge_str=cfg["dis"],
            diagnosis_code=cfg["diag_code"],
            diagnosis_desc=cfg["diag_desc"],
            line_items=cfg["items"],
            subtotal=cfg["subtotal"],
            tax_rate_pct=5.0,
            tax_amount=cfg["tax"],
            total_amount=cfg["total"],
            font_name=cfg["font"],
            col_x=cfg["col_x"],
            col_headers=cfg["headers"],
            subtotal_label="Sub-total",
            tax_label="GST @ 5%",
            total_label="NET PAYABLE",
        )
        f_row = cfg["items"][0]
        bills_meta[cfg["filename"]] = {
            "claim_id": cfg["claim_id"],
            "hospital_name": cfg["hospital"],
            "city": cfg["city"],
            "diagnosis_code": cfg["diag_code"],
            "patient_name": cfg["patient"],
            "subtotal": cfg["subtotal"],
            "tax": cfg["tax"],
            "total_amount": cfg["total"],
            "first_row_qty": f_row[1],
            "first_row_price": f_row[2],
            "first_row_amount": f_row[3],
            "expected_verdict": "APPROVE",
            "expected_max_risk": 28,
            "is_photo": False
        }

    # 3 Rotated/Noisy PNG Photos:
    # 15: Photo of bill 01 (UTI Dehradun)
    p15 = OUT_DIR / "bill_15_photo_uti.png"
    pdf_to_noisy_photo(p1, p15, angle=2.0, blur=True)
    bills_meta["bill_15_photo_uti.png"] = {
        "claim_id": "CLM-V3-15-PHOTO-UTI",
        "hospital_name": "Doon Valley Hospital",
        "city": "Dehradun",
        "diagnosis_code": "N39.0",
        "patient_name": "Amit Sharma",
        "subtotal": subtotal_1,
        "tax": tax_1,
        "total_amount": tot_1,
        "first_row_qty": 2,
        "first_row_price": 2200.0,
        "first_row_amount": 4400.0,
        "expected_verdict": "APPROVE",
        "expected_max_risk": 28,
        "is_photo": True
    }

    # 16: Photo of bill 02 (Fracture Indore)
    p16 = OUT_DIR / "bill_16_photo_fracture.png"
    pdf_to_noisy_photo(p2, p16, angle=-1.5, blur=True)
    bills_meta["bill_16_photo_fracture.png"] = {
        "claim_id": "CLM-V3-16-PHOTO-FRAC",
        "hospital_name": "Indore Ortho & Trauma Centre",
        "city": "Indore",
        "diagnosis_code": "S82.8",
        "patient_name": "Priya Verma",
        "subtotal": subtotal_2,
        "tax": tax_2,
        "total_amount": tot_2,
        "first_row_qty": 4,
        "first_row_price": 4000.0,
        "first_row_amount": 16000.0,
        "expected_verdict": "APPROVE",
        "expected_max_risk": 28,
        "is_photo": True
    }

    # 17: Photo of bill 07 (Pneumonia Mumbai)
    p17 = OUT_DIR / "bill_17_photo_pneumonia.png"
    pdf_to_noisy_photo(OUT_DIR / "bill_07_pneumonia_mumbai.pdf", p17, angle=1.8, blur=True)
    bills_meta["bill_17_photo_pneumonia.png"] = {
        "claim_id": "CLM-V3-17-PHOTO-PNEUMONIA",
        "hospital_name": "Lilavati Care Centre",
        "city": "Mumbai",
        "diagnosis_code": "J18.9",
        "patient_name": "Farhan Merchant",
        "subtotal": 30400.0,
        "tax": 1520.0,
        "total_amount": 31920.0,
        "first_row_qty": 4,
        "first_row_price": 4500.0,
        "first_row_amount": 18000.0,
        "expected_verdict": "APPROVE",
        "expected_max_risk": 28,
        "is_photo": True
    }

    gt_path = OUT_DIR / "ground_truth.json"
    with open(gt_path, "w") as f:
        json.dump(bills_meta, f, indent=2)

    print(f"Generated {len(bills_meta)} test bills in {OUT_DIR}")
    print(f"Wrote ground truth to {gt_path}")


if __name__ == "__main__":
    main()
