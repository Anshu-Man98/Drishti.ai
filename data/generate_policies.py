"""
Generates 2 fictional policy PDFs with numbered clauses in /data/policies/synthetic/:
1. care_plus_comprehensive_policy.pdf
2. optima_shield_standard_policy.pdf
"""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

SYNTH_POLICIES_DIR = Path(__file__).resolve().parent / "policies" / "synthetic"
SYNTH_POLICIES_DIR.mkdir(parents=True, exist_ok=True)


def create_policy_pdf(filename: Path, title: str, insurer: str, policy_code: str, sections: list):
    doc = SimpleDocTemplate(
        str(filename),
        pagesize=A4,
        leftMargin=50,
        rightMargin=50,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PolTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A")
    )
    meta_style = ParagraphStyle(
        "PolMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569")
    )
    sec_heading = ParagraphStyle(
        "SecHead",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=12,
        spaceAfter=6
    )
    clause_title = ParagraphStyle(
        "ClauseTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0F172A")
    )
    clause_body = ParagraphStyle(
        "ClauseBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )

    story = []

    # Title & Header
    story.append(Paragraph(f"<b>{title}</b>", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Underwritten by:</b> {insurer} | <b>Policy Form Code:</b> {policy_code} | <b>UIN:</b> IRDAI/HLT/{policy_code}/2025", meta_style))
    story.append(Spacer(1, 12))

    for sec in sections:
        story.append(Paragraph(sec["heading"], sec_heading))
        for cl in sec["clauses"]:
            story.append(Paragraph(f"<b>{cl['id']}: {cl['title']}</b>", clause_title))
            story.append(Paragraph(cl["text"], clause_body))
            story.append(Spacer(1, 6))

    doc.build(story)
    print(f"📘 Created Policy PDF: {filename.name}")


def generate_policies():
    # 1. Care Plus Comprehensive Policy
    care_plus_sections = [
        {
            "heading": "Section 1: In-Patient Hospitalization Benefits",
            "clauses": [
                {
                    "id": "Clause 1.1",
                    "title": "Room Rent & Nursing Expenses",
                    "text": "Expenses incurred for Room, Boarding and Nursing charges in Single Private AC Room category up to ₹7,000 per day. For normal wards, up to ₹4,000 per day. Any excess over the eligible room category shall result in proportional deduction across associated medical expenses."
                },
                {
                    "id": "Clause 1.2",
                    "title": "Intensive Care Unit (ICU) Charges",
                    "text": "ICU or Intensive Cardiac Care Unit (ICCU) charges are covered up to ₹15,000 per day during the period of stay in ICU upon recommendation of the treating intensivist."
                },
                {
                    "id": "Clause 1.3",
                    "title": "Surgeon, Specialist & Anesthetist Fees",
                    "text": "Medical practitioner fees, specialist consultation charges, anesthetist, surgeon and operation theater charges are covered as per actuals subject to prevailing reasonable and customary rates in the geographical territory."
                }
            ]
        },
        {
            "heading": "Section 2: Waiting Periods and Specific Limitations",
            "clauses": [
                {
                    "id": "Clause 2.1",
                    "title": "Initial Waiting Period",
                    "text": "A waiting period of 30 days from the inception date of the policy applies for any hospitalization, except claims arising directly from an accidental injury."
                },
                {
                    "id": "Clause 2.2",
                    "title": "Specific Disease Waiting Period (24 Months)",
                    "text": "A 24-month waiting period applies for treatments of Benign Prostatic Hypertrophy, Hernia, Hydrocele, Cholecystectomy, Calculus diseases of Gallbladder and Urogenital tract, and Cataract."
                },
                {
                    "id": "Clause 2.3",
                    "title": "Robotic & Modern Treatment Sub-Limit",
                    "text": "Robotic surgeries and specialized advanced medical technologies are subject to a maximum sub-limit of ₹1,50,000 per policy year."
                }
            ]
        }
    ]
    create_policy_pdf(
        filename=SYNTH_POLICIES_DIR / "care_plus_comprehensive_policy.pdf",
        title="Care Plus Comprehensive Health Insurance Policy",
        insurer="Care Health Insurance Limited",
        policy_code="CARE-PLUS-V2",
        sections=care_plus_sections
    )

    # 2. Optima Shield Standard Policy
    optima_sections = [
        {
            "heading": "Section 1: Inpatient Hospitalization Cover",
            "clauses": [
                {
                    "id": "Clause 1.1",
                    "title": "Hospital Accommodation & Room Rent Limits",
                    "text": "For Sum Insured below ₹5,00,000, Room Rent is capped at 1% of Sum Insured per day, subject to a maximum of ₹4,000 per day. For Sum Insured of ₹5,00,000 and above, there is no capping on standard Single Private Room category."
                },
                {
                    "id": "Clause 1.2",
                    "title": "ICU Room Expense",
                    "text": "ICU charges are covered up to 2% of Sum Insured per day, with an absolute ceiling of ₹10,000 per day for policies with Sum Insured below ₹5,00,000."
                },
                {
                    "id": "Clause 1.3",
                    "title": "Day Care Treatments",
                    "text": "Day care medical treatments requiring less than 24 hours hospitalization due to technological advancement are covered, provided a minimum 2-hour formal clinical observation is documented."
                }
            ]
        },
        {
            "heading": "Section 2: Waiting Periods and Exclusions",
            "clauses": [
                {
                    "id": "Clause 2.1",
                    "title": "30-Day Inception Moratorium",
                    "text": "Any illness contracted during the first 30 days of the first policy year is excluded, unless resulting from trauma or acute external accidental bodily injury."
                },
                {
                    "id": "Clause 2.2",
                    "title": "Two-Year Specific Exclusions",
                    "text": "Treatment of Gallbladder stones (Cholecystectomy), Knee replacements, and spine surgeries are excluded until 24 consecutive months of continuous coverage."
                },
                {
                    "id": "Clause 2.3",
                    "title": "Cataract Surgical Expense Sub-Limit",
                    "text": "Cataract surgical correction is capped at ₹35,000 per eye, including intraocular lens charges."
                }
            ]
        }
    ]
    create_policy_pdf(
        filename=SYNTH_POLICIES_DIR / "optima_shield_standard_policy.pdf",
        title="Optima Shield Standard Health Insurance Policy",
        insurer="Niva Bupa Health Insurance Limited",
        policy_code="OPTIMA-SHIELD-V1",
        sections=optima_sections
    )

    # 3. Real IRDAI Arogya Sanjeevani Standard Health Policy
    REAL_POLICIES_DIR = Path(__file__).resolve().parent / "policies" / "real"
    REAL_POLICIES_DIR.mkdir(parents=True, exist_ok=True)

    arogya_sections = [
        {
            "heading": "Section 3: Coverage & Eligible In-Patient Hospitalization Expenses",
            "clauses": [
                {
                    "id": "Clause 3.1",
                    "title": "Room, Boarding and Nursing Expenses",
                    "text": "Room, Boarding and Nursing Expenses incurred during hospitalization: Up to 2% of Sum Insured subject to a maximum of ₹5,000/- per day. For normal or shared ward, up to ₹3,000/- per day. Any excess over the eligible room category shall result in proportional deduction across associated medical expenses."
                },
                {
                    "id": "Clause 3.2",
                    "title": "Intensive Care Unit (ICU) / ICCU Expenses",
                    "text": "Intensive Care Unit (ICU) / Intensive Cardiac Care Unit (ICCU) expenses: Up to 5% of Sum Insured subject to a maximum of ₹10,000/- per day during stay in ICU."
                },
                {
                    "id": "Clause 3.3",
                    "title": "Pre-Hospitalization Medical Expenses",
                    "text": "Medical expenses incurred for a period of 30 days prior to the date of hospitalization are covered, provided that such expenses are directly related to the condition for which hospitalization occurred."
                },
                {
                    "id": "Clause 3.4",
                    "title": "Post-Hospitalization Medical Expenses",
                    "text": "Medical expenses incurred for a period of 60 days following discharge from hospital are covered, provided that such expenses are directly related to the condition for which hospitalization occurred."
                }
            ]
        },
        {
            "heading": "Section 4: Waiting Periods & Specific Ailment Exclusions",
            "clauses": [
                {
                    "id": "Clause 4.1",
                    "title": "Initial Waiting Period (30 Days)",
                    "text": "Expenses related to the treatment of any illness within 30 days from the first policy commencement date shall be excluded except claims arising from an accidental injury."
                },
                {
                    "id": "Clause 4.2",
                    "title": "Specific Illness Waiting Period (24 Months)",
                    "text": "A waiting period of 24 months shall apply for treatments of Benign ENT disorders, Cholecystectomy, Calculus diseases of Gallbladder and Urogenital tract, Hernia, Hydrocele, Piles, Fistula, and Cataract."
                }
            ]
        },
        {
            "heading": "Section 5: Co-Payment & Inadmissible Deductions",
            "clauses": [
                {
                    "id": "Clause 5.1",
                    "title": "Mandatory Co-Pay",
                    "text": "A fixed co-pay of 5% is applicable on each and every admissible claim amount under this standard health insurance policy."
                }
            ]
        },
        {
            "heading": "Section 6: Specific Treatment Sub-Limits",
            "clauses": [
                {
                    "id": "Clause 6.1",
                    "title": "Cataract Surgical Expense Sub-Limit",
                    "text": "Cataract treatment is subject to a sub-limit of 25% of Sum Insured or ₹40,000/- per eye, whichever is lower, during one policy period."
                },
                {
                    "id": "Clause 6.2",
                    "title": "Modern Treatment Methods and Advanced Surgeries",
                    "text": "Modern treatments such as uterine artery embolization, balloon sinuplasty, and robotic surgeries are covered up to 50% of Sum Insured subject to a maximum of ₹2,50,000/- per policy period."
                }
            ]
        }
    ]
    create_policy_pdf(
        filename=REAL_POLICIES_DIR / "arogya_sanjeevani_irdai.pdf",
        title="Arogya Sanjeevani Policy (Standard Health Policy, IRDAI)",
        insurer="IRDAI Standard Health Product / Universal Inter-Insurer Form",
        policy_code="AROGYA-SANJEEVANI-STD",
        sections=arogya_sections
    )


if __name__ == "__main__":
    generate_policies()

