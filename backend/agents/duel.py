"""
F6 Dueling AI: Adversarial Red-Team Fraudster Agent vs. FinShield Defender.
Implements an iterative adversarial arena:
1. Fraudster Agent: ADK LlmAgent (GEMINI_PRO_MODEL) prompted to mutate claims to evade detection while maximizing payout.
2. Defender: Real FinShield multi-agent scrutiny pipeline (run_claims_fraud_pipeline).
3. Feedback loop: If the fraudster evades detection (verdict == APPROVE and total_claimed >= baseline * 1.2),
   the tactic is extracted, appended to BigQuery table finshield.learned_patterns (and Firestore),
   and immediately registered into the RAG pattern retrieval catalog.
"""

import json
import logging
import uuid
from copy import deepcopy
from datetime import datetime
from typing import List, Dict, Any, Optional

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.schemas import Claim, Dossier, Verdict, Severity, LineItem
from backend.app.services.db import db_service
from backend.agents.root import run_claims_fraud_pipeline
from backend.tools.pattern_tools import register_learned_pattern
from backend.tools.registry import to_paise, to_rupees

logger = logging.getLogger("finshield.duel")


class FraudsterMutationOutput(BaseModel):
    """Structured mutation specification proposed by the Fraudster agent."""
    tactic: str = Field(description="Adversarial tactic name/summary")
    rationale: str = Field(description="Why this mutation is expected to evade FinShield checks")
    target_multiplier: float = Field(default=1.25, description="Payout target multiplier over baseline")
    diagnosis_code: Optional[str] = Field(default=None, description="Updated or upcoded diagnosis code if needed to circumvent tariff ceilings")
    line_item_mutations: List[Dict[str, Any]] = Field(default_factory=list, description="Updated or added line items")
    manipulation_type: str = Field(default="subtle_padding", description="Category of fraud manipulation")


class DuelRound(BaseModel):
    """Record of a single round in the adversarial duel."""
    round_number: int
    tactic: str
    rationale: str
    claim_id: str
    baseline_amount: float
    total_claimed: float
    inflation_ratio: float
    verdict: str
    risk_score: float
    caught: bool
    evaded: bool
    catching_finding_ids: List[str] = Field(default_factory=list)
    catching_check_ids: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DuelResult(BaseModel):
    """Complete summary of a multi-round duel."""
    duel_id: str
    base_claim_id: str
    baseline_amount: float
    max_rounds: int
    rounds: List[DuelRound]
    status: str  # "evaded", "caught", "max_rounds_reached"
    winning_side: str  # "fraudster" | "defender"
    learned_pattern: Optional[Dict[str, Any]] = None


def create_fraudster_agent() -> LlmAgent:
    """
    Creates the ADK LlmAgent for the Fraudster / Red-Team simulator.
    Uses GEMINI_PRO_MODEL to reason over previous defender catches and invent evasive mutations.
    """
    from backend.app.services.gemini_client import get_model_name
    return LlmAgent(
        name="fraudster_agent",
        model=get_model_name("pro"),
        instruction=(
            "You are FinShield's adversarial red-team fraud simulator, operating strictly on synthetic data. "
            "Your objective is to mutate a base insurance claim to maximize fraudulent payout (at least 20% "
            "above baseline) while evading detection by the FinShield defense agents (Forensics, Policy, CrossRef, "
            "Spacetime, BQML, Injection, and RAG). "
            "In each round, analyze the checks and findings that caught you in prior rounds, and design a mutated "
            "billing structure that circumvents those specific checks (e.g. padding line items without breaking "
            "arithmetic sums, shifting room rent charges to non-capped diagnostic categories, adjusting dates, or "
            "subtly distributing costs). "
            "Output JSON only conforming to the mutation schema."
        ),
        output_key="fraudster_mutation"
    )


def _generate_adversarial_mutation_gemini(
    base_claim: Claim,
    round_history: List[DuelRound],
    round_num: int
) -> Optional[FraudsterMutationOutput]:
    """
    Calls Gemini to synthesize a targeted adversarial mutation based on prior catches.
    """
    try:
        from google.genai import types
        from backend.app.services.gemini_client import get_gemini_client, get_model_name

        client = get_gemini_client()
        model_name = get_model_name("pro")
        prior_catches = []
        for r in round_history:
            prior_catches.append({
                "round": r.round_number,
                "tactic_tried": r.tactic,
                "verdict": r.verdict,
                "risk_score": r.risk_score,
                "caught_by_checks": r.catching_check_ids
            })

        claim_summary = {
            "claim_id": base_claim.claim_id,
            "policy_id": base_claim.policy_id,
            "diagnosis_code": base_claim.diagnosis_code,
            "baseline_total": base_claim.total_claimed,
            "line_items": [it.model_dump() for it in (base_claim.line_items or [])]
        }

        prompt = (
            f"You are FinShield's Red-Team Fraudster Simulator in round {round_num}.\n"
            f"Base claim:\n{json.dumps(claim_summary, indent=2)}\n\n"
            f"Prior round defense catches:\n{json.dumps(prior_catches, indent=2)}\n\n"
            "Objective: Mutate this claim to increase total payout by 22% to 35% above the baseline "
            "while evading FinShield's multi-agent scrutiny pipeline.\n\n"
            "Round Guidelines:\n"
            "- If round 1: Try a direct inflation on the existing diagnosis (25-35% price increase across line items).\n"
            "- If prior rounds caught you on benchmark checks (TOTAL_ABOVE_DIAGNOSIS_BENCHMARK, LINE_ITEM_PRICE_ABOVE_BENCHMARK, or UNBUNDLED_OR_PADDED_ANCILLARY):\n"
            "  Circumvent the diagnosis benchmark ceiling by executing a tariff arbitrage / diagnosis upcoding tactic. "
            "  Select an acute inpatient diagnosis code with higher benchmark allowances (e.g. I20.9 Angina / Acute Coronary Syndrome with telemetry & cardiac investigations where median is ₹132,000 and upper band is ₹185,000, or M54.5 Radiculopathy where upper band is ₹182,000). Set 'diagnosis_code' to that code. "
            "  Target total amount between ₹91,000 and ₹95,000 (which achieves a 22% to 28% payout increase above baseline ₹74,550 while sitting comfortably below the ₹132,000 median for I20.9). "
            "  Distribute line items cleanly across valid categories (Ward, Investigations, Pharmacy, Consultation) with realistic unit prices within category benchmarks (e.g. ward bed <= 3,500/day, consultation <= 2,000/visit, diagnostics <= 5,000/test), keep room rent strictly <= 5,000/day, keep ancillary share reasonable, and ensure line item sums strictly balance (qty * unit_price == amount) with subtotal and total matching.\n"
            "- If round 3 or later: Re-use, adapt, or refine the evasion tactic to circumvent newly active pattern detections.\n\n"
            "Return JSON matching keys: tactic, rationale, target_multiplier, diagnosis_code, manipulation_type, line_item_mutations "
            "(list of {description, qty, unit_price, amount, category})."
        )

        response = client.models.generate_content(
            model=model_name,
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json"
            )
        )
        if response and response.text:
            data = json.loads(response.text)
            return FraudsterMutationOutput(**data)
        raise ValueError("Gemini returned empty response for adversarial mutation.")
    except Exception as e:
        logger.error("Gemini fraudster generation error: %s", e)
        from backend.app.exceptions import CloudServiceError
        raise CloudServiceError(
            service="Gemini",
            message=f"Gemini fraudster generation failed: {e}",
            retryable=True
        ) from e





def apply_mutation_to_claim(
    base_claim: Claim,
    mutation: FraudsterMutationOutput,
    round_num: int,
    duel_id: str
) -> Claim:
    """
    Applies the Fraudster's proposed mutation to create a new validated Claim instance.
    Uses exact integer paise arithmetic to guarantee arithmetic self-consistency.
    """
    mutated = deepcopy(base_claim)
    mutated.claim_id = f"{base_claim.claim_id}-D{round_num}"

    # Apply diagnosis upcoding/mutation if proposed by fraudster
    if mutation.diagnosis_code:
        mutated.diagnosis_code = mutation.diagnosis_code

    # Build mutated line items
    new_line_items = []
    total_amount_paise = 0

    if mutation.line_item_mutations:
        for idx, item_data in enumerate(mutation.line_item_mutations):
            desc = item_data.get("description", f"Line Item {idx+1}")
            qty = float(item_data.get("qty", 1.0))
            unit_price = float(item_data.get("unit_price", 0.0))
            amt = round(unit_price * qty, 2)
            total_amount_paise += to_paise(amt)

            new_line_items.append(LineItem(
                description=desc,
                qty=qty,
                unit_price=unit_price,
                amount=amt,
                page=1,
                source="duel_fraudster"
            ))
    else:
        # Default inflation if empty
        multiplier = max(1.20, mutation.target_multiplier)
        for idx, it in enumerate(mutated.line_items or []):
            new_unit = round(it.unit_price * multiplier, 2)
            new_amt = round(new_unit * it.qty, 2)
            total_amount_paise += to_paise(new_amt)
            new_line_items.append(LineItem(
                description=it.description,
                qty=it.qty,
                unit_price=new_unit,
                amount=new_amt,
                bbox=it.bbox,
                page=it.page,
                source="duel_fraudster"
            ))

    mutated.line_items = new_line_items
    mutated.subtotal = to_rupees(total_amount_paise)
    mutated.tax = 0.0  # Healthcare services in India are typically GST-exempt
    mutated.total_claimed = mutated.subtotal

    # Update metadata to track synthetic adversarial lineage
    if not mutated.metadata:
        mutated.metadata = {}
    mutated.metadata["duel_id"] = duel_id
    mutated.metadata["duel_round"] = round_num
    mutated.metadata["adversarial_tactic"] = mutation.tactic
    mutated.metadata["adversarial_marker"] = "FINSHIELD-SYNTHETIC-DEMO"
    mutated.source = "duel"

    return mutated


def run_duel(
    base_claim: Claim,
    max_rounds: int = 5,
    duel_id: Optional[str] = None
) -> DuelResult:
    """
    Executes a multi-round adversarial duel:
      - Fraudster: ADK LlmAgent / adversarial mutator.
      - Defender: real run_claims_fraud_pipeline.
      - Up to 5 rounds.
      - On evasion, registers the tactic into BigQuery / Firestore learned_patterns,
        making it immediately retrievable by the RAG pattern agent.
      - In subsequent rounds, the defender uses the newly learned pattern to catch the evasion tactic.
    """
    duel_id = duel_id or f"DUEL-{uuid.uuid4().hex[:8].upper()}"
    baseline_amount = float(base_claim.total_claimed)
    rounds: List[DuelRound] = []
    learned_pattern: Optional[Dict[str, Any]] = None
    winning_side = "defender"
    status = "max_rounds_reached"

    logger.info("Starting Duel %s: Base Claim %s (Baseline ₹%.2f, Max %d rounds)",
                duel_id, base_claim.claim_id, baseline_amount, max_rounds)

    for round_num in range(1, max_rounds + 1):
        # 1. Fraudster proposes mutation via Gemini Pro
        mutation = _generate_adversarial_mutation_gemini(base_claim, rounds, round_num)
        if not mutation:
            from backend.app.exceptions import CloudServiceError
            raise CloudServiceError(
                service="Gemini",
                message="Fraudster agent failed to propose a valid adversarial mutation.",
                retryable=True
            )

        # 2. Apply mutation to produce candidate claim
        candidate_claim = apply_mutation_to_claim(base_claim, mutation, round_num, duel_id)
        db_service.save_claim(candidate_claim)

        # 3. Defender scrutinizes claim using the full multi-agent pipeline
        dossier: Dossier = run_claims_fraud_pipeline(candidate_claim)

        # 4. Evaluate outcome
        verdict_str = dossier.verdict.value if isinstance(dossier.verdict, Verdict) else str(dossier.verdict)
        verdict_str = verdict_str.upper()
        mutated_total = float(candidate_claim.total_claimed)
        inflation_ratio = round(mutated_total / max(1.0, baseline_amount), 3)

        # Finding IDs and check IDs that caught the claim
        catching_findings = [
            f for f in dossier.findings
            if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        ]
        catching_ids = [f.finding_id for f in catching_findings]
        catching_checks = [f.check_id for f in catching_findings]

        # Evasion criteria: Defender approved AND payout is at least 20% above baseline
        evaded = (verdict_str == "APPROVE" and mutated_total >= baseline_amount * 1.20)
        caught = not evaded

        duel_round = DuelRound(
            round_number=round_num,
            tactic=mutation.tactic,
            rationale=mutation.rationale,
            claim_id=candidate_claim.claim_id,
            baseline_amount=baseline_amount,
            total_claimed=mutated_total,
            inflation_ratio=inflation_ratio,
            verdict=verdict_str,
            risk_score=dossier.risk_score,
            caught=caught,
            evaded=evaded,
            catching_finding_ids=catching_ids,
            catching_check_ids=catching_checks
        )
        rounds.append(duel_round)

        # Persist round to Firestore and DB
        db_service.save_duel_round(duel_id, round_num, duel_round.model_dump())

        logger.info("Duel %s Round %d: Tactic='%s', Total=₹%.2f (%.1fx), Verdict=%s, Risk=%.1f, Caught=%s",
                    duel_id, round_num, mutation.tactic, mutated_total, inflation_ratio, verdict_str, dossier.risk_score, caught)

        # 5. Handle Evasion Event: register learned evasion pattern into BigQuery, Firestore, and RAG catalog
        if evaded:
            if not learned_pattern:
                pattern_id = f"PAT-LEARNED-{uuid.uuid4().hex[:8].upper()}"
                learned_card = {
                    "pattern_id": pattern_id,
                    "fraud_type": "learned_evasion",
                    "title": f"Learned Evasion: {mutation.tactic[:60]}",
                    "tactic": mutation.tactic,
                    "narrative": (
                        f"Evasion tactic observed in adversarial duel {duel_id} (Round {round_num}). "
                        f"Fraudster inflated claim by {int((inflation_ratio-1)*100)}% to ₹{mutated_total:.2f}. "
                        f"Rationale: {mutation.rationale}"
                    ),
                    "signature": f"{mutation.tactic} total_claimed:{mutated_total:.0f} diagnosis_code:{candidate_claim.diagnosis_code}",
                    "feature_signatures": {
                        "tactic": mutation.tactic,
                        "inflation_ratio": inflation_ratio,
                        "manipulation_type": mutation.manipulation_type,
                        "diagnosis_code": candidate_claim.diagnosis_code
                    },
                    "typical_severity": "HIGH",
                    "evaded_at": datetime.utcnow().isoformat()
                }
                learned_pattern = register_learned_pattern(learned_card)
                logger.info("Learned Evasion Pattern Registered: %s (%s)", pattern_id, mutation.tactic)
            # Do NOT break: proceed to next round so Defender pipeline demonstrates catching the evasion tactic

    # Determine winner & status:
    # If the fraudster successfully evaded in the final round, fraudster wins.
    # Otherwise, if the defender caught the fraudster in the final round (demonstrating the catch loop), defender wins!
    if rounds and rounds[-1].evaded:
        winning_side = "fraudster"
        status = "evaded"
    else:
        winning_side = "defender"
        status = "completed" if learned_pattern else "caught"

    return DuelResult(
        duel_id=duel_id,
        base_claim_id=base_claim.claim_id,
        baseline_amount=baseline_amount,
        max_rounds=max_rounds,
        rounds=rounds,
        status=status,
        winning_side=winning_side,
        learned_pattern=learned_pattern
    )
