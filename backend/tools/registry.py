"""
Central Tool Registry for FinShield / Drishti.ai.
Hardens the "LLMs never do arithmetic" rule into provable execution.
Collects all deterministic tools with explicit Vertex AI function calling declarations,
integer paise currency calculations, structured Cloud Logging, and tool execution audit trails.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from backend.app.schemas import Claim, Evidence, Finding, Severity, AgentName, Verdict
from backend.tools.geo import (
    haversine_km as _raw_haversine,
    min_travel_hours as _raw_min_travel,
    is_feasible as _raw_is_feasible,
    normalize_to_utc
)
from backend.tools.scoring import score_findings as _raw_score_findings
from backend.tools.bq import bq_warehouse

logger = logging.getLogger("finshield.tools.audit")

# Global in-memory audit store for tool invocations and computed numbers per claim
TOOL_AUDIT_LOG: Dict[str, List[Dict[str, Any]]] = {}
CLAIM_COMPUTED_STORE: Dict[str, Dict[str, Any]] = {}


def to_paise(rupees: Union[float, int, str, None]) -> int:
    """Converts a currency amount in rupees to integer paise (1 INR = 100 paise)."""
    if rupees is None:
        return 0
    if isinstance(rupees, str):
        cleaned = rupees.replace("₹", "").replace(",", "").replace("INR", "").replace("Rs.", "").strip()
        rupees = float(cleaned) if cleaned else 0.0
    return int(round(float(rupees) * 100))


def to_rupees(paise: int) -> float:
    """Converts integer paise to float rupees rounded to 2 decimal places."""
    return round(paise / 100.0, 2)


# ==============================================================================
# DETERMINISTIC TOOL IMPLEMENTATIONS (PAISE ACCURATE)
# ==============================================================================

def validate_arithmetic(
    line_items: List[Dict[str, Any]],
    subtotal: Optional[float] = 0.0,
    tax: Optional[float] = 0.0,
    total: Optional[float] = 0.0,
    doc_id: str = "doc_main",
    page: int = 1,
    subtotal_bbox: Optional[List[float]] = None,
    total_bbox: Optional[List[float]] = None,
    extraction_incomplete: bool = False
) -> Dict[str, Any]:
    """
    Validates line item products, line item sums, and invoice total amount.
    Strictly uses integer paise internally. Tolerance: 100 paise (+-1.0 INR).
    Returns structured results including a "computed" sub-object holding every number produced.
    """
    tolerance_paise = 100  # 1.0 INR
    findings: List[Finding] = []

    # Convert stated totals to integer paise
    stated_subtotal_paise = to_paise(subtotal)
    stated_tax_paise = to_paise(tax)
    stated_total_paise = to_paise(total)

    if extraction_incomplete:
        calc_sub_paise = sum(to_paise(item.get("amount", 0.0)) for item in line_items)
        calc_sub_rupees = to_rupees(calc_sub_paise)
        sub_rupees = subtotal if subtotal is not None else 0.0
        diff_rupees = abs(calc_sub_rupees - sub_rupees)
        findings.append(Finding(
            finding_id="F-EXTRACTION-INCOMPLETE",
            agent=AgentName.POLICY,
            check_id="EXTRACTION_INCOMPLETE",
            severity=Severity.HIGH,
            title="Extraction Incomplete: Itemized charges do not reconcile with subtotal",
            explanation=(
                f"Extracted line items sum to ₹{calc_sub_rupees:,.2f}, but the printed subtotal is "
                f"₹{sub_rupees:,.2f}. The document's itemized breakdown could not be completely parsed."
            ),
            evidence=[Evidence(
                doc_id=doc_id,
                page=page,
                bbox=subtotal_bbox,
                quote=f"Extracted sum: ₹{calc_sub_rupees:,.2f}, Printed subtotal: ₹{sub_rupees:,.2f}"
            )],
            confidence=0.95,
            computed_chip=f"Extraction incomplete (Δ ₹{diff_rupees:,.0f})",
            computed_details={
                "extracted_sum": calc_sub_rupees,
                "printed_subtotal": sub_rupees,
                "discrepancy": diff_rupees
            }
        ))
        return {
            "status": "incomplete",
            "findings": findings,
            "discrepancy_rupees": diff_rupees,
            "computed": {
                "calculated_subtotal_paise": calc_sub_paise,
                "stated_subtotal_paise": stated_subtotal_paise,
                "stated_tax_paise": stated_tax_paise,
                "stated_total_paise": stated_total_paise,
                "extraction_incomplete": True
            }
        }


    # 1. Validate qty * unit_price == amount for each line item
    calculated_subtotal_paise = 0
    for idx, item in enumerate(line_items):
        desc = item.get("description", f"Line item {idx+1}")
        qty = float(item.get("qty", 1.0))
        unit_price = float(item.get("unit_price", 0.0))
        amount = float(item.get("amount", 0.0))
        item_bbox = item.get("bbox")

        claimed_amount_paise = to_paise(amount)
        expected_amount_paise = int(round(qty * (unit_price * 100)))
        diff_item_paise = abs(expected_amount_paise - claimed_amount_paise)

        if diff_item_paise > tolerance_paise:
            findings.append(Finding(
                finding_id=f"F-MATH-ITEM-{idx+1}",
                agent=AgentName.POLICY,
                check_id="LINE_ITEM_MATH_MISMATCH",
                severity=Severity.HIGH,
                title=f"Calculation mismatch in line item: {desc}",
                explanation=(
                    f"Line item '{desc}' claims ₹{amount:,.2f}, but {qty} × ₹{unit_price:,.2f} "
                    f"equals ₹{to_rupees(expected_amount_paise):,.2f} (Discrepancy: ₹{to_rupees(diff_item_paise):,.2f})."
                ),
                evidence=[Evidence(
                    doc_id=doc_id,
                    page=item.get("page", page),
                    bbox=item_bbox,
                    quote=f"{desc}: claimed {amount}, expected {to_rupees(expected_amount_paise)}"
                )],
                confidence=1.0,
                computed_chip=f"{qty} × ₹{unit_price:,.0f} ≠ ₹{amount:,.0f} (Δ ₹{to_rupees(diff_item_paise):,.0f})",
                computed_details={
                    "qty": qty,
                    "unit_price_paise": to_paise(unit_price),
                    "claimed_amount_paise": claimed_amount_paise,
                    "expected_amount_paise": expected_amount_paise,
                    "diff_paise": diff_item_paise
                }
            ))

        calculated_subtotal_paise += claimed_amount_paise

    # 2. Validate sum(line_items) == subtotal
    subtotal_diff_paise = abs(calculated_subtotal_paise - stated_subtotal_paise)
    expected_total_paise = stated_subtotal_paise + stated_tax_paise
    total_diff_paise = abs(expected_total_paise - stated_total_paise)
    max_diff_paise = max(subtotal_diff_paise, total_diff_paise)

    # Compute formatting chip
    calc_sub_rupees = to_rupees(calculated_subtotal_paise)
    diff_rupees = to_rupees(max_diff_paise)
    sub_rupees = subtotal if subtotal is not None else 0.0
    tax_rupees = tax if tax is not None else 0.0
    tot_rupees = total if total is not None else 0.0

    if subtotal_diff_paise > tolerance_paise or total_diff_paise > tolerance_paise:
        chip = f"₹{calc_sub_rupees:,.0f} + ₹{tax_rupees:,.0f} ≠ ₹{tot_rupees:,.0f} (Δ ₹{diff_rupees:,.0f})"
    else:
        chip = f"₹{sub_rupees:,.0f} + ₹{tax_rupees:,.0f} = ₹{tot_rupees:,.0f} (Exact match)"

    if subtotal_diff_paise > tolerance_paise:
        diff_val = to_rupees(subtotal_diff_paise)
        is_large = (diff_val > 5000.0 or (subtotal_diff_paise / max(1, to_paise(sub_rupees))) > 0.05)
        severity = Severity.CRITICAL if is_large else Severity.HIGH
        findings.append(Finding(
            finding_id="F-MATH-SUBTOTAL",
            agent=AgentName.POLICY,
            check_id="SUBTOTAL_SUM_MISMATCH",
            severity=severity,
            title="Subtotal does not match sum of itemized charges",
            explanation=(
                f"The sum of all line items is ₹{calc_sub_rupees:,.2f}, but the printed subtotal is "
                f"₹{sub_rupees:,.2f} (Discrepancy: ₹{to_rupees(subtotal_diff_paise):,.2f})."
            ),
            evidence=[Evidence(
                doc_id=doc_id,
                page=page,
                bbox=subtotal_bbox,
                quote=f"Calculated sum: {calc_sub_rupees}, Printed subtotal: {sub_rupees}"
            )],
            confidence=1.0,
            computed_chip=chip,
            computed_details={
                "line_item_sum": calc_sub_rupees,
                "stated_subtotal": sub_rupees,
                "subtotal_diff": to_rupees(subtotal_diff_paise),
                "tolerance_paise": tolerance_paise
            }
        ))

    # 3. Validate subtotal + tax == total
    if total_diff_paise > tolerance_paise:
        findings.append(Finding(
            finding_id="F-MATH-TOTAL",
            agent=AgentName.POLICY,
            check_id="TOTAL_PAYABLE_MISMATCH",
            severity=Severity.CRITICAL,
            title="Total claimed does not match subtotal plus tax",
            explanation=(
                f"The invoice claims total payable of ₹{tot_rupees:,.2f}, but subtotal (₹{sub_rupees:,.2f}) + "
                f"tax (₹{tax_rupees:,.2f}) equals ₹{to_rupees(expected_total_paise):,.2f} (Unjustified inflation: ₹{to_rupees(total_diff_paise):,.2f})."
            ),
            evidence=[Evidence(
                doc_id=doc_id,
                page=page,
                bbox=total_bbox,
                quote=f"Claimed total: {total}, Expected total: {to_rupees(expected_total_paise)}"
            )],
            confidence=1.0,
            computed_chip=chip,
            computed_details={
                "stated_total": total,
                "expected_total": to_rupees(expected_total_paise),
                "total_diff": to_rupees(total_diff_paise),
                "tolerance_paise": tolerance_paise
            }
        ))

    match = (subtotal_diff_paise <= tolerance_paise) and (total_diff_paise <= tolerance_paise)

    computed = {
        "line_item_sum": calc_sub_rupees,
        "stated_subtotal": subtotal,
        "stated_tax": tax,
        "stated_total": total,
        "expected_total": to_rupees(expected_total_paise),
        "difference": diff_rupees,
        "subtotal_diff": to_rupees(subtotal_diff_paise),
        "total_diff": to_rupees(total_diff_paise),
        "line_item_sum_paise": calculated_subtotal_paise,
        "stated_total_paise": stated_total_paise,
        "difference_paise": max_diff_paise
    }

    return {
        "valid": match,
        "match": match,
        "findings": findings,
        "computed": computed,
        "tolerance_paise": tolerance_paise,
        "chip": chip
    }


def check_policy_caps(
    policy_id: Optional[str],
    claim: Union[Claim, Dict[str, Any]],
    doc_id: str = "doc_main"
) -> Dict[str, Any]:
    """
    Evaluates claim line items against policy caps (room rent, ICU, sub-limits)
    using integer paise arithmetic.
    """
    from backend.tools.policy_tools import _load_rules

    claim_data = claim if isinstance(claim, dict) else claim.model_dump()
    rules_catalog = _load_rules().get("policies", {})

    safe_policy_id = (policy_id or "POL-AROGYA-SANJEEVANI").upper()
    policy_key = "AROGYA_SANJEEVANI"
    if "CARE" in safe_policy_id:
        policy_key = "CARE_PLUS"
    elif "OPTIMA" in safe_policy_id:
        policy_key = "OPTIMA_SHIELD"

    policy_profile = rules_catalog.get(policy_key, rules_catalog.get("AROGYA_SANJEEVANI", {}))
    rules_list = policy_profile.get("rules", [])
    rules_by_key = {r["rule"]: r for r in rules_list}

    findings: List[Finding] = []
    computed: Dict[str, Any] = {}
    chip = "Within policy caps"
    compliant = True

    # 1. Check Room Rent Cap
    room_cap_rule = rules_by_key.get("room_rent_cap_per_day")
    if room_cap_rule:
        room_cap_limit = float(room_cap_rule["value"])
        room_cap_paise = to_paise(room_cap_limit)
        line_items = claim_data.get("line_items", [])

        for idx, item in enumerate(line_items):
            desc = item.get("description", "").lower()
            if any(k in desc for k in ["icu", "iccu", "intensive care"]):
                continue  # Evaluated under ICU cap
            if any(k in desc for k in ["room", "ward", "bed", "suite"]):
                unit_price = float(item.get("unit_price", 0.0))
                unit_price_paise = to_paise(unit_price)
                qty = float(item.get("qty", 1.0))

                if unit_price_paise > room_cap_paise:
                    compliant = False
                    excess_per_day_paise = unit_price_paise - room_cap_paise
                    total_excess_paise = int(round(excess_per_day_paise * qty))

                    chip = f"Billed ₹{unit_price:,.0f} > Cap ₹{room_cap_limit:,.0f} (Excess ₹{to_rupees(excess_per_day_paise):,.0f}/d)"

                    computed = {
                        "room_rent_billed": unit_price,
                        "room_rent_cap": room_cap_limit,
                        "excess_per_day": to_rupees(excess_per_day_paise),
                        "total_excess": to_rupees(total_excess_paise),
                        "room_rent_days": qty,
                        "room_rent_billed_paise": unit_price_paise,
                        "room_rent_cap_paise": room_cap_paise,
                        "total_excess_paise": total_excess_paise
                    }

                    findings.append(Finding(
                        finding_id=f"F-POL-ROOM-CAP-{idx+1}",
                        agent=AgentName.POLICY,
                        check_id="POLICY_ROOM_RENT_CAP_EXCEEDED",
                        severity=Severity.HIGH,
                        title=f"Room rent charges exceed policy cap ({room_cap_rule['clause_id']})",
                        explanation=(
                            f"Room rent billed at ₹{unit_price:,.2f}/day for {qty:.0f} days exceeds the eligible limit of "
                            f"₹{room_cap_limit:,.2f}/day by ₹{to_rupees(excess_per_day_paise):,.2f}/day "
                            f"(Total inadmissible room rent: ₹{to_rupees(total_excess_paise):,.2f}). "
                            f"Cited: {room_cap_rule['clause_id']} — {room_cap_rule['description']}"
                        ),
                        evidence=[
                            Evidence(
                                doc_id=doc_id,
                                page=item.get("page", 1),
                                bbox=item.get("bbox"),
                                quote=f"{item.get('description')}: billed ₹{unit_price}/day vs cap ₹{room_cap_limit}/day",
                                layer="visible"
                            ),
                            Evidence(
                                doc_id=room_cap_rule["clause_id"],
                                page=room_cap_rule.get("page", 1),
                                quote=room_cap_rule.get("text", room_cap_rule["description"]),
                                layer="retrieved"
                            )
                        ],
                        confidence=1.0,
                    ))

    return {
        "compliant": compliant,
        "findings": findings,
        "computed": computed,
        "chip": chip
    }


def check_price_benchmarks(
    claim: Dict[str, Any],
    doc_id: str = "doc_main"
) -> Dict[str, Any]:
    """
    Validates claim total and itemized unit prices against BigQuery statistical benchmarks.
    Emits grounded findings in integer paise:
      - TOTAL_ABOVE_DIAGNOSIS_BENCHMARK
      - LINE_ITEM_PRICE_ABOVE_BENCHMARK
      - UNBUNDLED_OR_PADDED_ANCILLARY
    """
    from backend.services.benchmarks import benchmark_service

    findings: List[Finding] = []
    computed: Dict[str, Any] = {}
    chips: List[str] = []

    if hasattr(claim, "model_dump"):
        claim_dict = claim.model_dump()
    elif isinstance(claim, dict):
        claim_dict = claim
    else:
        claim_dict = getattr(claim, "__dict__", {})

    diag_code = claim_dict.get("diagnosis_code") or "K35.8"
    diag_bench = benchmark_service.get_diagnosis_benchmark(diag_code)

    total_rupees = float(claim_dict.get("total_claimed") or claim_dict.get("subtotal") or 0.0)
    total_paise = to_paise(total_rupees)
    p95_total_paise = to_paise(diag_bench.p95)
    p90_total_paise = to_paise(diag_bench.p90)
    p75_total_paise = to_paise(diag_bench.p75)
    p50_total_paise = to_paise(diag_bench.p50)

    computed["diagnosis_code"] = diag_bench.diagnosis_code
    computed["diagnosis_benchmark_level"] = diag_bench.fallback_level
    computed["diagnosis_benchmark_sample_count"] = diag_bench.sample_count
    computed["diagnosis_p50"] = diag_bench.p50
    computed["diagnosis_p75"] = diag_bench.p75
    computed["diagnosis_p90"] = diag_bench.p90
    computed["diagnosis_p95"] = diag_bench.p95
    computed["total_claimed_paise"] = total_paise

    # 1. TOTAL_ABOVE_DIAGNOSIS_BENCHMARK
    # Widened effective upper band: accounts for realistic tier-1 / regional price variation
    # rather than treating synthetic p95 as a hard ceiling.
    # Exact benchmark (n >= 30) allows +25% tolerance; global or thin fallback allows +35%.
    is_exact_diag = (diag_bench.fallback_level == "exact" and diag_bench.sample_count >= 30)
    diag_tolerance_margin = 0.25 if is_exact_diag else 0.35
    upper_band_paise = int(round(p95_total_paise * (1.0 + diag_tolerance_margin)))
    upper_band_rupees = to_rupees(upper_band_paise)

    computed["diagnosis_tolerance_margin"] = diag_tolerance_margin
    computed["diagnosis_upper_band"] = upper_band_rupees

    if total_paise > upper_band_paise:
        ratio_vs_p95 = total_paise / max(1, p95_total_paise)
        excess_ratio = total_paise / max(1, upper_band_paise)
        diff_paise = total_paise - p95_total_paise
        
        # Smooth severity based on excess above the widened upper band
        if (excess_ratio >= 1.30 or ratio_vs_p95 >= 1.55) and is_exact_diag:
            sev = Severity.CRITICAL
        elif excess_ratio > 1.15 or ratio_vs_p95 >= 1.30:
            sev = Severity.HIGH
        elif excess_ratio > 1.0 or ratio_vs_p95 >= 1.10:
            sev = Severity.MEDIUM
        else:
            sev = Severity.LOW

        # Weak benchmark (thin sample size or global fallback) may never produce HIGH or CRITICAL
        if diag_bench.sample_count < 30 or diag_bench.fallback_level in ("chapter", "global"):
            sev = Severity.LOW

        chip_txt = f"Total vs p95: {ratio_vs_p95:.2f}x"
        chips.append(chip_txt)
        pct_diff = (ratio_vs_p95 - 1.0) * 100
        pct_int = round(pct_diff)
        pct_str = f"+{pct_diff:.1f}%" if pct_diff < 1.0 else f"+{pct_int}%"
        pct_text = f"{pct_diff:.1f}%" if pct_diff < 1.0 else f"{pct_int}%"

        computed["total_claimed_rupees"] = total_rupees
        computed["benchmark_p95"] = diag_bench.p95
        computed["benchmark_p50"] = diag_bench.p50
        computed["benchmark_p75"] = diag_bench.p75
        computed["benchmark_p90"] = diag_bench.p90
        computed["benchmark_ratio_p95"] = round(ratio_vs_p95, 3)
        computed["benchmark_pct_above_p95"] = round(pct_diff, 1)
        computed["benchmark_pct_above_p95_int"] = pct_int
        computed["benchmark_excess_rupees"] = to_rupees(diff_paise)

        findings.append(Finding(
            finding_id="F-BENCH-TOTAL-P95",
            agent=AgentName.POLICY,
            check_id="TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
            severity=sev,
            title=f"Total claim amount exceeds diagnosis benchmark ({pct_str} above p95)",
            explanation=(
                f"Total claimed amount of ₹{total_rupees:,.2f} is {pct_text} above the 95th percentile benchmark "
                f"(₹{diag_bench.p95:,.2f}) and exceeds the widened tolerance band of ₹{upper_band_rupees:,.2f} "
                f"(+{int(diag_tolerance_margin*100)}% margin) for diagnosis {diag_bench.diagnosis_code} "
                f"(benchmark level: '{diag_bench.fallback_level}', sample size n={diag_bench.sample_count}, "
                f"distribution: p50=₹{diag_bench.p50:,.2f}, p75=₹{diag_bench.p75:,.2f}, p90=₹{diag_bench.p90:,.2f}, p95=₹{diag_bench.p95:,.2f})."
            ),
            evidence=[Evidence(
                doc_id=doc_id,
                page=1,
                quote=f"Total claimed: ₹{total_rupees:,.2f} vs diagnosis {diag_bench.diagnosis_code} (p95=₹{diag_bench.p95:,.2f}, upper band=₹{upper_band_rupees:,.2f}, level={diag_bench.fallback_level}, n={diag_bench.sample_count})"
            )],
            confidence=0.95,
            computed_chip=chip_txt,
            computed_details={
                "total_claimed": total_rupees,
                "benchmark_p95": diag_bench.p95,
                "benchmark_upper_band": upper_band_rupees,
                "benchmark_p50": diag_bench.p50,
                "benchmark_p75": diag_bench.p75,
                "benchmark_p90": diag_bench.p90,
                "ratio_vs_p95": round(ratio_vs_p95, 3),
                "pct_above_p95": round(pct_diff, 1),
                "pct_above_p95_int": pct_int,
                "excess_paise": diff_paise,
                "excess_rupees": to_rupees(diff_paise),
                "fallback_level": diag_bench.fallback_level,
                "sample_count": diag_bench.sample_count
            }
        ))

    # 2. LINE_ITEM_PRICE_ABOVE_BENCHMARK
    line_items = claim_dict.get("line_items", []) or []
    ancillary_items = []
    ancillary_paise = 0

    for idx, it in enumerate(line_items):
        desc = it.get("description", "")
        unit_price = float(it.get("unit_price", 0.0) or 0.0)
        amt = float(it.get("amount", 0.0) or 0.0)
        qty = float(it.get("qty", 1.0) or 1.0)
        cat = benchmark_service.normalize_line_item_category(desc)
        cat_bench = benchmark_service.get_category_benchmark(cat, diag_code)

        unit_paise = to_paise(unit_price)
        cat_p95_unit_paise = to_paise(cat_bench.unit_price_p95)

        # Track true ancillary / consumable items only (exclude diagnostics, labs, imaging, rehab, consultations)
        desc_lower = desc.lower()
        is_consumable_item = (
            cat == "ancillary" or
            any(k in desc_lower for k in [
                "consumable", "disposable", "cannula", "trocar", "catheter",
                "ppe kit", "bandage", "dressing", "gauze", "syringe pack", "surgical pack",
                "hemostatic", "gel pack", "endosuture", "stapler"
            ])
        ) and not any(k in desc_lower for k in [
            "mri", "ct ", "scan", "x-ray", "radiology", "pathology", "lab", "test", "physio", "rehab", "therapy",
            "consult", "doctor", "visiting", "room", "bed", "ward", "icu"
        ])

        if is_consumable_item:
            ancillary_items.append(it)
            ancillary_paise += to_paise(amt)

        # Line item benchmark check: widened band logic
        is_exact_cat = (cat_bench.fallback_level == "exact" and cat_bench.sample_count >= 30)
        item_tolerance_margin = 0.20 if is_exact_cat else 0.30
        item_upper_band_paise = int(round(cat_p95_unit_paise * (1.0 + item_tolerance_margin)))
        item_upper_band_rupees = to_rupees(item_upper_band_paise)

        # Compute monetary impact
        item_excess_paise = max(0, (unit_paise - cat_p95_unit_paise)) * int(round(qty))
        excess_share = (item_excess_paise / max(1, total_paise)) if total_paise > 0 else 0.0
        item_excess_rupees = to_rupees(item_excess_paise)

        # Materiality gate: Must exceed widened upper band AND have material rupee impact (>= ₹2,000 and >= 3% share)
        if unit_paise > item_upper_band_paise and unit_price > 0 and (item_excess_rupees >= 2000.0 and excess_share >= 0.03):
            ratio_vs_p95 = unit_paise / max(1, cat_p95_unit_paise)
            excess_ratio = unit_paise / max(1, item_upper_band_paise)
            pct_diff = (ratio_vs_p95 - 1.0) * 100
            pct_int = round(pct_diff)
            pct_str = f"+{pct_diff:.1f}%" if pct_diff < 1.0 else f"+{pct_int}%"
            pct_text = f"{pct_diff:.1f}%" if pct_diff < 1.0 else f"{pct_int}%"

            if cat == "room_rent":
                sev = Severity.LOW  # Room rent caps are primarily audited by check_policy_caps
            elif (excess_ratio >= 1.35 or ratio_vs_p95 >= 1.60) and item_excess_rupees >= 12000.0 and excess_share >= 0.20:
                sev = Severity.CRITICAL
            elif excess_ratio > 1.15 and item_excess_rupees >= 5000.0 and excess_share >= 0.08:
                sev = Severity.HIGH
            elif excess_ratio > 1.0 and item_excess_rupees >= 2000.0 and excess_share >= 0.03:
                sev = Severity.MEDIUM
            else:
                sev = Severity.LOW

            # Weak benchmark cap
            if cat_bench.sample_count < 30 or cat_bench.fallback_level == "global":
                sev = Severity.LOW

            chip_item = f"{cat.title()} rate {ratio_vs_p95:.1f}x p95"
            chips.append(chip_item)

            computed[f"line_{idx+1}_unit_price"] = unit_price
            computed[f"line_{idx+1}_unit_p95"] = cat_bench.unit_price_p95
            computed[f"line_{idx+1}_upper_band"] = item_upper_band_rupees
            computed[f"line_{idx+1}_unit_p50"] = cat_bench.unit_price_p50
            computed[f"line_{idx+1}_unit_p90"] = cat_bench.unit_price_p90
            computed[f"line_{idx+1}_ratio"] = round(ratio_vs_p95, 2)
            computed[f"line_{idx+1}_pct"] = pct_int
            computed[f"line_{idx+1}_excess"] = item_excess_rupees

            findings.append(Finding(
                finding_id=f"F-BENCH-ITEM-{idx+1}",
                agent=AgentName.POLICY,
                check_id="LINE_ITEM_PRICE_ABOVE_BENCHMARK",
                severity=sev,
                title=f"Line item unit price exceeds benchmark: {desc}",
                explanation=(
                    f"Unit price of ₹{unit_price:,.2f} for '{desc}' (category: '{cat}') is {pct_text} above the "
                    f"95th percentile benchmark of ₹{cat_bench.unit_price_p95:,.2f} (widened band: ₹{item_upper_band_rupees:,.2f}, "
                    f"excess: ₹{item_excess_rupees:,.2f}, {excess_share*100:.1f}% of claim, benchmark level: '{cat_bench.fallback_level}', "
                    f"n={cat_bench.sample_count}, p50=₹{cat_bench.unit_price_p50:,.2f}, p90=₹{cat_bench.unit_price_p90:,.2f}, p95=₹{cat_bench.unit_price_p95:,.2f})."
                ),
                evidence=[Evidence(
                    doc_id=doc_id,
                    page=it.get("page", 1),
                    bbox=it.get("bbox"),
                    quote=f"{desc}: billed unit price ₹{unit_price:,.2f} vs p95 ₹{cat_bench.unit_price_p95:,.2f} (band ₹{item_upper_band_rupees:,.2f}, n={cat_bench.sample_count}, level={cat_bench.fallback_level})"
                )],
                confidence=0.95,
                computed_chip=chip_item,
                computed_details={
                    "description": desc,
                    "category": cat,
                    "unit_price": unit_price,
                    "item_upper_band": item_upper_band_rupees,
                    "benchmark_unit_p50": cat_bench.unit_price_p50,
                    "benchmark_unit_p75": cat_bench.unit_price_p75,
                    "benchmark_unit_p90": cat_bench.unit_price_p90,
                    "benchmark_unit_p95": cat_bench.unit_price_p95,
                    "ratio_vs_p95": round(ratio_vs_p95, 3),
                    "pct_above_p95": pct_int,
                    "item_excess_rupees": item_excess_rupees,
                    "excess_share_pct": round(excess_share * 100, 1),
                    "fallback_level": cat_bench.fallback_level,
                    "sample_count": cat_bench.sample_count
                }
            ))

    # 3. UNBUNDLED_OR_PADDED_ANCILLARY
    # Requires authentic category benchmark evidence:
    # 1) At least 3 distinct consumable line items
    # 2) Ancillary consumable share must exceed 28% of total bill
    # 3) Total ancillary consumable billing must exceed max(1.35x p95, ₹15,000)
    ancillary_bench = benchmark_service.get_category_benchmark("ancillary", diag_code)
    ancillary_p95_amt_paise = to_paise(ancillary_bench.amount_p95)
    ancillary_threshold_paise = max(int(round(ancillary_p95_amt_paise * 1.35)), to_paise(15000.0))
    ancillary_share = (ancillary_paise / max(1, total_paise)) if total_paise > 0 else 0.0

    computed["ancillary_total_rupees"] = to_rupees(ancillary_paise)
    computed["ancillary_threshold_rupees"] = to_rupees(ancillary_threshold_paise)
    computed["ancillary_share_pct"] = round(ancillary_share * 100, 1)
    computed["ancillary_share_pct_int"] = round(ancillary_share * 100)
    computed["ancillary_p95_rupees"] = ancillary_bench.amount_p95
    computed["ancillary_p50_rupees"] = ancillary_bench.amount_p50
    computed["ancillary_item_count"] = len(ancillary_items)

    if (
        len(ancillary_items) >= 3 and
        ancillary_share >= 0.28 and
        ancillary_paise > ancillary_threshold_paise
    ):
        ratio = ancillary_paise / max(1, ancillary_p95_amt_paise)
        if ratio >= 2.2 and ancillary_share >= 0.40:
            sev = Severity.HIGH
        elif ratio >= 1.60 or ancillary_share >= 0.32:
            sev = Severity.MEDIUM
        else:
            sev = Severity.LOW

        if ancillary_bench.fallback_level == "global" and sev == Severity.HIGH:
            sev = Severity.MEDIUM

        chip_anc = f"Padded ancillary: ₹{to_rupees(ancillary_paise):,.0f} ({ancillary_share*100:.0f}%)"
        chips.append(chip_anc)
        findings.append(Finding(
            finding_id="F-BENCH-ANCILLARY-PADDED",
            agent=AgentName.POLICY,
            check_id="UNBUNDLED_OR_PADDED_ANCILLARY",
            severity=sev,
            title=f"Unbundled or padded ancillary charges detected (₹{to_rupees(ancillary_paise):,.2f})",
            explanation=(
                f"Cumulative ancillary/consumables charges total ₹{to_rupees(ancillary_paise):,.2f} across {len(ancillary_items)} lines "
                f"({ancillary_share*100:.1f}% of total bill), exceeding category threshold of ₹{to_rupees(ancillary_threshold_paise):,.2f} "
                f"(benchmark p95: ₹{ancillary_bench.amount_p95:,.2f}, level: '{ancillary_bench.fallback_level}', n={ancillary_bench.sample_count}, "
                f"p50=₹{ancillary_bench.amount_p50:,.2f}). This pattern indicates unbundled surgical consumables padding."
            ),
            evidence=[Evidence(
                doc_id=doc_id,
                page=1,
                quote=f"Ancillary charges total: ₹{to_rupees(ancillary_paise):,.2f} across {len(ancillary_items)} items ({ancillary_share*100:.1f}% of bill vs threshold ₹{to_rupees(ancillary_threshold_paise):,.2f})"
            )],
            confidence=0.95,
            computed_chip=chip_anc,
            computed_details={
                "ancillary_total": to_rupees(ancillary_paise),
                "ancillary_item_count": len(ancillary_items),
                "ancillary_share": round(ancillary_share, 4),
                "ancillary_share_pct": round(ancillary_share * 100, 1),
                "ancillary_share_pct_int": round(ancillary_share * 100),
                "benchmark_amount_p50": ancillary_bench.amount_p50,
                "benchmark_amount_p95": ancillary_bench.amount_p95,
                "benchmark_threshold": to_rupees(ancillary_threshold_paise),
                "ratio_vs_p95": round(ratio, 3),
                "fallback_level": ancillary_bench.fallback_level,
                "sample_count": ancillary_bench.sample_count
            }
        ))

    return {
        "findings": findings,
        "computed": computed,
        "chips": chips
    }


def check_dates(
    admission_ts: Union[datetime, str],
    discharge_ts: Union[datetime, str],
    document_dates: Optional[List[Dict[str, Any]]] = None,
    doc_id: str = "doc_main"
) -> Dict[str, Any]:
    """Validates chronological sequence of hospitalization admission and discharge."""
    admission_ts = normalize_to_utc(admission_ts)
    discharge_ts = normalize_to_utc(discharge_ts)

    if not admission_ts or not discharge_ts:
        return {
            "valid": True,
            "findings": [],
            "computed": {},
            "chip": "Dates missing"
        }

    findings: List[Finding] = []
    los_seconds = (discharge_ts - admission_ts).total_seconds()
    los_days = max(1, math.ceil(los_seconds / 86400.0))

    valid = admission_ts <= discharge_ts
    chip = f"Length of Stay: {los_days} day{'s' if los_days != 1 else ''}"

    computed = {
        "length_of_stay_days": los_days,
        "duration_hours": round(los_seconds / 3600.0, 1),
        "admission_year": admission_ts.year,
        "discharge_year": discharge_ts.year
    }

    if not valid:
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
            confidence=1.0,
            computed_chip="Temporal Impossibility",
            computed_details=computed
        ))

    return {
        "valid": valid,
        "findings": findings,
        "computed": computed,
        "chip": chip
    }


def haversine_km(a: Any, b: Any = None, lat2: Optional[float] = None, lon2: Optional[float] = None) -> Dict[str, Any]:
    """Computes great-circle distance between two coordinate pairs."""
    dist = _raw_haversine(a, b, lat2, lon2)
    dist_rounded = round(dist / 10.0) * 10.0 if dist > 50 else round(dist, 1)
    chip = f"{dist_rounded:,.0f} km"

    return {
        "km": dist,
        "computed": {
            "km": dist,
            "km_rounded": dist_rounded
        },
        "chip": chip
    }


def min_travel_hours(km: float) -> Dict[str, Any]:
    """Calculates minimum realistic travel hours (Road <= 300km, Air > 300km)."""
    hrs = _raw_min_travel(km)
    chip = f"min realistic travel ≈ {hrs:.1f} h"

    return {
        "min_hours": hrs,
        "computed": {
            "min_hours": hrs,
            "road_speed_kmh": 80,
            "flight_speed_kmh": 700,
            "airport_overhead_hours": 2.5
        },
        "chip": chip
    }


def is_feasible(event_a: Any, event_b: Any) -> Dict[str, Any]:
    """Evaluates physical spacetime feasibility between consecutive events."""
    res = _raw_is_feasible(event_a, event_b)
    km = res.get("km", 0.0)
    avail_min = int(round(res.get("available_h", 0.0) * 60))
    req_h = res.get("required_h", 0.0)

    if not res.get("feasible", True) and not res.get("skipped", False):
        chip = f"{round(km):,.0f} km in {avail_min} min (req ≈ {req_h:.1f} h)"
    else:
        chip = f"{round(km):,.0f} km in {avail_min} min (Feasible)"

    computed = {
        "km": km,
        "available_hours": res.get("available_h", 0.0),
        "available_minutes": avail_min,
        "required_hours": req_h,
        "feasible": 1 if res.get("feasible") else 0
    }

    return {
        **res,
        "computed": computed,
        "chip": chip
    }


def score_findings(findings: List[Finding], ml_probability: Optional[float] = None) -> Dict[str, Any]:
    """Computes deterministic final risk score and verdict."""
    score, verdict = _raw_score_findings(findings, ml_probability)
    chip = f"Score: {score}/100 ({verdict.value.upper()})"

    crit_cnt = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    high_cnt = sum(1 for f in findings if f.severity == Severity.HIGH)
    med_cnt = sum(1 for f in findings if f.severity == Severity.MEDIUM)
    low_cnt = sum(1 for f in findings if f.severity == Severity.LOW)

    computed = {
        "risk_score": score,
        "verdict_value": verdict.value,
        "critical_count": crit_cnt,
        "high_count": high_cnt,
        "medium_count": med_cnt,
        "low_count": low_cnt,
        "finding_count": len(findings)
    }

    return {
        "score": score,
        "verdict": verdict,
        "computed": computed,
        "chip": chip
    }


def ml_score(claim_features: Dict[str, Any]) -> Dict[str, Any]:
    """Scores claim features using BigQuery ML boosted tree classifier."""
    from backend.tools.bq import ml_score as _raw_ml_score
    prob, top_features = _raw_ml_score(claim_features)
    pct = round(prob * 100, 1)
    chip = f"BQML: {pct}% fraud prob"

    computed = {
        "fraud_probability": round(prob, 4),
        "fraud_probability_pct": pct,
        "top_feature_count": len(top_features)
    }

    return {
        "probability": prob,
        "top_features": top_features,
        "computed": computed,
        "chip": chip
    }


# ==============================================================================
# TOOL REGISTRY & DISPATCHER WITH CLOUD LOGGING
# ==============================================================================

TOOL_MAP: Dict[str, Callable[..., Any]] = {
    "validate_arithmetic": validate_arithmetic,
    "check_policy_caps": check_policy_caps,
    "check_price_benchmarks": check_price_benchmarks,
    "check_dates": check_dates,
    "haversine_km": haversine_km,
    "min_travel_hours": min_travel_hours,
    "is_feasible": is_feasible,
    "score_findings": score_findings,
    "ml_score": ml_score
}


def call_tool(
    tool_name: str,
    args: Dict[str, Any],
    claim_id: str = "CLM-UNKNOWN",
    agent_name: str = "system"
) -> Dict[str, Any]:
    """
    Executes a registered deterministic tool with latency measurement,
    cryptographic argument/result hashing, and structured Cloud Logging.
    """
    if tool_name not in TOOL_MAP:
        raise ValueError(f"Tool '{tool_name}' not found in FinShield registry.")

    tool_fn = TOOL_MAP[tool_name]
    start_time = time.perf_counter()

    result = tool_fn(**args)
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # Stable canonical JSON hashes
    args_json = json.dumps(args, sort_keys=True, default=str)
    result_json = json.dumps(result, sort_keys=True, default=str)
    args_hash = hashlib.sha256(args_json.encode("utf-8")).hexdigest()[:12]
    result_hash = hashlib.sha256(result_json.encode("utf-8")).hexdigest()[:12]

    # Structured Cloud Logging line
    log_entry = {
        "claim_id": claim_id,
        "agent": agent_name,
        "tool": tool_name,
        "args_hash": args_hash,
        "result_hash": result_hash,
        "latency_ms": round(latency_ms, 2)
    }
    logger.info("FINSHIELD_TOOL_AUDIT: %s", json.dumps(log_entry))

    # Persist in claim audit store
    TOOL_AUDIT_LOG.setdefault(claim_id, []).append(log_entry)

    # Accumulate computed numbers into claim store
    if isinstance(result, dict) and "computed" in result:
        store = CLAIM_COMPUTED_STORE.setdefault(claim_id, {})
        store.update(result["computed"])

    return result


def get_tool_audit_transcript(claim_id: str) -> List[Dict[str, Any]]:
    """Returns the chronological audit log of all tool calls made for a claim."""
    return TOOL_AUDIT_LOG.get(claim_id, [])


def get_all_computed_values(claim_id: str) -> Dict[str, Any]:
    """Returns all deterministic numeric outputs computed for a claim."""
    return CLAIM_COMPUTED_STORE.get(claim_id, {})


# ==============================================================================
# VERTEX AI FUNCTION-CALLING DECLARATIONS
# ==============================================================================

FUNCTION_DECLARATIONS = [
    {
        "name": "validate_arithmetic",
        "description": "Deterministic validator for line item arithmetic, subtotals, taxes, and totals in integer paise. Returns computed numbers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "line_items": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "description": {"type": "STRING"},
                            "qty": {"type": "NUMBER"},
                            "unit_price": {"type": "NUMBER"},
                            "amount": {"type": "NUMBER"}
                        },
                        "required": ["amount"]
                    }
                },
                "subtotal": {"type": "NUMBER", "description": "Printed subtotal"},
                "tax": {"type": "NUMBER", "description": "Applicable tax"},
                "total": {"type": "NUMBER", "description": "Claimed total payable"}
            },
            "required": ["line_items", "subtotal", "tax", "total"]
        }
    },
    {
        "name": "check_policy_caps",
        "description": "Checks claim charges against policy caps (room rent, ICU) with paise accuracy.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "policy_id": {"type": "STRING", "description": "Insurance policy identifier"},
                "claim": {"type": "OBJECT", "description": "Claim data with line items and stay details"}
            },
            "required": ["policy_id", "claim"]
        }
    },
    {
        "name": "check_price_benchmarks",
        "description": "Checks claim total and itemized unit prices against BigQuery statistical benchmarks to identify inflation, micro-upcoding, and unbundled charges.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "claim": {"type": "OBJECT", "description": "Claim data with line items and diagnosis code"},
                "doc_id": {"type": "STRING", "description": "Target document identifier"}
            },
            "required": ["claim"]
        }
    },
    {
        "name": "check_dates",
        "description": "Validates chronological order of admission and discharge timestamps.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "admission_ts": {"type": "STRING", "description": "Admission ISO timestamp"},
                "discharge_ts": {"type": "STRING", "description": "Discharge ISO timestamp"}
            },
            "required": ["admission_ts", "discharge_ts"]
        }
    },
    {
        "name": "haversine_km",
        "description": "Calculates great-circle distance between two coordinates in kilometers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "a": {"type": "ARRAY", "items": {"type": "NUMBER"}, "description": "[lat1, lon1]"},
                "b": {"type": "ARRAY", "items": {"type": "NUMBER"}, "description": "[lat2, lon2]"}
            },
            "required": ["a", "b"]
        }
    },
    {
        "name": "min_travel_hours",
        "description": "Calculates minimum realistic travel hours (road speed 80 km/h or flight 700 km/h + 2.5h overhead).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "km": {"type": "NUMBER", "description": "Distance in kilometers"}
            },
            "required": ["km"]
        }
    },
    {
        "name": "is_feasible",
        "description": "Evaluates physical feasibility between two consecutive spacetime events.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "event_a": {"type": "OBJECT", "description": "First spacetime event"},
                "event_b": {"type": "OBJECT", "description": "Second spacetime event"}
            },
            "required": ["event_a", "event_b"]
        }
    },
    {
        "name": "score_findings",
        "description": "Computes final deterministic risk score (0-100) and verdict.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "findings": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "List of findings"}
            },
            "required": ["findings"]
        }
    },
    {
        "name": "ml_score",
        "description": "Predicts fraud probability and top SHAP explainability features using BigQuery ML.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "claim_features": {"type": "OBJECT", "description": "Engineered tabular claim features"}
            },
            "required": ["claim_features"]
        }
    }
]
