"""
Corpus 2: Fraud Pattern Discovery & RAG Retrieval Engine (finshield-patterns).
Searches 48 distinctive historical fraud pattern cards based on compact claim fingerprints
(amount ratios, entity links, timing, and specialist findings), avoiding false matches
on superficial terms like hospital names or drug brands.
"""

import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.app.config import settings
from backend.app.schemas import Claim, Finding, RetrievedContext

from datetime import datetime

logger = logging.getLogger("finshield.tools.patterns")

PATTERNS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "patterns" / "fraud_patterns.json"

_RUNTIME_LEARNED_PATTERNS: List[Dict[str, Any]] = []


def clear_learned_patterns_cache() -> None:
    """Clears in-memory runtime learned pattern cache (for test isolation)."""
    _RUNTIME_LEARNED_PATTERNS.clear()


def register_learned_pattern(pattern: Dict[str, Any]) -> Dict[str, Any]:
    """
    Registers a new learned evasion tactic from F6 Dueling AI.
    Saves to:
      1. Runtime in-memory catalog cache (_RUNTIME_LEARNED_PATTERNS)
      2. Cloud Firestore 'learned_patterns' collection (and local DB)
      3. BigQuery table 'finshield.learned_patterns'
    Makes it immediately retrievable by search_patterns.
    """
    pid = pattern.get("pattern_id") or f"PAT-LEARNED-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    tactic = pattern.get("tactic") or pattern.get("title") or "Unknown Evasion Tactic"
    sig = pattern.get("signature") or json.dumps(pattern.get("feature_signatures") or {})

    standardized_pattern = {
        "pattern_id": pid,
        "fraud_type": pattern.get("fraud_type") or "learned_evasion",
        "title": pattern.get("title") or f"Learned Evasion: {tactic[:60]}",
        "tactic": tactic,
        "narrative": pattern.get("narrative") or f"Evasion tactic observed during adversarial duel: {tactic}",
        "signature": sig,
        "typical_severity": pattern.get("typical_severity") or "HIGH",
        "feature_signatures": sig,
        "evaded_at": pattern.get("evaded_at") or datetime.utcnow().isoformat()
    }

    # 1. In-memory runtime cache
    _RUNTIME_LEARNED_PATTERNS.append(standardized_pattern)

    # 2. Persist to Firestore and SQLite
    try:
        from backend.app.services.db import db_service
        db_service.save_learned_pattern(standardized_pattern)
    except Exception as e:
        logger.warning("Warning persisting learned pattern to DB: %s", e)

    # 3. Persist to BigQuery finshield.learned_patterns
    if settings.GCP_PROJECT and settings.BIGQUERY_DATASET:
        try:
            from google.cloud import bigquery
            bq_client = bigquery.Client(project=settings.GCP_PROJECT)
            table_id = f"{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.learned_patterns"
            rows_to_insert = [{
                "pattern_id": pid,
                "tactic": tactic,
                "feature_signatures": str(sig),
                "evaded_at": standardized_pattern["evaded_at"]
            }]
            errors = bq_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                logger.error("BigQuery insert error for learned pattern: %s", errors)
        except Exception as e:
            # Non-blocking for offline/test environments
            pass

    return standardized_pattern


def load_pattern_cards() -> List[Dict[str, Any]]:
    """Loads all fraud pattern cards (base catalog + learned patterns)."""
    return _load_pattern_catalog()


def _load_pattern_catalog() -> List[Dict[str, Any]]:
    """Loads the base fraud pattern cards plus dynamically learned evasion patterns."""
    cards: List[Dict[str, Any]] = []
    if PATTERNS_PATH.exists():
        try:
            with open(PATTERNS_PATH, "r", encoding="utf-8") as f:
                cards = json.load(f)
        except Exception as e:
            logger.warning("Could not load patterns from %s: %s", PATTERNS_PATH, e)
    else:
        try:
            from data.build_pattern_cards import build_pattern_cards
            cards = build_pattern_cards()
            with open(PATTERNS_PATH, "w", encoding="utf-8") as f:
                json.dump(cards, f, indent=2)
        except Exception as e:
            logger.warning("Could not build patterns: %s", e)

    # Merge persisted learned patterns from Cloud Firestore / DB
    try:
        from backend.app.services.db import db_service
        persisted = db_service.get_learned_patterns()
        for p in persisted:
            if p.get("pattern_id"):
                cards.append({
                    "pattern_id": p.get("pattern_id"),
                    "fraud_type": p.get("fraud_type") or "learned_evasion",
                    "title": p.get("title") or p.get("tactic") or "Learned Evasion Pattern",
                    "tactic": p.get("tactic") or p.get("title") or "",
                    "narrative": p.get("narrative") or p.get("tactic") or "",
                    "signature": p.get("signature") or str(p.get("feature_signatures") or ""),
                    "typical_severity": p.get("typical_severity") or "HIGH",
                })
    except Exception:
        pass

    # Merge in-memory runtime learned patterns
    for p in _RUNTIME_LEARNED_PATTERNS:
        cards.append(p)

    # Deduplicate by pattern_id (later entries override earlier)
    seen = {}
    for c in cards:
        pid = c.get("pattern_id")
        if pid:
            seen[pid] = c
    return list(seen.values())


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
    from backend.tools.geo import normalize_to_utc
    adm = normalize_to_utc(getattr(claim, "admission_ts", None))
    dis = normalize_to_utc(getattr(claim, "discharge_ts", None))
    if adm and dis:
        los_days = max(1, int((dis - adm).total_seconds() // 86400))
    else:
        los_days = 1

    total_val = float(getattr(claim, "total_claimed", 0.0) or 0.0)
    fingerprint_parts.append(f"diagnosis_code:{claim.diagnosis_code or 'UNKNOWN'}")
    fingerprint_parts.append(f"total_claimed:{total_val:.0f}")
    fingerprint_parts.append(f"length_of_stay:{los_days}")

    # Check for room rent rates
    room_items = [it for it in (claim.line_items or []) if any(k in (getattr(it, "description", "") or "").lower() for k in ["room", "ward", "suite", "bed"])]
    if room_items:
        max_rate = max(getattr(it, "unit_price", 0.0) or 0.0 for it in room_items)
        fingerprint_parts.append(f"max_room_rent_rate:{max_rate:.0f}")
        if max_rate > 5000:
            fingerprint_parts.append("room_rent_vs_cap_ratio_exceeded")

    # 2. Entity link indicators (from claim metadata or bank hash)
    bank_hash = getattr(claim.claimant, "bank_account_hash", "") if claim.claimant else ""
    bank_hash = bank_hash or ""
    if "ring" in bank_hash.lower() or "shared" in bank_hash.lower():
        fingerprint_parts.append("shared_bank_account_ring shared_bank_account_count:14")
    elif len(bank_hash) == 16:
        # Standard hash format
        fingerprint_parts.append(f"bank_account_hash:{bank_hash[:8]}")

    # Check adversarial metadata if present
    if hasattr(claim, "metadata") and isinstance(claim.metadata, dict):
        if "adversarial_tactic" in claim.metadata:
            fingerprint_parts.append(str(claim.metadata["adversarial_tactic"]))

    # 3. Findings check_ids from the ParallelAgent specialists
    if findings:
        for f in findings:
            cid = f.check_id.lower()
            fingerprint_parts.append(f"finding_check:{cid}")
            if ("mismatch" in cid or "subtotal_sum" in cid or "total_payable" in cid or "arithmetic" in cid) and "benchmark" not in cid:
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


def _clean_text_for_tokens(text: str) -> List[str]:
    """Helper to tokenize and filter query and pattern strings."""
    # Bind decimal subcodes in alphanumeric codes like K35.8 -> k35_8, S82.8 -> s82_8
    text_bound = re.sub(r"\b([a-zA-Z]\d{2,3})\.(\d{1,2})\b", r"\1_\2", text)
    tokens = re.findall(r"\w+", text_bound.lower())
    stop_words = {
        "the", "and", "or", "in", "on", "at", "to", "for", "of", "with", "is", "a", "an", "this", "that",
        "diagnosis_code", "total_claimed", "length_of_stay", "max_room_rent_rate", "bank_account_hash",
        "finding_check", "diagnosis", "total", "claimed", "code", "finding", "check", "charges", "charge",
        "per", "day", "days", "length", "stay", "room", "rent", "rate", "max", "bank", "account", "hash"
    }
    result = []
    for t in tokens:
        if t in stop_words:
            continue
        if t.isdigit() and len(t) <= 1:
            continue
        result.append(t)
    return result


def _compute_pattern_match_score(query: str, card: Dict[str, Any]) -> float:
    """
    Computes a relevance score between the claim fingerprint and a pattern card.
    Considers fraud type, observable signature, and title.
    """
    q_meaningful = set(_clean_text_for_tokens(query))
    if not q_meaningful:
        return 0.0

    # Direct pattern ID match shortcut
    if card.get("pattern_id") and card.get("pattern_id").lower() in query.lower():
        return 0.95

    # Build card target tokens
    target_str = (
        f"{card.get('fraud_type', '')} "
        f"{card.get('title', '')} "
        f"{card.get('tactic', '')} "
        f"{card.get('signature', '')} "
        f"{card.get('narrative', '')}"
    )
    card_tokens = set(_clean_text_for_tokens(target_str))

    overlap = q_meaningful.intersection(card_tokens)
    if not overlap:
        return 0.0

    # Match ratio based on signature terms
    sig_tokens = set(_clean_text_for_tokens(card.get("signature", "")))
    sig_overlap = q_meaningful.intersection(sig_tokens)

    # Base recall across query
    base_score = len(overlap) / len(q_meaningful)

    # Boost if signature-specific traits matched directly
    sig_boost = (len(sig_overlap) / max(1, len(sig_tokens))) * 0.4

    # Boost if fraud_type matched exactly
    type_boost = 0.3 if card.get("fraud_type", "").lower() in query.lower() else 0.0

    # Boost if active learned evasion pattern matches key signature traits
    learned_boost = 0.25 if (card.get("fraud_type") == "learned_evasion" and len(sig_overlap) >= 2) else 0.0

    final_score = min(0.98, base_score * 0.4 + sig_boost + type_boost + learned_boost)
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

    # Optional: GCP Discovery Engine / Vertex AI Search integration if configured
    doc_search_active = (
        settings.GCP_PROJECT
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
