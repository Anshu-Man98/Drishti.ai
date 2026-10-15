"""
Deterministic arithmetic and date validation tools.
LLMs never compute sums, multiplications, or date durations.
All math runs here with exact precision and tolerance rules.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.app.schemas import Finding, Evidence, AgentName, Severity


def validate_arithmetic(
    line_items: List[Dict[str, Any]],
    subtotal: float,
    tax: float,
    total: float,
    doc_id: str = "doc_main",
    page: int = 1,
    subtotal_bbox: Optional[List[float]] = None,
    total_bbox: Optional[List[float]] = None
) -> List[Finding]:
    """
    Validates line item products, line item sums, and total amount.
    Tolerance: +-1.0 INR for rounding.
    Carries bounding boxes in evidence for visual audit citations.
    """
    findings: List[Finding] = []
    TOLERANCE = 1.0

    # 1. Validate qty * unit_price == amount for each line item
    calculated_subtotal = 0.0
    for idx, item in enumerate(line_items):
        desc = item.get("description", f"Line item {idx+1}")
        qty = float(item.get("qty", 1.0))
        unit_price = float(item.get("unit_price", 0.0))
        amount = float(item.get("amount", 0.0))
        item_bbox = item.get("bbox")

        expected_amount = round(qty * unit_price, 2)
        diff = abs(expected_amount - amount)

        if diff > TOLERANCE:
            findings.append(Finding(
                finding_id=f"F-MATH-ITEM-{idx+1}",
                agent=AgentName.POLICY,
                check_id="LINE_ITEM_MATH_MISMATCH",
                severity=Severity.HIGH,
                title=f"Calculation mismatch in line item: {desc}",
                explanation=(
                    f"Line item '{desc}' claims ₹{amount:,.2f}, but {qty} × ₹{unit_price:,.2f} "
                    f"equals ₹{expected_amount:,.2f} (Discrepancy: ₹{diff:,.2f})."
                ),
                evidence=[Evidence(
                    doc_id=doc_id,
                    page=item.get("page", page),
                    bbox=item_bbox,
                    quote=f"{desc}: claimed {amount}, expected {expected_amount}"
                )],
                confidence=1.0
            ))

        calculated_subtotal += amount

    # 2. Validate sum(line_items) == subtotal
    subtotal_diff = abs(calculated_subtotal - subtotal)
    if subtotal_diff > TOLERANCE:
        findings.append(Finding(
            finding_id="F-MATH-SUBTOTAL",
            agent=AgentName.POLICY,
            check_id="SUBTOTAL_SUM_MISMATCH",
            severity=Severity.HIGH,
            title="Subtotal does not match sum of itemized charges",
            explanation=(
                f"The sum of all line items is ₹{calculated_subtotal:,.2f}, but the printed subtotal is "
                f"₹{subtotal:,.2f} (Discrepancy: ₹{subtotal_diff:,.2f})."
            ),
            evidence=[Evidence(
                doc_id=doc_id,
                page=page,
                bbox=subtotal_bbox,
                quote=f"Calculated sum: {calculated_subtotal}, Printed subtotal: {subtotal}"
            )],
            confidence=1.0
        ))

    # 3. Validate subtotal + tax == total
    expected_total = round(subtotal + tax, 2)
    total_diff = abs(expected_total - total)
    if total_diff > TOLERANCE:
        findings.append(Finding(
            finding_id="F-MATH-TOTAL",
            agent=AgentName.POLICY,
            check_id="TOTAL_PAYABLE_MISMATCH",
            severity=Severity.CRITICAL,
            title="Total claimed does not match subtotal plus tax",
            explanation=(
                f"The invoice claims total payable of ₹{total:,.2f}, but subtotal (₹{subtotal:,.2f}) + "
                f"tax (₹{tax:,.2f}) equals ₹{expected_total:,.2f} (Unjustified inflation: ₹{total_diff:,.2f})."
            ),
            evidence=[Evidence(
                doc_id=doc_id,
                page=page,
                bbox=total_bbox,
                quote=f"Claimed total: {total}, Expected total: {expected_total}"
            )],
            confidence=1.0
        ))

    return findings


def check_dates(
    admission_ts: datetime,
    discharge_ts: datetime,
    document_dates: Optional[List[Dict[str, Any]]] = None,
    doc_id: str = "doc_main"
) -> List[Finding]:
    """
    Validates chronological sequence of admission, discharge, and bill dates.
    """
    findings: List[Finding] = []

    # 1. Admission must precede discharge
    if admission_ts > discharge_ts:
        findings.append(Finding(
            finding_id="F-DATE-REVERSED",
            agent=AgentName.POLICY,
            check_id="REVERSED_HOSPITALIZATION_DATES",
            severity=Severity.CRITICAL,
            title="Admission date occurs after discharge date",
            explanation=(
                f"Admission timestamp ({admission_ts.isoformat()}) is later than discharge "
                f"timestamp ({discharge_ts.isoformat()}). This represents a temporal impossibility."
            ),
            evidence=[Evidence(doc_id=doc_id, page=1, quote=f"Admission: {admission_ts}, Discharge: {discharge_ts}")],
            confidence=1.0
        ))

    # 2. Check document dates against stay
    if document_dates:
        for idx, doc_entry in enumerate(document_dates):
            doc_date = doc_entry.get("date")
            doc_label = doc_entry.get("label", f"Document {idx+1}")
            if doc_date and isinstance(doc_date, datetime):
                if doc_date < admission_ts - (discharge_ts - admission_ts) * 0.5:
                    findings.append(Finding(
                        finding_id=f"F-DATE-EARLY-{idx+1}",
                        agent=AgentName.POLICY,
                        check_id="BILL_DATED_BEFORE_ADMISSION",
                        severity=Severity.MEDIUM,
                        title=f"{doc_label} dated prior to admission",
                        explanation=f"{doc_label} is dated {doc_date.strftime('%d-%b-%Y')}, which is before the hospital admission date.",
                        evidence=[Evidence(doc_id=doc_id, page=1, quote=f"Date: {doc_date}")],
                        confidence=0.9
                    ))

    return findings
