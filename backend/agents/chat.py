"""
Adjuster Chat Copilot Agent for FinShield.
Enables insurance adjusters to query the claim dossier via conversational AI.
Grounded strictly on: the Dossier, all Findings, extracted Claim JSON, and policy clauses.
Uses Gemini Pro via google-genai SDK. Fails explicitly if cloud Gemini is unreachable.
"""

import re
import json
import logging
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple

from backend.app.config import settings
from backend.app.schemas import Claim, Dossier, Finding, Evidence, Severity, AgentName
from backend.app.services.db import db_service

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = (
    "You are FinShield's audit assistant talking to an insurance adjuster. "
    "Answer only from the case file provided. Cite finding ids like [F1] or [F-ARITH-TOTAL]. "
    "If asked something the case file can't answer, say what's missing and what the adjuster could check. "
    "Be brief and neutral. Never call the claimant a criminal — describe evidence and risk."
)

OFF_TOPIC_KEYWORDS = [
    "capital of", "president", "weather", "who won", "football", "cricket", "movie",
    "tell me a joke", "recipe", "population of", "france", "paris", "country",
    "criminal record", "is he going to jail", "is she going to jail", "arrest"
]


def sanitize_chat_context(text: Optional[str]) -> str:
    """Escapes XML delimiters and control directives to prevent prompt injection breakouts."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("</untrusted_case_file_context>", "")
        .replace("</untrusted_adjuster_query>", "")
    )


def build_case_file_context(claim: Claim, dossier: Optional[Dossier]) -> Tuple[str, Dict[str, Finding]]:
    """
    Constructs comprehensive grounding text from the Claim, Dossier, and Findings.
    Returns (context_text, finding_lookup_map).
    """
    lines = []
    lines.append("=== CASE FILE: CLAIM AUDIT DOSSIER ===")
    lines.append(f"Claim ID: {claim.claim_id}")
    lines.append(f"Policy ID: {claim.policy_id}")
    lines.append(f"Insurer: {claim.insurer_id}")
    lines.append(f"Claimant: {sanitize_chat_context(claim.claimant.name)} (ID: {claim.claimant.claimant_id})")
    lines.append(f"Healthcare Provider: {sanitize_chat_context(claim.provider.name)}, {claim.provider.city} (Hospital ID: {claim.provider.hospital_id})")
    adm_str = claim.admission_ts.strftime('%d-%b-%Y %H:%M') if isinstance(claim.admission_ts, datetime) else str(claim.admission_ts or 'Unknown')
    dis_str = claim.discharge_ts.strftime('%d-%b-%Y %H:%M') if isinstance(claim.discharge_ts, datetime) else str(claim.discharge_ts or 'Unknown')
    lines.append(f"Hospitalization: {adm_str} to {dis_str}")
    lines.append(f"Diagnosis Code: {claim.diagnosis_code or 'Unknown'}")
    sub_val = claim.subtotal if claim.subtotal is not None else (claim.total_claimed or 0.0)
    tax_val = claim.tax if claim.tax is not None else 0.0
    tot_val = claim.total_claimed if claim.total_claimed is not None else 0.0
    lines.append(f"Total Claimed: ₹{tot_val:,.2f} (Subtotal: ₹{sub_val:,.2f}, Tax: ₹{tax_val:,.2f})")

    lines.append("\n--- Itemized Bill Breakdown ---")
    for it in claim.line_items:
        lines.append(f"- {sanitize_chat_context(it.description)}: {it.qty} unit(s) @ ₹{it.unit_price:,.2f} = ₹{it.amount:,.2f}")

    finding_map: Dict[str, Finding] = {}

    if dossier:
        lines.append("\n--- Audit Dossier Summary ---")
        lines.append(f"Hybrid Risk Score: {dossier.risk_score}/100")
        if dossier.ml_score is not None:
            lines.append(f"BigQuery ML Probability: {dossier.ml_score * 100:.1f}%")
        lines.append(f"Audit Verdict: {dossier.verdict.value.upper()}")
        lines.append(f"Executive Summary: {sanitize_chat_context(dossier.summary)}")

        lines.append("\n--- Flagged Findings & Evidence ---")
        if not dossier.findings:
            lines.append("No anomaly findings flagged. All checks evaluated clean.")
        else:
            for idx, f in enumerate(dossier.findings, 1):
                alias = f"F{idx}"
                finding_map[alias] = f
                finding_map[f.finding_id] = f

                ev_quotes = []
                for ev in f.evidence:
                    safe_quote = sanitize_chat_context(ev.quote)
                    quote_str = f"Page {ev.page}: '{safe_quote}'" if safe_quote else f"Page {ev.page}"
                    if ev.bbox:
                        quote_str += f" [bbox: {ev.bbox}]"
                    ev_quotes.append(quote_str)

                ev_text = " | ".join(ev_quotes) if ev_quotes else "No direct document quote"
                lines.append(
                    f"[{alias}] (ID: {f.finding_id}) [{f.severity.value.upper()}] {sanitize_chat_context(f.title)}\n"
                    f"  Check: {f.check_id} | Agent: {f.agent.value} | Confidence: {f.confidence}\n"
                    f"  Explanation: {sanitize_chat_context(f.explanation)}\n"
                    f"  Evidence: {ev_text}"
                )

        if dossier.top_ml_features:
            lines.append("\n--- Top BigQuery ML Attributions ---")
            for mf in dossier.top_ml_features:
                lines.append(f"- {mf.feature}: {mf.attribution:+.4f}")

    lines.append("\n--- Applicable Insurer Policy Rules & Caps ---")
    lines.append("- Room Rent Cap (Arogya Sanjeevani Clause 3.1): Maximum ₹5,000/day or 2% of sum insured.")
    lines.append("- ICU Rent Cap: Maximum ₹10,000/day or 5% of sum insured.")
    lines.append("- Cross-Insurer Co-ordination: Simultaneous duplicate claims without disclosure violate Section 45.")

    return "\n".join(lines), finding_map


def extract_citations(text: str, finding_map: Dict[str, Finding]) -> Tuple[List[str], List[Evidence]]:
    """
    Parses citation markers like [F1], [F2], or [F-ARITH-TOTAL] in text and resolves them to Finding IDs and Evidence.
    """
    cited_ids: List[str] = []
    cited_evidence: List[Evidence] = []
    seen_ids = set()

    # Matches [F1], [F2], [F-ARITH-TOTAL], [F-POLICY-ROOM-RENT], etc.
    matches = re.findall(r"\[(F\d+|F-[A-Z0-9_\-]+)\]", text)
    for m in matches:
        if m in finding_map:
            f = finding_map[m]
            if f.finding_id not in seen_ids:
                seen_ids.add(f.finding_id)
                cited_ids.append(f.finding_id)
                cited_evidence.extend(f.evidence)

    return cited_ids, cited_evidence



async def stream_chat_response(
    claim_id: str,
    user_message: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Streams the assistant's answer chunk-by-chunk via Server-Sent Events (SSE).
    Yields dicts with format:
      {"chunk": str, "done": False}
      {"done": True, "answer": str, "cited_finding_ids": List[str], "cited_evidence": List[Dict]}
    Saves user and assistant messages in Firestore/SQLite.
    """
    # 1. Fetch Claim and Dossier
    claim = db_service.get_claim(claim_id)
    if not claim:
        yield {"chunk": f"Error: Claim {claim_id} not found in database.", "done": False}
        yield {"done": True, "answer": f"Error: Claim {claim_id} not found.", "cited_finding_ids": [], "cited_evidence": []}
        return

    dossier = db_service.get_dossier(claim_id)
    if not dossier:
        try:
            from backend.agents.root import run_claims_fraud_pipeline
            dossier = run_claims_fraud_pipeline(claim)
            db_service.save_dossier(dossier)
        except Exception as e:
            logger.info("Auto-generating dossier note for claim %s: %s", claim_id, e)

    context_text, finding_map = build_case_file_context(claim, dossier)

    # 2. Check if live Gemini API is usable
    path_taken: Optional[str] = None  # "live" | "retried" | "fallback"
    full_answer = ""
    cited_ids = []
    cited_evidence = []
    try:
        from google.genai import types
        from backend.app.services.gemini_client import get_gemini_client, get_model_name

        client = get_gemini_client()
        model_name = get_model_name("pro")

        safe_query = sanitize_chat_context(user_message)
        prompt = (
            "You are FinShield's audit assistant talking to an insurance adjuster. "
            "Answer only from the case file provided below. Cite finding IDs like [F1]. "
            "If asked something the case file cannot answer, say what is missing. "
            "Be brief, objective, and neutral. Never call the claimant a criminal.\n\n"
            "<untrusted_case_file_context>\n"
            f"{context_text}\n"
            "</untrusted_case_file_context>\n\n"
            "<untrusted_adjuster_query>\n"
            f"{safe_query}\n"
            "</untrusted_adjuster_query>\n\n"
            "Respond based exclusively on the provided context."
        )

        for attempt in (1, 2):
            try:
                response_stream = client.models.generate_content_stream(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=CHAT_SYSTEM_PROMPT,
                        temperature=0.2,
                    )
                )

                attempt_chunks = []
                for chunk in response_stream:
                    if chunk.text:
                        attempt_chunks.append(chunk.text)

                candidate_text = "".join(attempt_chunks)
                if not candidate_text.strip():
                    raise ValueError("Gemini returned empty or whitespace-only response")

                # Successfully generated non-empty answer
                path_taken = "live" if attempt == 1 else "retried"
                logger.info("Chat answer produced via %s Gemini path for claim %s", path_taken, claim_id)

                for chunk_text in attempt_chunks:
                    full_answer += chunk_text
                    yield {"chunk": chunk_text, "done": False}
                    await asyncio.sleep(0.01)

                cited_ids, cited_evidence = extract_citations(full_answer, finding_map)
                break
            except Exception as e:
                if attempt == 1:
                    logger.warning("Live Gemini attempt 1 failed for claim %s: %s. Retrying once...", claim_id, e)
                else:
                    logger.warning("Live Gemini attempt 2 failed for claim %s: %s.", claim_id, e)
    except Exception as e:
        logger.warning("Failed to initialize or call Gemini client for claim %s: %s", claim_id, e)

    # 3. Explicit error response if Gemini was unavailable or both attempts failed
    if not path_taken:
        path_taken = "unavailable"
        logger.error("Chat generation failed for claim %s: live Gemini unavailable after retry.", claim_id)
        full_answer = (
            "AI Dossier Copilot is temporarily unavailable. The cloud Gemini model could not be reached. "
            "Please verify API connectivity and try again."
        )
        cited_ids = []
        cited_evidence = []
        yield {"chunk": full_answer, "done": False}

    # 3b. Enforce Numeric Grounding Guard on chat output (Security Hardening)
    try:
        from backend.tools.grounding import sanitize_text_grounding
        from backend.tools.registry import get_all_computed_values
        computed_store = get_all_computed_values(claim.claim_id)
        grounded_answer, _ = sanitize_text_grounding(full_answer, computed_store, claim)
        full_answer = grounded_answer
    except Exception as e:
        logger.warning("Grounding guard warning for claim %s: %s", claim_id, e)

    # 4. Save chat messages in database (Firestore / SQLite)
    db_service.save_chat_message(claim_id=claim_id, role="user", content=user_message)
    db_service.save_chat_message(
        claim_id=claim_id,
        role="assistant",
        content=full_answer,
        cited_finding_ids=cited_ids
    )

    # 5. Emit final event with structured citation payload
    yield {
        "done": True,
        "answer": full_answer,
        "cited_finding_ids": cited_ids,
        "cited_evidence": [ev.model_dump() for ev in cited_evidence]
    }
