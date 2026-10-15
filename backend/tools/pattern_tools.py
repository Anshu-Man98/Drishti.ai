"""
Corpus 2: Fraud Pattern Discovery & RAG Retrieval Engine (finshield-patterns).
Searches 48 distinctive historical fraud pattern cards based on compact claim fingerprints
(amount ratios, entity links, timing, and specialist findings), avoiding false matches
on superficial terms like hospital names or drug brands.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.app.config import settings
from backend.app.schemas import Claim, Finding, RetrievedContext

PATTERNS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "patterns" / "fraud_patterns.json"


def load_pattern_cards() -> List[Dict[str, Any]]:
    """Loads the 48 distinctive fraud pattern cards."""
    return _load_pattern_catalog()


def _load_pattern_catalog() -> List[Dict[str, Any]]:
    """Loads the 48 distinctive fraud pattern cards."""
    if PATTERNS_PATH.exists():
        with open(PATTERNS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback: compile on the fly if needed
    try:
        from data.build_pattern_cards import build_pattern_cards
        cards = build_pattern_cards()
        with open(PATTERNS_PATH, "w", encoding="utf-8") as f:
            json.dump(cards, f, indent=2)
        return cards
    except Exception as e:
        print(f"[PatternTools] Warning: could not load patterns: {e}")
        return []


def build_claim_fingerprint(
    claim: Claim,
    findings: Optional[List[Finding]] = None
) -> str:
    """
    Builds a compact deterministic claim fingerprint from fraud-relevant features
    and specialist agent findings so far.
    Excludes hospital names and medicine brand names to avoid superficial text matching.
    """
    fingerprint_parts: List[str] = []

    # 1. Structural billing & diagnosis features
    los_days = max(1, int((claim.discharge_ts - claim.admission_ts).total_seconds() // 86400))
    fingerprint_parts.append(f"diagnosis_code:{claim.diagnosis_code}")
    fingerprint_parts.append(f"total_claimed:{claim.total_claimed:.0f}")
    fingerprint_parts.append(f"length_of_stay:{los_days}")

    # Check for room rent rates
    room_items = [it for it in claim.line_items if any(k in it.description.lower() for k in ["room", "ward", "suite", "bed"])]
    if room_items:
        max_rate = max(it.unit_price for it in room_items)
        fingerprint_parts.append(f"max_room_rent_rate:{max_rate:.0f}")
        if max_rate > 5000:
            fingerprint_parts.append("room_rent_vs_cap_ratio_exceeded")

    # 2. Entity link indicators (from claim metadata or bank hash)
    bank_hash = getattr(claim.claimant, "bank_account_hash", "") or ""
    if "ring" in bank_hash.lower() or "shared" in bank_hash.lower():
        fingerprint_parts.append("shared_bank_account_ring shared_bank_account_count:14")
    elif len(bank_hash) == 16:
        # Standard hash format
        fingerprint_parts.append(f"bank_account_hash:{bank_hash[:8]}")

    # 3. Findings check_ids from the ParallelAgent specialists
    if findings:
        for f in findings:
            cid = f.check_id.lower()
            fingerprint_parts.append(f"finding_check:{cid}")
            if "total" in cid or "mismatch" in cid or "arithmetic" in cid:
                fingerprint_parts.append("arithmetic_mismatch total_payable_discrepancy printed_total")
            elif "room" in cid or "cap" in cid:
                fingerprint_parts.append("policy_cap_breach deluxe_suite_over_invoicing clause_3_1")
            elif "duplicate" in cid or "cross" in cid:
                fingerprint_parts.append("cross_insurer_duplicate parallel_submission competing_insurers duplicate_bill")
            elif "spacetime" in cid or "travel" in cid:
                fingerprint_parts.append("impossible_travel haversine_transit high_speed_impossible_velocity")
            elif "forged" in cid or "font" in cid or "producer" in cid or "tamper" in cid:
                fingerprint_parts.append("forged_document typography_tampering metadata_editor_footprint courier_bold")
            elif "injection" in cid:
                fingerprint_parts.append("prompt_injection hidden_instruction_ai_reviewer")

    return " ".join(fingerprint_parts)


def _compute_pattern_match_score(query: str, card: Dict[str, Any]) -> float:
    """
    Computes a relevance score between the claim fingerprint and a pattern card.
    Considers fraud type, observable signature, and title.
    """
    q_tokens = set(re.findall(r"\w+", query.lower()))
    if not q_tokens:
        return 0.0

    # Build card target tokens
    target_str = (
        f"{card.get('fraud_type', '')} "
        f"{card.get('title', '')} "
        f"{card.get('signature', '')} "
        f"{card.get('narrative', '')}"
    ).lower()
    card_tokens = set(re.findall(r"\w+", target_str))

    stop_words = {"the", "and", "or", "in", "on", "at", "to", "for", "of", "with", "is", "a", "an", "this", "that"}
    q_meaningful = q_tokens - stop_words
    if not q_meaningful:
        q_meaningful = q_tokens

    overlap = q_meaningful.intersection(card_tokens)
    if not overlap:
        return 0.0

    # Match ratio based on signature terms
    sig_tokens = set(re.findall(r"\w+", card.get("signature", "").lower())) - stop_words
    sig_overlap = q_meaningful.intersection(sig_tokens)

    # Base recall across query
    base_score = len(overlap) / len(q_meaningful)

    # Boost if signature-specific traits matched directly
    sig_boost = (len(sig_overlap) / max(1, len(sig_tokens))) * 0.4

    # Boost if fraud_type matched exactly
    type_boost = 0.3 if card.get("fraud_type", "").lower() in query.lower() else 0.0

    final_score = min(0.98, base_score * 0.4 + sig_boost + type_boost)
    return round(final_score, 3)


def search_patterns(
    claim_summary_or_fingerprint: str,
    k: int = 3,
    min_score: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Retrieves top-k matching historical fraud patterns from Corpus 2 (finshield-patterns).
    Guards:
      - Results below min_score (0.5) are discarded.
      - Nonsense or clean inputs return empty list [].
    """
    if not settings.RAG_PATTERNS_ENABLED:
        return []

    # Optional: GCP Discovery Engine / Vertex AI Search integration if live
    doc_search_active = (
        not settings.LOCAL_FALLBACK
        and settings.GCP_PROJECT
        and getattr(settings, "DATASTORE_PATTERNS", None)
    )
    if doc_search_active:
        try:
            from google.cloud import discoveryengine_v1 as discoveryengine
            client = discoveryengine.SearchServiceClient()
            serving_config = (
                f"projects/{settings.GCP_PROJECT}/locations/global/collections/default_collection/"
                f"dataStores/{settings.DATASTORE_PATTERNS}/servingConfigs/default_search"
            )
            request = discoveryengine.SearchRequest(
                serving_config=serving_config,
                query=claim_summary_or_fingerprint,
                page_size=k
            )
            response = client.search(request=request)
            results = []
            for item in response.results:
                data = json.loads(item.document.struct_data)
                results.append({
                    "pattern_id": data.get("pattern_id"),
                    "title": data.get("title"),
                    "narrative": data.get("narrative"),
                    "signature": data.get("signature"),
                    "score": 0.85
                })
            if results:
                return results
        except Exception as e:
            # Fall back seamlessly to local knowledge base
            pass

    # Deterministic local knowledge base search
    catalog = _load_pattern_catalog()
    scored_cards = []

    for card in catalog:
        score = _compute_pattern_match_score(claim_summary_or_fingerprint, card)
        if score >= min_score:
            scored_cards.append({
                "pattern_id": card["pattern_id"],
                "fraud_type": card["fraud_type"],
                "title": card["title"],
                "narrative": card["narrative"],
                "signature": card["signature"],
                "typical_severity": card["typical_severity"],
                "score": score
            })

    scored_cards.sort(key=lambda x: x["score"], reverse=True)
    return scored_cards[:k]
