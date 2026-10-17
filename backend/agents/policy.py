"""
Arithmetic & Policy Agent for FinShield.
Audits line item arithmetic, dates, policy caps, and sub-limits.
Calls deterministic tools for all math and policy clause grounding.
"""

from typing import List, Dict, Any, Tuple
from pydantic import BaseModel
from google.adk.agents import LlmAgent

from backend.app.schemas import Finding, Claim, Severity, AgentName, Evidence
from backend.app.config import settings
from backend.tools.registry import (
    call_tool,
    validate_arithmetic,
    detect_duplicate_line_items,
    check_room_days_vs_stay,
    validate_tax_rates,
    check_dates,
    check_policy_caps,
    check_price_benchmarks
)
from backend.tools.policy_tools import search_policy

POLICY_SYSTEM_PROMPT = """You are a claims auditor. You NEVER compute numbers yourself — always call the tools. For every
violation, cite the policy clause id and text returned by search_policy. Emit Findings in JSON only."""


DINING_MERCHANT_KEYWORDS = {
    "restaurant", "bistro", "cafe", "café", "diner", "bakery", "pizzeria",
    "dhaba", "bar & grill", "eatery", "kitchen", "catering", "dining",
    "food", "supermarket", "grocery", "sweets", "fast food"
}

DINING_ITEM_KEYWORDS = {
    "tikka", "naan", "roti", "biryani", "curry", "paneer", "pizza", "burger",
    "sandwich", "pasta", "fries", "tandoori", "thali", "rice", "dal", "masala",
    "beverage", "mocktail", "cocktail", "beer", "wine", "soda", "coke", "pepsi",
    "soup", "salad", "dessert", "ice cream", "platter", "buffet", "starters",
    "main course", "noodles", "chilli", "fried rice", "spring roll", "coffee",
    "espresso", "latte", "cappuccino", "tea", "chai", "dosa", "idli", "vada",
    "paratha", "kulcha", "lassi", "kebab", "chowmein", "manchurian"
}

CLINICAL_KEYWORDS = {
    "consultation", "doctor", "surgeon", "physician", "medicine", "pharmacy",
    "ward", "bed", "icu", "ot", "surgery", "lab", "test", "injection", "iv",
    "insulin", "hba1c", "lipid", "dressing", "anesthesia", "infusion",
    "hospitalization", "operation", "radiology", "ct", "mri", "x-ray", "usg",
    "blood", "urine", "dialysis", "biopsy", "chemotherapy", "physiotherapy",
    "nursing", "admission", "discharge", "hospital", "clinic"
}


def is_non_medical_bill(claim: Claim) -> Tuple[bool, str, List[str]]:
    """
    Document type gate:
    Detects whether a submitted invoice is a dining, restaurant, or retail commercial receipt
    rather than an institutional medical bill.
    """
    provider_name = (claim.provider.name if claim.provider else "") or getattr(claim, "hospital_name", "") or ""
    p_lower = provider_name.lower()
    has_dining_merchant = any(kw in p_lower for kw in DINING_MERCHANT_KEYWORDS)

    item_descs = [it.description.lower() for it in (claim.line_items or []) if it.description]
    dining_items = [desc for desc in item_descs if any(kw in desc for kw in DINING_ITEM_KEYWORDS)]
    clinical_items = [desc for desc in item_descs if any(kw in desc for kw in CLINICAL_KEYWORDS)]

    diag = (claim.diagnosis_code or "").strip().upper()
    has_medical_diag = bool(diag and diag not in ("NONE", "UNKNOWN", "N/A", "-") and len(diag) >= 3)

    if has_dining_merchant or (len(dining_items) > 0 and len(clinical_items) == 0):
        if len(clinical_items) == 0 and (not has_medical_diag or has_dining_merchant):
            return True, provider_name, dining_items

    return False, provider_name, []


class PolicyOutput(BaseModel):
    findings: List[Finding]


def analyze_policy_and_arithmetic(claim: Claim) -> List[Finding]:
    """
    Deterministic specialist runner for Arithmetic & Policy verification.
    Wires all tool execution through the central Tool Registry with Cloud Logging.
    """
    findings: List[Finding] = []
    doc_id = claim.documents[0].doc_id if claim.documents else "doc_main"

    # Document type gate: non-medical documents (e.g. restaurant receipts)
    is_non_medical, prov_name, matched_items = is_non_medical_bill(claim)
    if is_non_medical:
        items_str = ", ".join(matched_items[:3]) if matched_items else "dining charges"
        return [Finding(
            finding_id="F-DOC-NOT-MEDICAL",
            agent=AgentName.POLICY,
            check_id="NOT_A_MEDICAL_BILL",
            severity=Severity.HIGH,
            title="Non-Medical Document Submitted: Document is not a medical bill",
            explanation=(
                f"The submitted invoice from '{prov_name or 'Commercial Merchant'}' contains non-medical dining items "
                f"({items_str}) rather than healthcare line items. No patient, hospital, clinical services, or "
                "institutional medical diagnosis were identified."
            ),
            evidence=[Evidence(
                doc_id=doc_id,
                page=1,
                quote=f"Commercial receipt detected with items: {items_str}",
                layer="extracted"
            )],
            confidence=0.99,
            computed_chip="Document Type: NOT_A_MEDICAL_BILL",
            computed_details={
                "status": "incomplete",
                "doc_type": "NOT_A_MEDICAL_BILL",
                "provider": prov_name,
                "dining_items": matched_items
            }
        )]

    from backend.tools.docai import locate_field

    # 1. Validate Arithmetic with bounding boxes and integer paise precision
    line_items_dict = [it.model_dump() for it in claim.line_items]
    sub_evidence = locate_field(doc_id, "subtotal", claim)
    tot_evidence = locate_field(doc_id, "total_claimed", claim)

    math_result = call_tool(
        "validate_arithmetic",
        {
            "line_items": line_items_dict,
            "subtotal": claim.subtotal,
            "tax": claim.tax,
            "total": claim.total_claimed,
            "doc_id": doc_id,
            "subtotal_bbox": sub_evidence.bbox if sub_evidence else None,
            "total_bbox": tot_evidence.bbox if tot_evidence else None,
            "extraction_incomplete": bool(claim.metadata.get("extraction_incomplete", False)) if claim.metadata else False
        },
        claim_id=claim.claim_id,
        agent_name="policy"
    )
    findings.extend(math_result.get("findings", []))

    # 2. Check for Duplicate Line Items (same description, qty, rate without date distinction)
    dup_result = call_tool(
        "detect_duplicate_line_items",
        {
            "line_items": line_items_dict,
            "doc_id": doc_id
        },
        claim_id=claim.claim_id,
        agent_name="policy"
    )
    findings.extend(dup_result.get("findings", []))

    # 3. Check Room Days vs Length of Stay
    stay_result = call_tool(
        "check_room_days_vs_stay",
        {
            "admission_ts": claim.admission_ts,
            "discharge_ts": claim.discharge_ts,
            "line_items": line_items_dict,
            "doc_id": doc_id
        },
        claim_id=claim.claim_id,
        agent_name="policy"
    )
    findings.extend(stay_result.get("findings", []))

    # 4. Validate GST Tax Rates against healthcare rules
    tax_result = call_tool(
        "validate_tax_rates",
        {
            "subtotal": claim.subtotal or 0.0,
            "tax": claim.tax or 0.0,
            "line_items": line_items_dict,
            "doc_id": doc_id
        },
        claim_id=claim.claim_id,
        agent_name="policy"
    )
    findings.extend(tax_result.get("findings", []))

    # 2. Check Dates
    bill_date = (claim.metadata or {}).get("bill_date") or getattr(claim, "bill_date", None)
    document_dates = (claim.metadata or {}).get("document_dates", [])
    date_result = call_tool(
        "check_dates",
        {
            "admission_ts": claim.admission_ts,
            "discharge_ts": claim.discharge_ts,
            "bill_date": bill_date,
            "document_dates": document_dates,
            "doc_id": doc_id
        },
        claim_id=claim.claim_id,
        agent_name="policy"
    )
    findings.extend(date_result.get("findings", []))

    # 3. Check Policy Caps
    claim_dict = claim.model_dump()
    cap_result = call_tool(
        "check_policy_caps",
        {
            "policy_id": claim.policy_id,
            "claim": claim_dict,
            "doc_id": doc_id
        },
        claim_id=claim.claim_id,
        agent_name="policy"
    )
    findings.extend(cap_result.get("findings", []))

    # 4. Check Price Benchmarks (BigQuery statistical distributions)
    bench_result = call_tool(
        "check_price_benchmarks",
        {
            "claim": claim_dict,
            "doc_id": doc_id
        },
        claim_id=claim.claim_id,
        agent_name="policy"
    )
    findings.extend(bench_result.get("findings", []))

    return findings


def create_policy_agent() -> LlmAgent:
    return LlmAgent(
        name="policy_agent",
        instruction=POLICY_SYSTEM_PROMPT,
        model=settings.GEMINI_FLASH_MODEL,
        tools=[
            validate_arithmetic,
            detect_duplicate_line_items,
            check_room_days_vs_stay,
            validate_tax_rates,
            check_dates,
            check_policy_caps,
            check_price_benchmarks,
            search_policy
        ],
        output_schema=PolicyOutput,
        output_key="policy_findings"
    )
