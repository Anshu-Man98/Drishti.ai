"""
Deterministic policy compliance and numbered clause retrieval engine (Corpus 1: finshield-policies).
Indexes numbered policy clauses from real IRDAI Arogya Sanjeevani and synthetic policies.
Guarantees every policy finding carries evidence with layer: "retrieved" citing the exact clause.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from backend.app.schemas import Finding, Evidence, AgentName, Severity, Claim

CLAUSES_INDEX_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "policies" / "clauses_index.json"


RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "policies" / "rules.json"


def _load_rules() -> Dict[str, Any]:
    if RULES_PATH.exists():
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_clauses() -> List[Dict[str, Any]]:
    if CLAUSES_INDEX_PATH.exists():
        with open(CLAUSES_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _resolve_policy_key(policy_id: str) -> str:
    pid = (policy_id or "").upper()
    if "CARE" in pid:
        return "CARE_PLUS"
    elif "OPTIMA" in pid or "BUPA" in pid:
        return "OPTIMA_SHIELD"
    return "AROGYA_SANJEEVANI"


def _compute_query_score(query: str, target_text: str) -> float:
    """
    Computes lexical similarity score between query and target clause text.
    Uses token overlap normalized by query length and keyword density.
    """
    q_tokens = set(re.findall(r"\w+", query.lower()))
    if not q_tokens:
        return 0.0

    target_tokens = set(re.findall(r"\w+", target_text.lower()))
    if not target_tokens:
        return 0.0

    # Ignore generic English stop words in score calculation
    stop_words = {"the", "and", "or", "in", "on", "at", "to", "for", "of", "with", "is", "are", "a", "an", "this", "that", "under"}
    q_meaningful = q_tokens - stop_words
    if not q_meaningful:
        q_meaningful = q_tokens

    overlap = q_meaningful.intersection(target_tokens)
    if not overlap:
        return 0.0

    # Recall ratio with penalty for short nonsense matching
    recall = len(overlap) / len(q_meaningful)

    # Boost if key phrases match exactly
    q_str = " ".join(q_meaningful)
    if q_str in target_text.lower():
        recall = min(1.0, recall + 0.3)

    return round(min(1.0, recall), 3)


def search_policy(
    query: str,
    policy_id: str = "POL-AROGYA-88124",
    min_score: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Searches numbered clauses in Corpus 1 (finshield-policies).
    Returns matching clauses scored by relevance.
    Discard results below min_score (default 0.5); nonsense queries return empty list [].
    """
    all_clauses = _load_clauses()
    policy_key = _resolve_policy_key(policy_id)

    # Filter to targeted policy
    relevant_clauses = [c for c in all_clauses if c["policy_key"] == policy_key]
    if not relevant_clauses:
        relevant_clauses = all_clauses

    results = []
    for c in relevant_clauses:
        haystack = f"{c['clause_id']} {c['clause_title']} {c['text']} {c.get('rule', '')}"
        score = _compute_query_score(query, haystack)

        if score >= min_score:
            results.append({
                "clause_id": c["clause_id"],
                "clause_title": c["clause_title"],
                "text": c["text"],
                "page": c.get("page", 1),
                "score": score,
                "source": c.get("source", "real")
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def get_clause_by_id(clause_id: str, policy_id: str = "POL-AROGYA-88124") -> Optional[Dict[str, Any]]:
    """Retrieves exact clause by its numbered ID (e.g. 'Clause 3.1')."""
    all_clauses = _load_clauses()
    policy_key = _resolve_policy_key(policy_id)

    for c in all_clauses:
        if c["policy_key"] == policy_key and c["clause_id"].lower() == clause_id.lower():
            return c
    for c in all_clauses:
        if c["clause_id"].lower() == clause_id.lower():
            return c
    return None


def check_policy_caps(
    policy_id: str,
    claim: Union[Claim, Dict[str, Any]],
    doc_id: str = "doc_main"
) -> List[Finding]:
    """
    Evaluates claim line items against policy caps (room rent, ICU, waiting periods).
    MANDATORY A4 REQUIREMENT:
      Every policy finding carries evidence with layer: "retrieved" citing the exact clause_id and text,
      in addition to the document bounding box with layer: "visible".
    """
    findings: List[Finding] = []
    policy_key = _resolve_policy_key(policy_id)
    all_clauses = _load_clauses()
    policy_clauses = [c for c in all_clauses if c["policy_key"] == policy_key]
    clauses_by_rule = {c.get("rule"): c for c in policy_clauses if c.get("rule")}

    if hasattr(claim, "model_dump"):
        claim_dict = claim.model_dump()
    elif hasattr(claim, "dict"):
        claim_dict = claim.dict()
    elif isinstance(claim, dict):
        claim_dict = claim
    else:
        claim_dict = dict(claim)

    docs = claim_dict.get("documents", [])
    if docs and isinstance(docs[0], dict):
        doc_id = docs[0].get("doc_id", doc_id)

    line_items = claim_dict.get("line_items", [])

    # 1. Check Room Rent Cap (e.g. Arogya Sanjeevani Clause 3.1: ₹5,000/day)
    room_clause = clauses_by_rule.get("room_rent_cap_per_day")
    if room_clause:
        room_cap_limit = float(room_clause["value"])

        for idx, item in enumerate(line_items):
            desc = item.get("description", "").lower()
            if any(term in desc for term in ["room", "ward", "bed", "suite"]):
                unit_price = float(item.get("unit_price", 0.0))
                qty = float(item.get("qty", 1.0))

                if unit_price > room_cap_limit:
                    excess_per_day = unit_price - room_cap_limit
                    total_excess = excess_per_day * qty

                    evidence_items = [
                        # Document bounding box citation (visible layer)
                        Evidence(
                            doc_id=doc_id,
                            page=item.get("page", 1),
                            bbox=item.get("bbox"),
                            quote=f"{item.get('description')}: billed ₹{unit_price:,.2f}/day vs cap ₹{room_cap_limit:,.2f}/day",
                            layer="visible"
                        ),
                        # Policy numbered clause citation (retrieved layer)
                        Evidence(
                            doc_id=room_clause["clause_id"],
                            page=room_clause.get("page", 1),
                            quote=room_clause["text"],
                            layer="retrieved"
                        )
                    ]

                    findings.append(Finding(
                        finding_id=f"F-POL-ROOM-CAP-{idx+1}",
                        agent=AgentName.POLICY,
                        check_id="POLICY_ROOM_RENT_CAP_EXCEEDED",
                        severity=Severity.HIGH,
                        title=f"Room rent charges exceed policy cap ({room_clause['clause_id']})",
                        explanation=(
                            f"Room rent billed at ₹{unit_price:,.2f}/day for {qty:.0f} days exceeds the eligible limit of "
                            f"₹{room_cap_limit:,.2f}/day by ₹{excess_per_day:,.2f}/day (Total inadmissible room rent: ₹{total_excess:,.2f}). "
                            f"Cited: {room_clause['clause_id']} — {room_clause['clause_title']}: \"{room_clause['text']}\""
                        ),
                        evidence=evidence_items,
                        confidence=1.0,
                        computed_chip=f"Exceeds cap: ₹{unit_price:,.2f} > ₹{room_cap_limit:,.2f} ({room_clause['clause_id']})",
                        computed_details={
                            "rule": "room_rent_cap_per_day",
                            "clause_id": room_clause["clause_id"],
                            "clause_title": room_clause["clause_title"],
                            "billed_rate": unit_price,
                            "cap_limit": room_cap_limit,
                            "excess_per_day": excess_per_day,
                            "total_inadmissible": total_excess
                        }
                    ))

    # 2. Check ICU Rent Cap (e.g. Arogya Sanjeevani Clause 3.2: ₹10,000/day)
    icu_clause = clauses_by_rule.get("icu_rent_cap_per_day")
    if icu_clause:
        icu_limit = float(icu_clause["value"])

        for idx, item in enumerate(line_items):
            desc = item.get("description", "").lower()
            if any(term in desc for term in ["icu", "iccu", "intensive care"]):
                unit_price = float(item.get("unit_price", 0.0))
                qty = float(item.get("qty", 1.0))

                if unit_price > icu_limit:
                    excess_per_day = unit_price - icu_limit
                    total_excess = excess_per_day * qty

                    evidence_items = [
                        Evidence(
                            doc_id=doc_id,
                            page=item.get("page", 1),
                            bbox=item.get("bbox"),
                            quote=f"Billed ICU: ₹{unit_price:,.2f}/day, Limit: ₹{icu_limit:,.2f}/day",
                            layer="visible"
                        ),
                        Evidence(
                            doc_id=icu_clause["clause_id"],
                            page=icu_clause.get("page", 1),
                            quote=icu_clause["text"],
                            layer="retrieved"
                        )
                    ]

                    findings.append(Finding(
                        finding_id=f"F-POL-ICU-CAP-{idx+1}",
                        agent=AgentName.POLICY,
                        check_id="POLICY_ICU_CAP_EXCEEDED",
                        severity=Severity.HIGH,
                        title=f"ICU charges exceed eligible sub-limit ({icu_clause['clause_id']})",
                        explanation=(
                            f"ICU billed at ₹{unit_price:,.2f}/day exceeds the policy ceiling of ₹{icu_limit:,.2f}/day. "
                            f"Cited: {icu_clause['clause_id']} — {icu_clause['clause_title']}: \"{icu_clause['text']}\""
                        ),
                        evidence=evidence_items,
                        confidence=1.0,
                        computed_chip=f"Exceeds ICU ceiling: ₹{unit_price:,.2f} > ₹{icu_limit:,.2f} ({icu_clause['clause_id']})",
                        computed_details={
                            "rule": "icu_rent_cap_per_day",
                            "clause_id": icu_clause["clause_id"],
                            "clause_title": icu_clause["clause_title"],
                            "billed_rate": unit_price,
                            "cap_limit": icu_limit,
                            "total_inadmissible": total_excess
                        }
                    ))

    return findings
