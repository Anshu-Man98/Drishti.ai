"""
Acceptance test suite for F6: Dueling AI (Adversarial Red-Team Fraudster vs. FinShield Defender).

Validates:
1. Fraudster Agent: ADK LlmAgent initialization and configuration with GEMINI_PRO_MODEL.
2. Mutation Integrity: Exact integer paise arithmetic preserved on all adversarial mutations.
3. Multi-Round Adversarial Duel:
   - Runs rounds sequentially with real Defender pipeline (run_claims_fraud_pipeline).
   - Records each round's tactic, rationale, total claimed, inflation ratio, verdict, and catching checks.
   - Persists each round in db_service (Firestore / SQLite).
4. Evasion Detection & Learning Feedback Loop:
   - Evasion triggers when defender verdict is APPROVE and total_claimed >= baseline * 1.20.
   - Extracts tactic, registers learned pattern into BigQuery / Firestore.
   - Immediately retrievable by RAG pattern agent (search_patterns).
5. Fast and clean execution without hardcoded demo transcripts.
"""

import json
from pathlib import Path
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import (
    Claim, Claimant, Provider, LineItem, Verdict, Severity
)
from backend.app.services.db import db_service
from backend.agents.duel import (
    create_fraudster_agent,
    apply_mutation_to_claim,
    run_duel,
    FraudsterMutationOutput,
    DuelResult
)
from backend.tools.pattern_tools import (
    search_patterns,
    register_learned_pattern,
    load_pattern_cards
)
from backend.tools.registry import to_paise, to_rupees

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "data" / "demo"
GROUND_TRUTH_PATH = DEMO_DIR / "ground_truth.json"

client = TestClient(app)


@pytest.fixture
def clean_base_claim() -> Claim:
    """Provides a synthetic authentic base claim for duel testing."""
    return Claim(
        claim_id="CLM-G1-DUEL-BASE",
        policy_id="POL-CARE-CLASSIC-001",
        insurer_id="INS-CARE-HEALTH",
        claimant=Claimant(
            claimant_id="C-101",
            name="Aarav Mehta",
            phone="+91-9876543210",
            bank_account_hash="1122334455667788",
            age=42,
            gender="Male"
        ),
        provider=Provider(
            hospital_id="H-101",
            name="Apollo Hospitals Mumbai",
            city="Mumbai",
            lat=19.0178,
            lng=72.8478
        ),
        doctor_id="DOC-501",
        admission_ts=datetime(2026, 7, 10, 10, 0),
        discharge_ts=datetime(2026, 7, 12, 14, 0),
        diagnosis_code="A09.9",
        line_items=[
            LineItem(
                item_id="ITM-1",
                description="Consultation charges - Specialist",
                qty=2.0,
                unit_price=2000.0,
                amount=4000.0,
                category="consultation"
            ),
            LineItem(
                item_id="ITM-2",
                description="Semi-Private Twin Sharing Room Rent",
                qty=2.0,
                unit_price=3500.0,
                amount=7000.0,
                category="room_rent"
            ),
            LineItem(
                item_id="ITM-3",
                description="Routine Hematology and Metabolic Panel",
                qty=1.0,
                unit_price=3500.0,
                amount=3500.0,
                category="investigations"
            ),
            LineItem(
                item_id="ITM-4",
                description="IV Fluids and Essential Antibiotics",
                qty=1.0,
                unit_price=4500.0,
                amount=4500.0,
                category="pharmacy"
            )
        ],
        subtotal=19000.0,
        tax=0.0,
        total_claimed=19000.0
    )


# ==============================================================================
# 1. ADK FRAUDSTER AGENT INITIALIZATION
# ==============================================================================

def test_fraudster_agent_adk_initialization():
    """Validates ADK Fraudster LlmAgent construction and configuration."""
    agent = create_fraudster_agent()
    assert agent.name == "fraudster_agent"
    assert "adversarial" in agent.instruction.lower() or "fraud" in agent.instruction.lower()
    assert agent.output_key == "fraudster_mutation"


# ==============================================================================
# 2. ADVERSARIAL MUTATION INTEGER ARITHMETIC INTEGRITY
# ==============================================================================

def test_apply_mutation_preserves_arithmetic_consistency(clean_base_claim):
    """
    Verifies that when a fraudster mutates a claim, line item totals and subtotals
    are strictly balanced in integer paise to avoid trivial arithmetic flaws.
    """
    mutation = FraudsterMutationOutput(
        tactic="Subtle Line-Item Padding with Strict Arithmetic",
        rationale="Inflate line items by 25% while maintaining exact subtotal balance",
        target_multiplier=1.25,
        line_item_mutations=[
            {"description": "Specialist Consult", "qty": 2.0, "unit_price": 2500.0, "amount": 5000.0, "category": "consultation"},
            {"description": "Room Rent", "qty": 2.0, "unit_price": 4375.0, "amount": 8750.0, "category": "room_rent"},
            {"description": "Diagnostic Panel", "qty": 1.0, "unit_price": 4375.0, "amount": 4375.0, "category": "investigations"},
            {"description": "Pharmacy & Fluids", "qty": 1.0, "unit_price": 5625.0, "amount": 5625.0, "category": "pharmacy"}
        ],
        manipulation_type="subtle_padding"
    )

    mutated = apply_mutation_to_claim(clean_base_claim, mutation, round_num=1, duel_id="DUEL-TEST-1")

    assert mutated.claim_id == "CLM-G1-DUEL-BASE-D1"
    assert len(mutated.line_items) == 4

    # Strict paise sum verification
    sum_paise = sum(to_paise(it.amount) for it in mutated.line_items)
    expected_subtotal = to_rupees(sum_paise)

    assert mutated.subtotal == expected_subtotal
    assert mutated.total_claimed == expected_subtotal
    assert mutated.total_claimed == 23750.0
    assert mutated.total_claimed >= clean_base_claim.total_claimed * 1.20


# ==============================================================================
# 3. MULTI-ROUND ADVERSARIAL DUEL WITH REAL PIPELINE
# ==============================================================================

def test_run_duel_multi_round_execution(clean_base_claim):
    """
    Executes a multi-round duel using the real Defender multi-agent pipeline.
    Validates:
      - Sequential rounds run and produce valid DuelRound objects.
      - Each round runs through the actual FinShield pipeline (yielding a verdict & risk score).
      - Rounds are recorded in db_service.
    """
    db_service.save_claim(clean_base_claim)
    result: DuelResult = run_duel(clean_base_claim, max_rounds=2, duel_id="DUEL-EXEC-TEST")

    assert result.duel_id == "DUEL-EXEC-TEST"
    assert result.baseline_amount == 19000.0
    assert len(result.rounds) >= 1
    assert len(result.rounds) <= 2

    # Verify first round details
    r1 = result.rounds[0]
    assert r1.round_number == 1
    assert r1.baseline_amount == 19000.0
    assert r1.total_claimed > 19000.0
    assert r1.inflation_ratio >= 1.20
    assert r1.verdict in ("APPROVE", "REVIEW", "REJECT")
    assert isinstance(r1.risk_score, (int, float))

    # Verify rounds were persisted in db_service
    saved_rounds = db_service.get_duel_rounds("DUEL-EXEC-TEST")
    assert len(saved_rounds) == len(result.rounds)
    assert saved_rounds[0]["round_number"] == 1


# ==============================================================================
# 4. EVASION & LEARNED PATTERNS FEEDBACK LOOP
# ==============================================================================

def test_learned_pattern_registration_and_retrieval(clean_base_claim):
    """
    Verifies that when a fraudster tactic is learned:
      1. register_learned_pattern saves it into the active catalog and Firestore/DB.
      2. search_patterns immediately retrieves the learned tactic by query/fingerprint.
    """
    tactic_name = "Room Rent Relabeling to High-Tech Continuous Telemetry"
    learned_card = {
        "pattern_id": "PAT-LEARNED-TELEMETRY-99",
        "fraud_type": "learned_evasion",
        "title": f"Learned Evasion: {tactic_name}",
        "tactic": tactic_name,
        "narrative": "Fraudster circumvents statutory room caps by shifting charges to continuous hemodynamic telemetry.",
        "signature": "continuous hemodynamic telemetry room_rent_relabeling non_capped_diagnostics",
        "feature_signatures": {
            "tactic": tactic_name,
            "category_shift": "room_rent -> diagnostics",
            "evaded_round": 2
        },
        "typical_severity": "HIGH",
        "evaded_at": datetime.utcnow().isoformat()
    }

    registered = register_learned_pattern(learned_card)
    assert registered["pattern_id"] == "PAT-LEARNED-TELEMETRY-99"

    # Verify it is in the catalog
    all_cards = load_pattern_cards()
    pids = [c["pattern_id"] for c in all_cards]
    assert "PAT-LEARNED-TELEMETRY-99" in pids

    # Search for this pattern using key tokens from the signature
    results = search_patterns("continuous hemodynamic telemetry non_capped_diagnostics", k=3, min_score=0.4)
    assert len(results) >= 1
    matched_pids = [r["pattern_id"] for r in results]
    assert "PAT-LEARNED-TELEMETRY-99" in matched_pids


# ==============================================================================
# 5. DUEL API ENDPOINT VERIFICATION
# ==============================================================================

def test_duel_api_endpoints(clean_base_claim):
    """
    Tests POST /api/duel/start, GET /api/duel/{id}/rounds, and GET /api/duel/patterns/learned.
    """
    db_service.save_claim(clean_base_claim)

    # 1. Start duel via API
    res = client.post(
        "/api/duel/start?wait=true",
        json={"claim_id": clean_base_claim.claim_id, "rounds": 1},
        headers={"Authorization": "Bearer test-token"}
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    duel_data = res.json()
    assert "duel_id" in duel_data
    assert len(duel_data["rounds"]) == 1
    duel_id = duel_data["duel_id"]

    # 2. Query rounds via API
    rounds_res = client.get(
        f"/api/duel/{duel_id}/rounds",
        headers={"Authorization": "Bearer test-token"}
    )
    assert rounds_res.status_code == 200
    rounds_data = rounds_res.json()
    assert len(rounds_data) == 1
    assert rounds_data[0]["round_number"] == 1

    # 3. Query learned patterns via API
    patterns_res = client.get(
        "/api/duel/patterns/learned",
        headers={"Authorization": "Bearer test-token"}
    )
    assert patterns_res.status_code == 200
    patterns_data = patterns_res.json()
    assert isinstance(patterns_data, list)


def test_duel_start_without_claim_id_picks_authentic_claim(clean_base_claim):
    """
    Regression test: POST /api/duel/start with no claim_id must pick an authentic claim
    from the database (resolving full Claim object, not ClaimSummary) and return 200 OK.
    """
    db_service.save_claim(clean_base_claim)

    res = client.post(
        "/api/duel/start?wait=true",
        json={"rounds": 1},
        headers={"Authorization": "Bearer test-token"}
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    duel_data = res.json()
    assert "duel_id" in duel_data
    assert len(duel_data["rounds"]) == 1
    assert duel_data["rounds"][0]["baseline_amount"] == clean_base_claim.total_claimed


def test_adversarial_evasion_learning_loop_e2e(clean_base_claim):
    """
    Validates the complete 'evade -> learn -> catch' adversarial cycle:
      - Round 1: Fraudster attempts naive inflation -> Caught by baseline checks.
      - Round 2: Fraudster executes tariff arbitrage / upcoding -> Evades detection (verdict == APPROVE, >= 1.2x).
      - Feedback loop: Evasion tactic is extracted and registered into learned_patterns catalog.
      - Round 3: Fraudster repeats/refines the tactic -> Caught by Defender's RAG agent matching the newly learned pattern.
      - Outcome: Defender wins overall after learning and neutralizing the evasive strategy.
    """
    db_service.save_claim(clean_base_claim)
    result: DuelResult = run_duel(clean_base_claim, max_rounds=3, duel_id="DUEL-LEARNING-E2E")

    assert len(result.rounds) == 3
    r1, r2, r3 = result.rounds[0], result.rounds[1], result.rounds[2]

    # Round 1: Caught
    assert r1.caught is True
    assert r1.evaded is False
    assert r1.verdict in ("REVIEW", "REJECT")

    # Round 2: Evaded
    assert r2.evaded is True
    assert r2.caught is False
    assert r2.verdict == "APPROVE"
    assert r2.total_claimed >= clean_base_claim.total_claimed * 1.20

    # Learning Feedback Loop: Pattern successfully registered
    assert result.learned_pattern is not None
    learned_pid = result.learned_pattern["pattern_id"]
    assert learned_pid.startswith("PAT-LEARNED-")

    # Round 3: Caught by the learned pattern
    assert r3.caught is True
    assert r3.evaded is False
    assert r3.verdict in ("REVIEW", "REJECT")
    assert any("matches_known_pattern" in cid or "learned" in cid for cid in r3.catching_check_ids)

    # Defender wins after neutralizing the evasion tactic
    assert result.winning_side == "defender"
    assert result.status == "completed"

