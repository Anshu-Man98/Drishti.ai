"""
Adjuster Chat Copilot Agent for FinShield.
Enables insurance adjusters to query the claim dossier via conversational AI.
Grounded strictly on: the Dossier, all Findings, extracted Claim JSON, and policy clauses.
Uses Gemini Pro via google-genai SDK, with deterministic fallback for offline testing.
"""

import re
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple

from backend.app.config import settings
from backend.app.schemas import Claim, Dossier, Finding, Evidence, Severity, AgentName
from backend.app.services.db import db_service

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
    lines.append(f"Attending Doctor ID: {claim.doctor_id}")
    lines.append(f"Hospitalization: {claim.admission_ts.strftime('%d-%b-%Y %H:%M')} to {claim.discharge_ts.strftime('%d-%b-%Y %H:%M')}")
    lines.append(f"Diagnosis Code: {claim.diagnosis_code}")
    lines.append(f"Total Claimed: ₹{claim.total_claimed:,.2f} (Subtotal: ₹{claim.subtotal:,.2f}, Tax: ₹{claim.tax:,.2f})")

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


def generate_deterministic_answer(
    claim: Claim,
    dossier: Optional[Dossier],
    finding_map: Dict[str, Finding],
    question: str
) -> Tuple[str, List[str], List[Evidence]]:
    """
    Deterministic grounded fallback reasoning engine when live Gemini API key is absent.
    Handles standard adjuster inquiries with exact citations and flags off-topic queries.
    """
    q_lower = question.lower().strip()

    # 1. Off-topic check
    if any(k in q_lower for k in OFF_TOPIC_KEYWORDS) or "france" in q_lower or "capital" in q_lower:
        ans = (
            f"This question cannot be answered from the case file. The case file contains claim details, "
            f"itemized billing, and multi-agent fraud inspection findings for Claim {claim.claim_id}, "
            "but contains no information regarding that topic. If you need additional context, you may "
            "request verified hospital records or policyholder documentation."
        )
        return ans, [], []

    findings = dossier.findings if dossier else []

    # 2. "Why was this flagged?" / "Why flagged"
    if any(k in q_lower for k in ["why was this flagged", "why flagged", "what was flagged", "flags", "anomaly"]):
        if not findings:
            ans = (
                f"Claim {claim.claim_id} was not flagged for fraud or irregularities. "
                "All automated checks (document metadata forensics, policy limit rules, arithmetic reconciliation, "
                f"and claims warehouse cross-referencing) completed clean with Risk Score {dossier.risk_score if dossier else 0}/100. "
                "The claim is recommended for automated approval."
            )
            return ans, [], []

        # Find primary findings
        bullet_points = []
        for idx, (alias, f) in enumerate(finding_map.items()):
            if alias.startswith("F") and alias[1:].isdigit():
                bullet_points.append(f"- [{alias}] {f.title}: {f.explanation}")

        ans = (
            f"Claim {claim.claim_id} was flagged due to {len(findings)} anomaly finding(s) "
            f"resulting in a Hybrid Risk Score of {dossier.risk_score}/100 ({dossier.verdict.value.upper()}):\n\n"
            + "\n".join(bullet_points[:3]) + "\n\n"
            "Each cited flag indicates elevated risk requiring adjuster review or verification against original hospital books."
        )
        c_ids, c_ev = extract_citations(ans, finding_map)
        return ans, c_ids, c_ev

    # 3. "What's the strongest evidence?" / "evidence"
    if any(k in q_lower for k in ["strongest evidence", "main evidence", "best evidence", "evidence"]):
        if not findings:
            ans = f"No adverse evidence was identified for Claim {claim.claim_id}. All line items and metadata match hospital norms."
            return ans, [], []

        # Find primary critical and high severity findings
        crit_findings = [f for f in findings if f.severity == Severity.CRITICAL]
        high_findings = [f for f in findings if f.severity == Severity.HIGH]
        primary_findings = (crit_findings + high_findings)[:2] if (crit_findings or high_findings) else findings[:1]

        points = []
        for pf in primary_findings:
            alias = next((k for k, v in finding_map.items() if v.finding_id == pf.finding_id and k.startswith("F") and k[1:].isdigit()), pf.finding_id)
            ev_quote = pf.evidence[0].quote if pf.evidence and pf.evidence[0].quote else pf.title
            points.append(f"[{alias}] {pf.title}: {pf.explanation} (Evidence: \"{ev_quote}\")")

        ans = (
            f"The strongest evidence for Claim {claim.claim_id} includes:\n\n"
            + "\n\n".join(f"- {pt}" for pt in points)
            + "\n\nThese findings carry the highest severity weighting in the adjuster audit dossier."
        )
        c_ids, c_ev = extract_citations(ans, finding_map)
        return ans, c_ids, c_ev

    # 4. "Which policy clause applies?" / "policy clause" / "clause"
    if any(k in q_lower for k in ["policy clause", "clause", "limit", "cap"]):
        policy_finding = next((f for f in findings if f.agent == AgentName.POLICY), None)
        if policy_finding:
            alias = next((k for k, v in finding_map.items() if v.finding_id == policy_finding.finding_id and k.startswith("F") and k[1:].isdigit()), policy_finding.finding_id)
            ans = (
                f"Under Policy {claim.policy_id}, the relevant clause is Arogya Sanjeevani Clause 3.1 "
                f"which imposes a room rent ceiling of ₹5,000/day. Finding [{alias}] documents that "
                f"the billed rate violates this clause: {policy_finding.explanation}"
            )
        else:
            ans = (
                f"Policy {claim.policy_id} applies standard IRDAI limits: Clause 3.1 limits room rent to ₹5,000/day, "
                "and ICU charges to ₹10,000/day. No policy limit breaches were flagged on this claim."
            )
        c_ids, c_ev = extract_citations(ans, finding_map)
        return ans, c_ids, c_ev

    # 5. "What should I verify next?" / "verify next" / "next steps"
    if any(k in q_lower for k in ["verify next", "next steps", "what should i do", "recommendation", "action"]):
        if not findings:
            ans = (
                "No adverse findings require investigation. You may proceed with standard policy deductibles "
                "verification and automated claim disbursement."
            )
            return ans, [], []

        actions = []
        if any(f.agent == AgentName.FORENSICS for f in findings):
            actions.append("1. Request original digital invoice files directly from hospital billing administration.")
        if any(f.agent == AgentName.POLICY for f in findings):
            actions.append("2. Recalculate admissible room rent according to Clause 3.1 policy caps.")
        if any(f.agent == AgentName.CROSSREF for f in findings):
            actions.append("3. Issue an insurer inquiry notice to verify if an identical claim was submitted to another carrier.")
        if any(f.agent == AgentName.SPACETIME for f in findings):
            actions.append("4. Verify the attending doctor's physical presence via hospital shift and OT registers.")

        if not actions:
            actions.append("1. Request verified original physical hospital discharge papers.")

        ans = (
            f"Based on the flagged findings for Claim {claim.claim_id}, recommended next steps are:\n"
            + "\n".join(actions)
        )
        return ans, [], []

    # 6. General case inquiry
    ans = (
        f"Claim {claim.claim_id} was submitted for ₹{claim.total_claimed:,.2f} at {claim.provider.name} "
        f"under Policy {claim.policy_id}. The multi-agent copilot computed a Hybrid Risk Score of "
        f"{dossier.risk_score if dossier else 0}/100. "
    )
    if findings:
        primary = findings[0]
        alias = next((k for k, v in finding_map.items() if v.finding_id == primary.finding_id and k.startswith("F") and k[1:].isdigit()), primary.finding_id)
        ans += f"Primary observation: [{alias}] {primary.title} ({primary.explanation})."
    else:
        ans += "All forensic, mathematical, and policy verifications are clean."

    c_ids, c_ev = extract_citations(ans, finding_map)
    return ans, c_ids, c_ev


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
            print(f"[Adjuster Chat] Auto-generating dossier note: {e}")

    context_text, finding_map = build_case_file_context(claim, dossier)

    # 2. Check if live Gemini API is usable
    used_gemini = False
    full_answer = ""

    if settings.GOOGLE_API_KEY and not settings.LOCAL_FALLBACK:
        try:
            from google import genai
            from google.genai import types

            if settings.GOOGLE_API_KEY:
                client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            else:
                client = genai.Client(vertexai=True, project=settings.GCP_PROJECT, location=settings.GCP_REGION)

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

            # Stream via Gemini Pro
            response_stream = client.models.generate_content_stream(
                model=settings.GEMINI_PRO_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM_PROMPT,
                    temperature=0.2,
                )
            )

            for chunk in response_stream:
                if chunk.text:
                    full_answer += chunk.text
                    yield {"chunk": chunk.text, "done": False}
                    await asyncio.sleep(0.01)

            used_gemini = True
        except Exception as e:
            print(f"[Adjuster Chat] Live Gemini API call notice, falling back to deterministic engine: {e}")

    # 3. Deterministic engine fallback
    if not used_gemini:
        full_answer, cited_ids, cited_evidence = generate_deterministic_answer(
            claim=claim,
            dossier=dossier,
            finding_map=finding_map,
            question=user_message
        )

        # Stream words smoothly to emulate realistic typing speed
        words = full_answer.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield {"chunk": chunk, "done": False}
            await asyncio.sleep(0.015)
    else:
        cited_ids, cited_evidence = extract_citations(full_answer, finding_map)

    # 3b. Enforce Numeric Grounding Guard on chat output (Security Hardening)
    try:
        from backend.tools.grounding import sanitize_text_grounding
        from backend.tools.registry import get_all_computed_values
        computed_store = get_all_computed_values(claim.claim_id)
        grounded_answer, _ = sanitize_text_grounding(full_answer, computed_store, claim)
        full_answer = grounded_answer
    except Exception as e:
        print(f"[Adjuster Chat] Grounding guard warning: {e}")

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
