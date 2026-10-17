"""
backend/tests/test_fix2_clean_bills_reconciliation.py

Parametrized unit tests for Fix 2: Clean Bills Reconciliation & Severity Logic.
Tests:
1. Row-level reconciliation rule:
   - Reconciles misread/defaulted quantity when amount / unit_price yields a valid integer.
   - Cross-checks with Gemini vision line items to confirm quantity and records field_sources.
   - Preserves mathematically consistent rows unchanged.
2. Severity rule for validate_arithmetic:
   - When printed totals reconcile (sum(lines) == subtotal and subtotal + tax == total),
     a quantity mismatch on a row produces low-severity LINE_QUANTITY_UNVERIFIED,
     status stays 'valid', and verdict stays APPROVE (risk < 30).
   - When printed totals do NOT reconcile (e.g. line amounts don't sum to subtotal,
     or subtotal is 40,000 too high), it produces critical fraud findings (SUBTOTAL_SUM_MISMATCH
     or LINE_ITEM_MATH_MISMATCH) and triggers REJECT >= 85.
"""

import pytest
from backend.app.schemas import Claim, LineItem, Finding, Severity, Verdict, Claimant, Provider
from backend.tools.registry import validate_arithmetic
from backend.tools.scoring import score_findings
from backend.tools.docai import _map_docai_result_to_claim, GeminiExtractedBill, GeminiExtractedLineItem


# ---------------------------------------------------------------------------
# 1. Row-Level Reconciliation Rule Unit Tests
# ---------------------------------------------------------------------------

class FakeDocAiEntity:
    def __init__(self, type_, mention_text=None, properties=None, confidence=0.98):
        self.type_ = type_
        self.mention_text = mention_text
        self.properties = properties or []
        self.confidence = confidence
        self.page_anchor = None
        self.normalized_value = None




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


class FakeDocAiDocument:
    def __init__(self, entities=None, text=""):
        self.entities = entities or []
        self.text = text


def test_row_level_reconciliation_with_gemini_vision():
    """DocAI returns qty=1.0 for a 4,400 INR row with price 2,200. Gemini confirms qty=2.0."""
    docai_props = [
        FakeDocAiProperty("line_item/description", "Ward bed charges"),
        FakeDocAiProperty("line_item/quantity", "1", normalized_text="1"),
        FakeDocAiProperty("line_item/unit_price", "2,200.00", normalized_text="2200"),
        FakeDocAiProperty("line_item/amount", "4,400.00", normalized_text="4400"),
    ]
    docai_doc = FakeDocAiDocument(
        entities=[
            FakeDocAiEntity("supplier_name", "Doon Valley Hospital"),
            FakeDocAiEntity("net_amount", "9,100.00", properties=[FakeDocAiProperty("amount", "9100.00", normalized_text="9100")]),
            FakeDocAiEntity("total_amount", "9,555.00", properties=[FakeDocAiProperty("amount", "9555.00", normalized_text="9555")]),
            FakeDocAiEntity("line_item", properties=docai_props),
        ],
        text="Doon Valley Hospital, Rajpur Road, Dehradun\nWard bed charges 2 2200 4400"
    )

    gemini_bill = GeminiExtractedBill(
        hospital_name="Doon Valley Hospital",
        city="Dehradun",
        subtotal=9100.0,
        tax=455.0,
        total_claimed=9555.0,
        line_items=[
            GeminiExtractedLineItem(description="Ward bed charges", qty=2.0, unit_price=2200.0, amount=4400.0),
        ]
    )

    claim, ents = _map_docai_result_to_claim(
        doc=docai_doc,
        pdf_bytes=b"%PDF-fake",
        filename="bill.pdf",
        claim_id="CLM-TEST-RECON-01",
        page_count=1,
        gemini_result=gemini_bill
    )

    assert len(claim.line_items) == 1
    item = claim.line_items[0]
    # Quantity must be reconciled to 2.0
    assert item.qty == 2.0
    assert item.amount == 4400.0
    assert item.unit_price == 2200.0
    assert claim.provider.city == "Dehradun"


@pytest.mark.parametrize("amount, unit_price, extracted_qty, expected_reconciled_qty", [
    (4400.0, 2200.0, 1.0, 2.0),
    (16000.0, 4000.0, 1.0, 4.0),
    (10500.0, 3500.0, 1.0, 3.0),
    (3200.0, 800.0, 1.0, 4.0),
    (1500.0, 250.0, 1.0, 6.0),
])
def test_row_level_reconciliation_math_candidate(amount, unit_price, extracted_qty, expected_reconciled_qty):
    """When amount / unit_price gives a clear integer quantity, math reconciliation corrects qty."""
    docai_props = [
        FakeDocAiProperty("line_item/description", "Medical Service Item"),
        FakeDocAiProperty("line_item/quantity", str(extracted_qty), normalized_text=str(extracted_qty)),
        FakeDocAiProperty("line_item/unit_price", str(unit_price), normalized_text=str(unit_price)),
        FakeDocAiProperty("line_item/amount", str(amount), normalized_text=str(amount)),
    ]
    docai_doc = FakeDocAiDocument(
        entities=[
            FakeDocAiEntity("supplier_name", "Test Hospital"),
            FakeDocAiEntity("net_amount", str(amount), properties=[FakeDocAiProperty("amount", str(amount))]),
            FakeDocAiEntity("total_amount", str(amount), properties=[FakeDocAiProperty("amount", str(amount))]),
            FakeDocAiEntity("line_item", properties=docai_props),
        ]
    )

    claim, ents = _map_docai_result_to_claim(
        doc=docai_doc,
        pdf_bytes=b"%PDF-fake",
        filename="bill.pdf",
        claim_id="CLM-TEST-RECON-MATH",
        page_count=1,
        gemini_result=None
    )

    assert len(claim.line_items) == 1
    assert claim.line_items[0].qty == expected_reconciled_qty
    assert claim.line_items[0].amount == expected_reconciled_qty * unit_price


# ---------------------------------------------------------------------------
# 2. Severity Rule Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("qty, unit_price, amount", [
    (1.0, 2200.0, 4400.0),  # UTI Ward bed charges misread
    (1.0, 4000.0, 16000.0), # Fracture Room rent misread
    (1.0, 3500.0, 10500.0), # Dengue ICU charges misread
])
def test_severity_rule_clean_internally_consistent_bill(qty, unit_price, amount):
    """
    When printed line amounts add up to printed subtotal and subtotal + tax == total,
    a single-row quantity x price mismatch is treated as an extraction uncertainty:
    - severity is LOW (check_id = LINE_QUANTITY_UNVERIFIED)
    - status is 'valid'
    - overall risk < 30 and verdict is APPROVE (never REJECT).
    """
    items = [
        {"description": "Hospital Room Charges", "qty": qty, "unit_price": unit_price, "amount": amount},
        {"description": "Consultation", "qty": 1, "unit_price": 1000.0, "amount": 1000.0},
    ]
    subtotal = amount + 1000.0
    tax = round(subtotal * 0.05, 2)
    total = round(subtotal + tax, 2)

    res = validate_arithmetic(items, subtotal=subtotal, tax=tax, total=total)

    # Status must be valid (not mismatch, not incomplete)
    assert res["status"] == "valid"
    assert res["valid"] is True

    # Finding must be extraction uncertainty with LOW severity
    findings = res["findings"]
    assert len(findings) == 1
    assert findings[0].check_id == "LINE_QUANTITY_UNVERIFIED"
    assert findings[0].severity == Severity.LOW
    assert "Line quantity could not be verified" in findings[0].title

    # Scoring must approve
    risk, verdict = score_findings(findings)
    assert verdict == Verdict.APPROVE
    assert risk < 30


def test_severity_rule_real_fraud_subtotal_mismatch():
    """
    When line amounts do NOT sum to subtotal (e.g. f02: subtotal 40,000 too high),
    it produces critical SUBTOTAL_SUM_MISMATCH and REJECT >= 85.
    """
    items = [
        {"description": "Ward charges", "qty": 2, "unit_price": 2000.0, "amount": 4000.0},
        {"description": "Consultation", "qty": 1, "unit_price": 1000.0, "amount": 1000.0},
    ]
    # Sum is 5,000, but printed subtotal is 45,000 (40,000 too high!)
    subtotal = 45000.0
    tax = 2250.0
    total = 47250.0

    res = validate_arithmetic(items, subtotal=subtotal, tax=tax, total=total)
    assert res["status"] == "mismatch"
    assert res["valid"] is False

    findings = res["findings"]
    sub_findings = [f for f in findings if f.check_id == "SUBTOTAL_SUM_MISMATCH"]
    assert len(sub_findings) == 1
    assert sub_findings[0].severity == Severity.CRITICAL

    risk, verdict = score_findings(findings)
    assert verdict == Verdict.REJECT
    assert risk >= 85


def test_severity_rule_line_math_mismatch_with_unreconciled_totals():
    """
    When a line item has math mismatch AND line amounts don't sum to subtotal,
    it is treated as a real fraud LINE_ITEM_MATH_MISMATCH.
    """
    items = [
        {"description": "Fabricated procedure", "qty": 1, "unit_price": 5000.0, "amount": 25000.0},
    ]
    # Claim claims 25,000 amount, but subtotal is 35,000 (discrepant on both fronts)
    subtotal = 35000.0
    tax = 1750.0
    total = 36750.0

    res = validate_arithmetic(items, subtotal=subtotal, tax=tax, total=total)
    assert res["status"] == "mismatch"
    assert any(f.check_id == "LINE_ITEM_MATH_MISMATCH" for f in res["findings"])
