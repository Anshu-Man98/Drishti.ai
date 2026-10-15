"""
Acceptance test suite for Feature A3: Deterministic Math Validator via Function Calling.
Validates:
1. Property test: 500 randomly generated line-item sets verify that validate_arithmetic
   agrees with a plain Python integer paise sum.
2. Grounding guard test: asserts fabricated numerical figures are caught and reported.
3. Regression test: runs all golden demo claims (G1-G6) 3 consecutive times,
   asserting identical risk_score, verdict, and set of finding check_ids on every run.
4. Tool-call audit test: verifies that G2's pipeline logs an explicit structured function call
   to validate_arithmetic with hashes, latency, and arguments.
5. Golden claim G2 paise-accurate chip test: verifies computed_chip contains exact paise-level numbers.
"""

import json
import random
from pathlib import Path
import pytest

from backend.tools.registry import (
    validate_arithmetic,
    to_paise,
    to_rupees,
    call_tool,
    get_tool_audit_transcript,
    get_all_computed_values
)
from backend.tools.grounding import assert_numbers_grounded, sanitize_text_grounding
from backend.tools.docai import process_document_docai
from backend.agents.root import run_claims_fraud_pipeline
from backend.app.schemas import Claim, Finding, Severity, AgentName
from backend.app.services.db import db_service

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "data" / "demo"
GROUND_TRUTH_PATH = DEMO_DIR / "ground_truth.json"


# ==============================================================================
# 1. PROPERTY TEST: 500 RANDOMLY GENERATED LINE-ITEM SETS
# ==============================================================================

def test_property_500_random_line_items_arithmetic_agreement():
    """
    Property test: For 500 randomly generated line-item sets, validate_arithmetic
    agrees with a plain Python sum. Deterministic, integer-paise accurate, zero floats for money.
    """
    random.seed(42)

    for run_idx in range(500):
        num_items = random.randint(1, 15)
        line_items = []
        expected_subtotal_paise = 0

        for i in range(num_items):
            qty = random.randint(1, 10)
            # Unit price in rupees with 2 decimals
            unit_price_rupees = round(random.uniform(50.0, 5000.0), 2)
            unit_price_paise = to_paise(unit_price_rupees)
            amount_paise = qty * unit_price_paise
            expected_subtotal_paise += amount_paise

            line_items.append({
                "description": f"Item {i+1}",
                "qty": qty,
                "unit_price": unit_price_rupees,
                "amount": to_rupees(amount_paise)
            })

        subtotal_rupees = to_rupees(expected_subtotal_paise)
        tax_rupees = round(subtotal_rupees * 0.18, 2)
        tax_paise = to_paise(tax_rupees)
        total_paise = expected_subtotal_paise + tax_paise
        total_rupees = to_rupees(total_paise)

        # Run validate_arithmetic
        res = validate_arithmetic(
            line_items=line_items,
            subtotal=subtotal_rupees,
            tax=tax_rupees,
            total=total_rupees
        )

        # In a consistent bill, it must match
        assert res["valid"] is True, f"Failed on iteration {run_idx}: expected match"
        assert res["match"] is True
        assert len(res["findings"]) == 0

        # Computed numbers must strictly match the Python sum
        computed = res["computed"]
        assert computed["line_item_sum_paise"] == expected_subtotal_paise
        assert computed["stated_total_paise"] == total_paise
        assert computed["difference_paise"] <= res["tolerance_paise"]


def test_property_line_items_deliberate_mismatch_detected():
    """Verifies that tampering with a line item by 10 INR is flagged deterministically."""
    line_items = [
        {"description": "Medicine A", "qty": 2, "unit_price": 500.0, "amount": 1000.0},
        {"description": "Medicine B", "qty": 1, "unit_price": 750.0, "amount": 750.0}
    ]
    # Correct sum is 1,750. We claim 1,760 (+10 INR inflation)
    res = validate_arithmetic(
        line_items=line_items,
        subtotal=1760.0,
        tax=0.0,
        total=1760.0
    )
    assert res["valid"] is False
    assert res["match"] is False
    assert len(res["findings"]) >= 1
    assert res["computed"]["difference"] == 10.0
    assert res["computed"]["difference_paise"] == 1000


# ==============================================================================
# 2. NUMERIC GROUNDING GUARD TESTS
# ==============================================================================

def test_grounding_guard_catches_fabricated_number():
    """
    Grounding test: feed the guard a summary containing a fabricated figure
    (e.g., ₹45,000 when actual was ₹17,475) and assert it is caught.
    """
    tool_outputs = {
        "computed": {
            "line_item_sum": 90500.0,
            "stated_total": 112500.0,
            "difference": 17475.0,
            "stated_tax": 4525.0,
            "expected_total": 95025.0
        }
    }

    # Case A: Honest summary with only legitimate computed numbers
    honest_summary = (
        "Audit completed. Line item sum is ₹90,500 (+₹4,525 tax = ₹95,025), "
        "resulting in a discrepancy of ₹17,475 against claimed total ₹1,12,500 [F1]."
    )
    res_honest = assert_numbers_grounded(honest_summary, tool_outputs)
    assert res_honest["grounded"] is True
    assert len(res_honest["ungrounded"]) == 0

    # Case B: Hallucinated / Fabricated figure: ₹45,000
    hallucinated_summary = (
        "Audit completed. The claimant engaged in systematic fraud with an unapproved "
        "inflation of ₹45,000 across multiple department bills."
    )
    res_hallucinated = assert_numbers_grounded(hallucinated_summary, tool_outputs)
    assert res_hallucinated["grounded"] is False
    assert len(res_hallucinated["ungrounded"]) >= 1
    assert any("45,000" in item["value"] or item["numeric_value"] == 45000.0 for item in res_hallucinated["ungrounded"])

    # Test sanitization strips the offending sentence
    sanitized, ungrounded_items = sanitize_text_grounding(hallucinated_summary, tool_outputs)
    assert "₹45,000" not in sanitized
    assert len(ungrounded_items) >= 1


def test_grounding_guard_whitelists_finding_ids_and_policy_clauses():
    """Verifies that non-factual numbers like [F3], Clause 3.1, or year 2026 are whitelisted."""
    tool_outputs = {"computed": {"risk_score": 60}}
    text = "Under Clause 3.1, finding [F3] was flagged in the 2026 policy review for 1st instance violation."

    res = assert_numbers_grounded(text, tool_outputs)
    assert res["grounded"] is True, f"Expected whitelisted references to pass, got: {res['ungrounded']}"


# ==============================================================================
# 3. TOOL-CALL AUDIT TEST (G2 TRANSCRIPT)
# ==============================================================================

def test_tool_call_audit_on_g2_claim():
    """
    Tool-call audit test: assert that for G2 the Arithmetic agent's transcript
    contains an actual function call to validate_arithmetic with hashes and latency.
    """
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    g2_info = gt["G2"]
    pdf_path = DEMO_DIR / g2_info["file"]
    claim_id = "CLM-G2-A3-AUDIT"

    claim, _ = process_document_docai(pdf_path.read_bytes(), filename=g2_info["file"], claim_id=claim_id)
    dossier = run_claims_fraud_pipeline(claim)

    # Inspect the central tool audit transcript for this claim
    transcript = get_tool_audit_transcript(claim_id)
    assert len(transcript) >= 1, "Expected tool audit transcript to contain calls"

    # Find the validate_arithmetic call
    arith_call = next((call for call in transcript if call["tool"] == "validate_arithmetic"), None)
    assert arith_call is not None, "Transcript must record explicit validate_arithmetic function call"

    # Verify structured logging schema: claim_id, agent, tool, args_hash, result_hash, latency_ms
    assert arith_call["claim_id"] == claim_id
    assert arith_call["agent"] == "policy"
    assert "args_hash" in arith_call
    assert "result_hash" in arith_call
    assert "latency_ms" in arith_call
    assert arith_call["latency_ms"] >= 0.0

    # Verify G2's arithmetic finding carries computed_chip with exact paise-level numbers
    math_finding = next((f for f in dossier.findings if "TOTAL" in f.check_id or "SUBTOTAL" in f.check_id), None)
    assert math_finding is not None
    assert math_finding.computed_chip is not None
    assert "112,500" in math_finding.computed_chip
    assert "17,475" in math_finding.computed_chip or "90,500" in math_finding.computed_chip


# ==============================================================================
# 4. REGRESSION TEST: 3 CONSECUTIVE RUNS OF ALL GOLDEN DEMO CLAIMS
# ==============================================================================

@pytest.mark.parametrize("golden_key", ["G1", "G2", "G3", "G4", "G5", "G6"])
def test_regression_three_runs_identical_score_and_findings(golden_key: str):
    """
    Regression test: run all golden claims 3 consecutive times;
    assert identical risk_score, verdict, and set of finding check_ids each time.
    """
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    info = gt[golden_key]
    pdf_path = DEMO_DIR / info["file"]

    results = []

    for run_i in range(3):
        claim_id = f"CLM-{golden_key}-A3-RUN{run_i+1}"
        claim, _ = process_document_docai(pdf_path.read_bytes(), filename=info["file"], claim_id=claim_id)
        dossier = run_claims_fraud_pipeline(claim)

        finding_check_ids = sorted([f.check_id for f in dossier.findings if f.severity != Severity.INFO])
        results.append({
            "risk_score": dossier.risk_score,
            "verdict": dossier.verdict.value,
            "check_ids": finding_check_ids
        })

    # Verify run 1 == run 2 == run 3
    assert results[0]["risk_score"] == results[1]["risk_score"] == results[2]["risk_score"], (
        f"Non-deterministic risk score on {golden_key}: {results}"
    )
    assert results[0]["verdict"] == results[1]["verdict"] == results[2]["verdict"], (
        f"Non-deterministic verdict on {golden_key}: {results}"
    )
    assert results[0]["check_ids"] == results[1]["check_ids"] == results[2]["check_ids"], (
        f"Non-deterministic findings on {golden_key}: {results}"
    )
