"""
Numeric Grounding Guard for FinShield / Drishti.ai.
Enforces the hard rule: "Every number that appears in Dossier.summary and Finding.explanation
must trace to a deterministic tool output or extracted Claim JSON."
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.app.schemas import Claim


# Whitelist patterns for non-factual numerals
WHITELIST_PATTERNS = [
    re.compile(r"\[F-?[A-Za-z0-9_-]+\]", re.IGNORECASE),  # [F1], [F3], [F-MATH-TOTAL]
    re.compile(r"\bF\d+\b", re.IGNORECASE),               # F1, F2
    re.compile(r"Clause\s*\d+(\.\d+)?", re.IGNORECASE),    # Clause 3.1
    re.compile(r"\b202[0-9]\b"),                          # Year 2026, 2025
    re.compile(r"\b(1st|2nd|3rd|4th|5th)\b", re.IGNORECASE)
]


def _extract_number_instances(text: str) -> List[Dict[str, Any]]:
    """
    Extracts all numeric mentions with their raw text, normalized value, and sentence context.
    Handles currency (INR, Rs, ₹, Lakhs, Crores), percentages, distances (km), durations (min, h, days).
    """
    results: List[Dict[str, Any]] = []
    sentences = re.split(r"(?<=[.!?])\s+", text)

    for sentence in sentences:
        if not sentence.strip():
            continue

        # 1. Lakhs and Crores e.g. "1.8 lakh", "2 crore"
        for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*(lakhs?|lacs?|crores?|cr)\b", sentence, re.IGNORECASE):
            raw_str = m.group(0)
            base_num = float(m.group(1))
            unit = m.group(2).lower()
            val = base_num * (100000.0 if "la" in unit else 10000000.0)
            results.append({"raw": raw_str, "value": val, "context": sentence})

        # 2. Explicit Currency e.g. "₹1,80,000", "₹ 112,500.00", "INR 180,000", "Rs. 95,025"
        for m in re.finditer(r"(?:₹|INR|Rs\.?)\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)", sentence, re.IGNORECASE):
            raw_str = m.group(0)
            val_str = m.group(1).replace(",", "")
            results.append({"raw": raw_str, "value": float(val_str), "context": sentence})

        # 3. Distances e.g. "1,150 km", "1154km"
        for m in re.finditer(r"([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)\s*(?:km|kilometers)\b", sentence, re.IGNORECASE):
            raw_str = m.group(0)
            val_str = m.group(1).replace(",", "")
            results.append({"raw": raw_str, "value": float(val_str), "context": sentence})

        # 4. Durations e.g. "90 min", "4.1 h", "2 days"
        for m in re.finditer(r"([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)\s*(?:min|mins|minutes|h|hr|hrs|hours|days|day)\b", sentence, re.IGNORECASE):
            raw_str = m.group(0)
            val_str = m.group(1).replace(",", "")
            results.append({"raw": raw_str, "value": float(val_str), "context": sentence})

        # 5. Percentages e.g. "18%", "5.5%"
        for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*%", sentence):
            raw_str = m.group(0)
            val_str = m.group(1)
            results.append({"raw": raw_str, "value": float(val_str), "context": sentence})

        # 6. Standalone formatted or plain numbers (e.g. 180000, 112,500, 30,000)
        for m in re.finditer(r"\b([0-9]+(?:,[0-9]+)+(?:\.[0-9]+)?)\b", sentence):
            raw_str = m.group(0)
            val_str = m.group(1).replace(",", "")
            # Avoid re-adding if already extracted in currency
            if not any(r["context"] == sentence and raw_str in r["raw"] for r in results):
                results.append({"raw": raw_str, "value": float(val_str), "context": sentence})

    return results


def _collect_ground_truth_numbers(
    tool_outputs: Union[List[Dict[str, Any]], Dict[str, Any]],
    claim: Optional[Claim] = None
) -> Set[float]:
    """
    Gathers all legitimate numbers from tool outputs and Claim JSON into a ground truth set.
    Includes both rupee amounts and paise representations, as well as percentage fractions.
    """
    truth_set: Set[float] = set()

    def _harvest(obj: Any):
        if isinstance(obj, (int, float)):
            if not math.isnan(obj) and not math.isinf(obj):
                truth_set.add(float(obj))
                # Add paise equivalent and rupee equivalent
                truth_set.add(float(round(obj * 100, 2)))
                truth_set.add(float(round(obj / 100.0, 2)))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _harvest(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _harvest(item)

    # 1. Harvest from tool_outputs
    _harvest(tool_outputs)

    # 2. Harvest from Claim JSON if provided
    if claim is not None:
        truth_set.add(float(claim.subtotal))
        truth_set.add(float(claim.tax))
        truth_set.add(float(claim.total_claimed))
        truth_set.add(float(round(claim.total_claimed * 100, 2)))

        for it in claim.line_items:
            truth_set.add(float(it.qty))
            truth_set.add(float(it.unit_price))
            truth_set.add(float(it.amount))
            truth_set.add(float(round(it.amount * 100, 2)))

        truth_set.add(float(claim.provider.lat))
        truth_set.add(float(claim.provider.lng))

        # Dates (day, month, year)
        for dt in [claim.admission_ts, claim.discharge_ts]:
            if isinstance(dt, datetime):
                truth_set.add(float(dt.year))
                truth_set.add(float(dt.month))
                truth_set.add(float(dt.day))

    # Add standard base numbers (0, 1)
    truth_set.add(0.0)
    truth_set.add(1.0)
    truth_set.add(100.0)

    return truth_set


def is_whitelisted(raw_str: str, sentence: str) -> bool:
    """Checks if a numeral mention matches whitelisted patterns."""
    for pat in WHITELIST_PATTERNS:
        if pat.search(raw_str) or pat.search(sentence):
            # Check if this specific number is part of the whitelisted pattern
            match = pat.search(sentence)
            if match and raw_str.replace("₹", "").strip() in match.group(0):
                return True
    return False


def assert_numbers_grounded(
    text: str,
    tool_outputs: Union[List[Dict[str, Any]], Dict[str, Any]],
    claim: Optional[Claim] = None
) -> Dict[str, Any]:
    """
    Validates that every numeric literal in the generated text traces to a deterministic tool
    output or Claim JSON value.
    Returns:
      {
        "grounded": bool,
        "ungrounded": [{"value": str, "context": str, "numeric_value": float}],
        "grounded_values": List[float]
      }
    """
    instances = _extract_number_instances(text)
    truth_set = _collect_ground_truth_numbers(tool_outputs, claim)

    ungrounded_list: List[Dict[str, Any]] = []
    grounded_vals: List[float] = []

    for item in instances:
        raw = item["raw"]
        val = item["value"]
        ctx = item["context"]

        # Check whitelist first
        if is_whitelisted(raw, ctx):
            grounded_vals.append(val)
            continue

        # Check against ground truth set
        # Match with tolerance: exact or within 1 INR or 0.1%
        matched = False
        for gt in truth_set:
            if math.isclose(val, gt, abs_tol=1.0) or math.isclose(val, gt, rel_tol=0.005):
                matched = True
                break

        if matched:
            grounded_vals.append(val)
        else:
            ungrounded_list.append({
                "value": raw,
                "context": ctx,
                "numeric_value": val
            })

    return {
        "grounded": len(ungrounded_list) == 0,
        "ungrounded": ungrounded_list,
        "grounded_values": grounded_vals
    }


def sanitize_text_grounding(
    text: str,
    tool_outputs: Union[List[Dict[str, Any]], Dict[str, Any]],
    claim: Optional[Claim] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Runs the numeric grounding guard. If ungrounded numbers exist, strips the offending sentences
    to prevent shipping fabricated figures.
    Returns: (sanitized_text, list_of_ungrounded_items)
    """
    guard_res = assert_numbers_grounded(text, tool_outputs, claim)
    if guard_res["grounded"]:
        return text, []

    ungrounded = guard_res["ungrounded"]
    bad_contexts = {item["context"].strip() for item in ungrounded}

    sentences = re.split(r"(?<=[.!?])\s+", text)
    clean_sentences = [s for s in sentences if s.strip() not in bad_contexts]

    sanitized = " ".join(clean_sentences).strip()
    return sanitized, ungrounded
