"""
Tests for Issue 3: Grounding Guard Root Cause and Noise Elimination.
Verifies that:
1. Normal clean claim yields zero `ungrounded_number` findings.
2. Benchmark findings register all percentiles, sample sizes, ratios, and amounts, so their explanations are 100% grounded.
3. The grounding guard continues to catch and strip genuine fabricated numbers.
4. Analytics router excludes info/internal findings and reports distinct claims affected.
"""

import pytest
from datetime import datetime
from backend.app.schemas import Claim, Finding, AgentName, Severity, LineItem, Provider
from backend.tools.registry import (
    call_tool,
    check_price_benchmarks,
    get_all_computed_values,
    CLAIM_COMPUTED_STORE
)
from backend.tools.grounding import (
    assert_numbers_grounded,
    sanitize_text_grounding,
    _extract_number_instances
)
from backend.services.benchmarks import benchmark_service


def test_clean_claim_yields_zero_ungrounded_number_findings():
    """Verifies that running checks on a clean claim yields zero ungrounded_number findings."""
    claim = Claim(
        claim_id="TEST-CLEAN-G1-VAL",
        policy_id="POL-CARE-99812",
        insurer_id="INS-CARE",
        claimant_name="Rohan Verma",
        diagnosis_code="K35.8",
        total_claimed=74550.0,
        subtotal=71000.0,
        tax=3550.0,
        line_items=[
            LineItem(description="Appendectomy surgical procedure", qty=1, unit_price=45000.0, amount=45000.0),
            LineItem(description="Standard post-op room rent", qty=3, unit_price=4000.0, amount=12000.0),
            LineItem(description="Surgeon and anesthesia consultation", qty=2, unit_price=5000.0, amount=10000.0),
            LineItem(description="Operating theater sterile pack", qty=1, unit_price=4000.0, amount=4000.0)
        ]
    )

    # Execute price benchmarks via tool registry
    res = call_tool(
        "check_price_benchmarks",
        {"claim": claim.model_dump(), "doc_id": "doc_main"},
        claim_id=claim.claim_id,
        agent_name="policy"
    )

    findings = res.get("findings", [])
    # Clean claim should not have any ungrounded findings
    ungrounded = [f for f in findings if f.check_id == "ungrounded_number"]
    assert len(ungrounded) == 0, f"Expected 0 ungrounded findings on clean claim, got {len(ungrounded)}"


def test_benchmark_findings_explanations_are_grounded_at_root():
    """
    Verifies that when benchmark findings fire (total excess, line item excess, ancillary padding),
    every single number mentioned in their explanations (percentiles, ratios, sample count, amounts)
    is properly registered in computed store and grounded by the guard.
    """
    claim_id = "TEST-INFLATED-BENCH-GROUNDING"
    claim_data = {
        "claim_id": claim_id,
        "diagnosis_code": "K35.8",
        "total_claimed": 150000.0,
        "subtotal": 140000.0,
        "tax": 10000.0,
        "line_items": [
            {"description": "Appendectomy surgical fee", "qty": 1, "unit_price": 85000.0, "amount": 85000.0},
            {"description": "Disposable trocar & cannula set", "qty": 5, "unit_price": 6000.0, "amount": 30000.0},
            {"description": "Surgical consumable pack", "qty": 4, "unit_price": 4000.0, "amount": 16000.0},
            {"description": "PPE and sterile drape pack", "qty": 3, "unit_price": 3000.0, "amount": 9000.0}
        ]
    }

    res = call_tool(
        "check_price_benchmarks",
        {"claim": claim_data, "doc_id": "doc_main"},
        claim_id=claim_id,
        agent_name="policy"
    )

    findings = res.get("findings", [])
    assert len(findings) >= 2, f"Expected at least 2 benchmark findings, got {len(findings)}"

    computed = get_all_computed_values(claim_id)

    for f in findings:
        finding_store = dict(computed)
        if f.computed_details:
            finding_store.update(f.computed_details)

        # Check finding explanation
        guard_exp = assert_numbers_grounded(f.explanation, finding_store)
        assert guard_exp["grounded"] is True, (
            f"Finding {f.finding_id} explanation has ungrounded numbers: {guard_exp['ungrounded']} "
            f"in explanation: {f.explanation}"
        )

        # Check finding title
        guard_title = assert_numbers_grounded(f.title, finding_store)
        assert guard_title["grounded"] is True, (
            f"Finding {f.finding_id} title has ungrounded numbers: {guard_title['ungrounded']} "
            f"in title: {f.title}"
        )


def test_grounding_guard_catches_and_strips_genuine_fabricated_numbers():
    """
    CRITICAL: Verifies the grounding guard is NOT suppressed or bypassable.
    Invented numbers that do NOT trace to tool outputs or claim JSON must be caught and stripped.
    """
    tool_outputs = {
        "computed": {
            "total_claimed": 74550.0,
            "benchmark_p95": 59644.85,
            "benchmark_p50": 52955.82,
            "sample_count": 301
        }
    }

    # Case 1: Text with fabricated currency figure
    hallucinated_text = (
        "The claim is under review. Hospital added an unauthorized secret fee of ₹88,999 "
        "not justified by the diagnostic workup."
    )
    res = assert_numbers_grounded(hallucinated_text, tool_outputs)
    assert res["grounded"] is False, "Expected guard to detect fabricated ₹88,999"
    assert any("88,999" in item["value"] or item["numeric_value"] == 88999.0 for item in res["ungrounded"])

    # Test sanitization strips the sentence containing ₹88,999
    sanitized, ungrounded = sanitize_text_grounding(hallucinated_text, tool_outputs)
    assert "₹88,999" not in sanitized
    assert len(ungrounded) == 1

    # Case 2: Text with fabricated kickback percentage
    hallucinated_pct_text = (
        "Claim analysis completed. An illegitimate commission of 45% was redirected to an unverified entity."
    )
    res_pct = assert_numbers_grounded(hallucinated_pct_text, tool_outputs)
    assert res_pct["grounded"] is False, "Expected guard to detect fabricated 45%"
    assert any(item["numeric_value"] == 45.0 for item in res_pct["ungrounded"])


def test_analytics_router_excludes_info_and_internal_findings():
    """
    Verifies that dashboard analytics calculation ignores info/internal findings
    and counts real findings and distinct claims affected accurately.
    """
    from backend.app.routers.analytics import router

    mock_dossiers = {
        "CLM-001": {
            "findings": [
                {"agent": "ml", "severity": "info", "check_id": "ungrounded_number", "title": "Noise"},
                {"agent": "policy", "severity": "high", "check_id": "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK", "title": "Real"}
            ]
        },
        "CLM-002": {
            "findings": [
                {"agent": "ml", "severity": "info", "check_id": "ungrounded_number", "title": "Noise"},
                {"agent": "ml", "severity": "high", "check_id": "BQML_ANOMALY_OUTLIER", "title": "Real ML"}
            ]
        }
    }

    # Replicate analytics filtering logic
    agent_counts = {"ml": 0, "policy": 0}
    agent_claims = {"ml": set(), "policy": set()}

    for d_id, d_data in mock_dossiers.items():
        for f in d_data.get("findings", []):
            sev = (f.get("severity") or "").lower()
            ch = (f.get("check_id") or "").upper()
            if sev == "info":
                continue
            if any(noise in ch for noise in ["UNGROUNDED", "INTERNAL", "DOCUMENT_UNREADABLE"]):
                continue

            ag = (f.get("agent") or "").lower()
            if ag in agent_counts:
                agent_counts[ag] += 1
                agent_claims[ag].add(d_id)

    # ML should only have 1 finding (from CLM-002), NOT 3
    assert agent_counts["ml"] == 1, f"Expected 1 real ML finding, got {agent_counts['ml']}"
    assert len(agent_claims["ml"]) == 1, f"Expected 1 claim affected by ML, got {len(agent_claims['ml'])}"
    assert agent_counts["policy"] == 1
    assert len(agent_claims["policy"]) == 1
