"""
backend/tests/test_fix1_printed_total.py

Unit and integration tests for QA Fix 1:
A bill with no printed total must not be approved.
1. Bill with no printed total: derives total, field_sources.total_claimed = "derived",
   dossier status is incomplete, verdict floor REVIEW (risk >= 45),
   EXTRACTION_INCOMPLETE finding grounded in computed registry.
2. Bill with printed total (clean): field_sources.total_claimed from docai/gemini/layout,
   APPROVE (< 30), status complete, no EXTRACTION_INCOMPLETE.
3. Bill with wrong printed total: TOTAL_PAYABLE_MISMATCH (fraud check), REJECT verdict.
4. Field provenance audit: absent/inferred fields marked "derived".
"""

import pytest
from backend.app.schemas import Claim, LineItem, Claimant, Provider, Verdict, Severity
from backend.tools.docai import (
    _map_docai_result_to_claim,
    GeminiExtractedBill,
    GeminiExtractedLineItem
)
from backend.agents.policy import analyze_policy_and_arithmetic
from backend.tools.scoring import score_findings, is_incomplete_analysis_condition
from backend.tools.registry import validate_arithmetic


class FakeDocAiProperty:
    def __init__(self, type_, mention_text, normalized_text=None, confidence=0.98):
        self.type_ = type_
        self.mention_text = mention_text
        self.confidence = confidence
        if normalized_text:
            class NormVal:
                text = normalized_text
            self.normalized_value = NormVal()
        else:
            self.normalized_value = None


class FakeDocAiEntity:
    def __init__(self, type_, mention_text=None, properties=None, confidence=0.98):
        self.type_ = type_
        self.mention_text = mention_text
        self.properties = properties or []
        self.confidence = confidence
        self.page_anchor = None
        self.normalized_value = None


class FakeDocAiDocument:
    def __init__(self, entities=None, text=""):
        self.entities = entities or []
        self.text = text


def _create_uti_docai_doc(with_total_text: str = None, total_entity_val: str = None):
    """
    Creates a fake DocAI document for the UTI bill with the exact items:
    Ward bed charges 2 x 2200 = 4400, Consultation 2 x 500 = 1000,
    Urine culture 1 x 700 = 700, IV antibiotics 6 x 300 = 1800,
    Ultrasound abdomen 1 x 1200 = 1200.
    Sub-total: 9,100, GST @ 5%: 455.
    """
    line_props = [
        [
            FakeDocAiProperty("line_item/description", "Ward bed charges"),
            FakeDocAiProperty("line_item/quantity", "2"),
            FakeDocAiProperty("line_item/unit_price", "2200"),
            FakeDocAiProperty("line_item/amount", "4400"),
        ],
        [
            FakeDocAiProperty("line_item/description", "Consultation"),
            FakeDocAiProperty("line_item/quantity", "2"),
            FakeDocAiProperty("line_item/unit_price", "500"),
            FakeDocAiProperty("line_item/amount", "1000"),
        ],
        [
            FakeDocAiProperty("line_item/description", "Urine culture"),
            FakeDocAiProperty("line_item/quantity", "1"),
            FakeDocAiProperty("line_item/unit_price", "700"),
            FakeDocAiProperty("line_item/amount", "700"),
        ],
        [
            FakeDocAiProperty("line_item/description", "IV antibiotics"),
            FakeDocAiProperty("line_item/quantity", "6"),
            FakeDocAiProperty("line_item/unit_price", "300"),
            FakeDocAiProperty("line_item/amount", "1800"),
        ],
        [
            FakeDocAiProperty("line_item/description", "Ultrasound abdomen"),
            FakeDocAiProperty("line_item/quantity", "1"),
            FakeDocAiProperty("line_item/unit_price", "1200"),
            FakeDocAiProperty("line_item/amount", "1200"),
        ]
    ]

    entities = [
        FakeDocAiEntity("supplier_name", "Doon Valley Hospital"),
        FakeDocAiEntity("receiver_name", "Amit Sharma"),
        FakeDocAiEntity("invoice_date", "17-Oct-2026"),
        FakeDocAiEntity("net_amount", "9,100.00", properties=[FakeDocAiProperty("amount", "9100.00")]),
        FakeDocAiEntity("total_tax_amount", "455.00", properties=[FakeDocAiProperty("amount", "455.00")]),
    ]
    for lp in line_props:
        entities.append(FakeDocAiEntity("line_item", properties=lp))

    if total_entity_val:
        entities.append(FakeDocAiEntity("total_amount", total_entity_val, properties=[FakeDocAiProperty("amount", total_entity_val)]))

    body_text = (
        "Doon Valley Hospital, Rajpur Road, Dehradun\n"
        "Patient: Amit Sharma\n"
        "Bill No: INV-DDN-2026-104\n"
        "Admission: 15-Oct-2026 10:00  Discharge: 17-Oct-2026 11:00\n"
        "Diagnosis: N39.0 Urinary tract infection\n"
        "Description Qty Price Total\n"
        "Ward bed charges 2 2200 4400\n"
        "Consultation 2 500 1000\n"
        "Urine culture 1 700 700\n"
        "IV antibiotics 6 300 1800\n"
        "Ultrasound abdomen 1 1200 1200\n"
        "Sub-total 9,100\n"
        "GST @ 5% 455\n"
    )
    if with_total_text:
        body_text += f"{with_total_text}\n"

    return FakeDocAiDocument(entities=entities, text=body_text)


def test_fix1_bill_without_printed_total():
    """
    Test 1: UTI bill with no printed total line.
    - total_claimed is derived from subtotal (9100) + tax (455) = 9555
    - field_sources['total_claimed'] == 'derived'
    - claim.metadata['has_printed_total'] is False
    - EXTRACTION_INCOMPLETE finding emitted with grounded text
    - status == 'incomplete'
    - verdict == REVIEW, risk >= 45
    """
    doc = _create_uti_docai_doc(with_total_text=None, total_entity_val=None)

    claim, ents = _map_docai_result_to_claim(
        doc=doc,
        pdf_bytes=b"%PDF-fake",
        filename="bill_no_total.pdf",
        claim_id="CLM-TEST-FIX1-NO-TOTAL",
        page_count=1,
        gemini_result=None
    )

    # 1. Extraction checks
    assert claim.total_claimed == 9555.0
    assert claim.subtotal == 9100.0
    assert claim.tax == 455.0
    assert claim.field_sources.get("total_claimed") == "derived"
    assert claim.metadata.get("has_printed_total") is False
    assert claim.metadata.get("extraction_incomplete") is True

    # 2. Audit pipeline findings
    findings = analyze_policy_and_arithmetic(claim)
    inc_findings = [f for f in findings if f.check_id == "EXTRACTION_INCOMPLETE"]
    assert len(inc_findings) >= 1
    missing_total_f = [f for f in inc_findings if "No printed total found" in f.explanation]
    assert len(missing_total_f) == 1
    assert "derived total ₹9,555.00 from subtotal + tax" in missing_total_f[0].explanation
    assert missing_total_f[0].severity in (Severity.INFO, Severity.LOW)

    # 3. No false fraud finding for arithmetic mismatch
    fraud_mismatch = [f for f in findings if f.check_id == "TOTAL_PAYABLE_MISMATCH"]
    assert len(fraud_mismatch) == 0

    # 4. Scoring: must enforce verdict floor REVIEW and risk >= 45
    risk_score, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.REVIEW
    assert risk_score >= 45

    # 5. Status: is incomplete
    is_inc = any(is_incomplete_analysis_condition(f) for f in findings)
    assert is_inc is True


def test_fix1_bill_with_printed_total():
    """
    Test 2: UTI bill with printed NET PAYABLE 9,555.
    - field_sources['total_claimed'] from docai/gemini
    - status == 'complete'
    - verdict == APPROVE (< 30)
    - no EXTRACTION_INCOMPLETE finding
    """
    doc = _create_uti_docai_doc(with_total_text="NET PAYABLE 9,555", total_entity_val="9555.00")

    claim, ents = _map_docai_result_to_claim(
        doc=doc,
        pdf_bytes=b"%PDF-fake",
        filename="bill_with_total.pdf",
        claim_id="CLM-TEST-FIX1-WITH-TOTAL",
        page_count=1,
        gemini_result=None
    )

    assert claim.total_claimed == 9555.0
    assert claim.field_sources.get("total_claimed") != "derived"
    assert claim.metadata.get("has_printed_total") is not False

    findings = analyze_policy_and_arithmetic(claim)
    inc_findings = [f for f in findings if f.check_id == "EXTRACTION_INCOMPLETE"]
    assert len(inc_findings) == 0

    risk_score, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.APPROVE
    assert risk_score < 30

    is_inc = any(is_incomplete_analysis_condition(f) for f in findings)
    assert is_inc is False


def test_fix1_bill_with_wrong_printed_total():
    """
    Test 3: UTI bill with wrong printed total NET PAYABLE 12,000.
    Subtotal 9100 + Tax 455 != 12000.
    - TOTAL_PAYABLE_MISMATCH finding emitted with HIGH or CRITICAL severity
    - verdict == REJECT
    - status == 'complete' (it was printed, just fraudulent/erroneous)
    """
    doc = _create_uti_docai_doc(with_total_text="NET PAYABLE 12,000", total_entity_val="12000.00")

    claim, ents = _map_docai_result_to_claim(
        doc=doc,
        pdf_bytes=b"%PDF-fake",
        filename="bill_wrong_total.pdf",
        claim_id="CLM-TEST-FIX1-WRONG-TOTAL",
        page_count=1,
        gemini_result=None
    )

    assert claim.total_claimed == 12000.0
    assert claim.field_sources.get("total_claimed") != "derived"

    findings = analyze_policy_and_arithmetic(claim)
    mismatch_findings = [f for f in findings if f.check_id == "TOTAL_PAYABLE_MISMATCH"]
    assert len(mismatch_findings) == 1
    assert mismatch_findings[0].severity in (Severity.HIGH, Severity.CRITICAL)

    risk_score, verdict = score_findings(findings, ml_probability=0.05)
    assert verdict == Verdict.REJECT
    assert risk_score >= 70


def test_fix1_field_provenance_audit():
    """
    Test 4: Provenance map test.
    Checks that missing or inferred fields are flagged as "derived" in field_sources.
    """
    doc = FakeDocAiDocument(
        entities=[
            FakeDocAiEntity("supplier_name", "Apollo Hospital"),
            # Missing receiver_name, invoice_date, net_amount, tax, total
        ],
        text="Apollo Hospital\nConsultation 1000\nSubtotal 1000"
    )

    claim, ents = _map_docai_result_to_claim(
        doc=doc,
        pdf_bytes=b"%PDF-fake",
        filename="sparse_bill.pdf",
        claim_id="CLM-TEST-PROVENANCE",
        page_count=1,
        gemini_result=None
    )

    # City inferred from hospital name / defaulted
    assert claim.field_sources.get("city") == "derived"
    assert claim.provider.city == "Unknown"

    # Insurer inferred from default/policy
    assert claim.field_sources.get("insurer_id") == "derived"

    # Total claimed derived
    assert claim.field_sources.get("total_claimed") == "derived"

    # Test with claimant name present: when not in BQ warehouse, bank account is derived / hashed
    from unittest.mock import patch
    from backend.tools.bq import bq_warehouse

    doc2 = FakeDocAiDocument(
        entities=[
            FakeDocAiEntity("receiver_name", "Unregistered Patient XYZ"),
        ],
        text="Patient: Unregistered Patient XYZ"
    )
    with patch.object(bq_warehouse, "lookup_claimant_bank_hash", return_value=None):
        claim2, _ = _map_docai_result_to_claim(
            doc=doc2,
            pdf_bytes=b"%PDF-fake",
            filename="bill2.pdf",
            claim_id="CLM-TEST-PROV-2",
            page_count=1,
            gemini_result=None
        )
        assert claim2.field_sources.get("claimant_bank_account") == "derived"
