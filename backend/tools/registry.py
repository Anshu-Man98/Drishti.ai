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
    total_bbox: Optional[List[float]] = None
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
                        computed_chip=chip,
                        computed_details=computed
                    ))

    return {
        "compliant": compliant,
        "findings": findings,
        "computed": computed,
        "chip": chip
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
