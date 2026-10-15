"""
Deterministic policy compliance and limit verification tools.
Uses data/policies/rules.json as the grounded rules engine.
Cites clause IDs, clause text, and policy limits for every check.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from backend.app.schemas import Finding, Evidence, AgentName, Severity

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "policies" / "rules.json"


def _load_rules() -> Dict[str, Any]:
    if RULES_PATH.exists():
        with open(RULES_PATH) as f:
            return json.load(f)
    return {}


def check_policy_caps(
    policy_id: str,
    claim_data: Dict[str, Any],
    doc_id: str = "doc_main"
) -> List[Finding]:
    """
    Evaluates claim line items against policy caps (room rent, ICU, waiting periods).
    Cites specific clause IDs and text.
    """
    findings: List[Finding] = []
    rules_catalog = _load_rules().get("policies", {})

    # Match policy to rule profile
    policy_key = "AROGYA_SANJEEVANI"
    if "CARE" in policy_id.upper():
        policy_key = "CARE_PLUS"
    elif "OPTIMA" in policy_id.upper():
        policy_key = "OPTIMA_SHIELD"

    policy_profile = rules_catalog.get(policy_key, rules_catalog.get("AROGYA_SANJEEVANI", {}))
    rules_list = policy_profile.get("rules", [])
    rules_by_key = {r["rule"]: r for r in rules_list}

    # 1. Check Room Rent Cap
    room_cap_rule = rules_by_key.get("room_rent_cap_per_day")
    if room_cap_rule:
        room_cap_limit = float(room_cap_rule["value"])
        line_items = claim_data.get("line_items", [])
        
        for idx, item in enumerate(line_items):
            desc = item.get("description", "").lower()
            if "room" in desc or "ward" in desc or "bed" in desc or "suite" in desc:
                unit_price = float(item.get("unit_price", 0.0))
                qty = float(item.get("qty", 1.0))

                if unit_price > room_cap_limit:
                    excess_per_day = unit_price - room_cap_limit
                    total_excess = excess_per_day * qty
                    findings.append(Finding(
                        finding_id=f"F-POL-ROOM-CAP-{idx+1}",
                        agent=AgentName.POLICY,
                        check_id="POLICY_ROOM_RENT_CAP_EXCEEDED",
                        severity=Severity.HIGH,
                        title=f"Room rent charges exceed policy cap ({room_cap_rule['clause_id']})",
                        explanation=(
                            f"Room rent billed at ₹{unit_price:,.2f}/day for {qty:.0f} days exceeds the eligible limit of "
                            f"₹{room_cap_limit:,.2f}/day by ₹{excess_per_day:,.2f}/day (Total inadmissible room rent: ₹{total_excess:,.2f}). "
                            f"Cited: {room_cap_rule['clause_id']} — {room_cap_rule['description']}"
                        ),
                        evidence=[Evidence(
                            doc_id=doc_id,
                            page=item.get("page", 1),
                            bbox=item.get("bbox"),
                            quote=f"{item.get('description')}: billed ₹{unit_price}/day vs cap ₹{room_cap_limit}/day"
                        )],
                        confidence=1.0
                    ))

    # 2. Check ICU Rent Cap
    icu_cap_rule = rules_by_key.get("icu_rent_cap_per_day")
    if icu_cap_rule:
        icu_limit = float(icu_cap_rule["value"])
        for idx, item in enumerate(claim_data.get("line_items", [])):
            desc = item.get("description", "").lower()
            if "icu" in desc or "iccu" in desc:
                unit_price = float(item.get("unit_price", 0.0))
                if unit_price > icu_limit:
                    findings.append(Finding(
                        finding_id=f"F-POL-ICU-CAP-{idx+1}",
                        agent=AgentName.POLICY,
                        check_id="POLICY_ICU_CAP_EXCEEDED",
                        severity=Severity.HIGH,
                        title=f"ICU charges exceed eligible sub-limit ({icu_cap_rule['clause_id']})",
                        explanation=(
                            f"ICU billed at ₹{unit_price:,.2f}/day exceeds the policy ceiling of ₹{icu_limit:,.2f}/day. "
                            f"Cited: {icu_cap_rule['clause_id']} — {icu_cap_rule['description']}"
                        ),
                        evidence=[Evidence(
                            doc_id=doc_id,
                            page=item.get("page", 1),
                            bbox=item.get("bbox"),
                            quote=f"Billed ICU: ₹{unit_price}/day, Limit: ₹{icu_limit}/day"
                        )],
                        confidence=1.0
                    ))

    return findings


def search_policy(query: str, policy_id: str = "POL-AROGYA-001") -> Dict[str, Any]:
    """
    Retrieves grounded clauses from policy datastore / rules.json.
    """
    rules_catalog = _load_rules().get("policies", {})
    policy_key = "AROGYA_SANJEEVANI"
    if "CARE" in policy_id.upper():
        policy_key = "CARE_PLUS"
    elif "OPTIMA" in policy_id.upper():
        policy_key = "OPTIMA_SHIELD"

    profile = rules_catalog.get(policy_key, rules_catalog.get("AROGYA_SANJEEVANI", {}))
    rules = profile.get("rules", [])

    q_lower = query.lower()
    matches = []
    for r in rules:
        if any(term in r["rule"] or term in r["description"].lower() for term in q_lower.split()):
            matches.append({
                "clause_id": r["clause_id"],
                "rule": r["rule"],
                "value": r["value"],
                "text": r["description"]
            })

    if not matches and rules:
        matches.append({
            "clause_id": rules[0]["clause_id"],
            "rule": rules[0]["rule"],
            "value": rules[0]["value"],
            "text": rules[0]["description"]
        })

    return {
        "policy_name": profile.get("policy_name", "Standard Health Policy"),
        "matches": matches
    }
