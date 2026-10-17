"""
Tests for Adjuster Chat Copilot Agent benchmark understanding and numeric grounding (Issue 5).
Ensures the chat assistant quotes authentic benchmark values, stated prices, and excess figures,
and does not discard grounded benchmark numbers or tell the adjuster to check external sources.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from backend.app.schemas import (
    Claim, Claimant, Provider, LineItem, Dossier, Finding, Severity, AgentName, Evidence, Verdict
)
from backend.agents.chat import build_case_file_context, stream_chat_response, CHAT_SYSTEM_PROMPT
from backend.tools.grounding import sanitize_text_grounding, assert_numbers_grounded, _extract_number_instances


def _create_sample_g3_claim_and_dossier():
    claim = Claim(
        claim_id="CLM-G3-POLICYCAP-TEST",
        policy_id="POL-AROGYA-33219",
        insurer_id="INS-ICICI",
        claimant=Claimant(claimant_id="CLMNT-6520", name="Vikram Patel", phone="+919876543210", bank_account_hash="hash6520"),
        provider=Provider(hospital_id="HOSP-103", name="Metro Healthcare Institute", city="Bengaluru"),
        admission_ts=datetime(2026, 5, 18, 8, 0),
        discharge_ts=datetime(2026, 5, 22, 12, 0),
        diagnosis_code="K80.2",
        subtotal=126500.0,
        tax=6325.0,
        total_claimed=132825.0,
        line_items=[
            LineItem(description="Super Deluxe Executive Suite Room (4 days)", qty=4.0, unit_price=14500.0, amount=58000.0),
            LineItem(description="Cholecystectomy Laparoscopic Procedure", qty=1.0, unit_price=42000.0, amount=42000.0),
            LineItem(description="Surgeon & Anesthesia Professional Charges", qty=1.0, unit_price=15000.0, amount=15000.0),
            LineItem(description="OT Consumables & Surgical Disposables", qty=1.0, unit_price=11500.0, amount=11500.0)
        ]
    )

    findings = [
        Finding(
            finding_id="F-POL-ROOM-CAP-1",
            agent=AgentName.POLICY,
            check_id="POLICY_ROOM_RENT_CAP_EXCEEDED",
            severity=Severity.HIGH,
            title="Room rent charges exceed policy cap (Clause 3.1)",
            explanation="Room rent billed at ₹14,500.00/day for 4 days exceeds the eligible limit of ₹5,000.00/day by ₹9,500.00/day (Total inadmissible room rent: ₹38,000.00).",
            evidence=[
                Evidence(doc_id="doc1", page=1, quote="Super Deluxe Executive Suite Room (4 days): billed ₹14500.0/day vs cap ₹5000.0/day")
            ],
            confidence=1.0,
            computed_details={
                "room_rent_billed": 14500.0,
                "room_rent_cap": 5000.0,
                "excess_per_day": 9500.0,
                "room_rent_days": 4.0,
                "total_excess": 38000.0
            }
        ),
        Finding(
            finding_id="F-BENCH-TOTAL-P95",
            agent=AgentName.POLICY,
            check_id="TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
            severity=Severity.HIGH,
            title="Total claim amount exceeds diagnosis benchmark (+86% above p95)",
            explanation="Total claimed amount of ₹132,825.00 is 86% above the 95th percentile benchmark (₹71,473.04) and exceeds the effective regional upper band of ₹89,341.30 for diagnosis K80.2.",
            evidence=[
                Evidence(doc_id="doc1", page=1, quote="Total claimed: ₹132,825.00 vs diagnosis K80.2 benchmark p95=₹71,473.04")
            ],
            confidence=0.95,
            computed_details={
                "total_claimed": 132825.0,
                "benchmark_p95": 71473.04,
                "widened_upper_band": 89341.30,
                "pct_above_p95": 85.8,
                "pct_above_p95_int": 86,
                "excess_rupees": 43483.70
            }
        ),
        Finding(
            finding_id="F-BENCH-ITEM-1",
            agent=AgentName.POLICY,
            check_id="LINE_ITEM_PRICE_ABOVE_BENCHMARK",
            severity=Severity.LOW,
            title="Line item unit price exceeds benchmark: Super Deluxe Executive Suite Room (4 days)",
            explanation="Unit price of ₹14,500.00 for 'Super Deluxe Executive Suite Room (4 days)' is 202% above the 95th percentile benchmark of ₹4,800.00.",
            evidence=[
                Evidence(doc_id="doc1", page=1, quote="Super Deluxe Executive Suite Room: billed unit price ₹14,500.00 vs p95 ₹4,800.00")
            ],
            confidence=0.95,
            computed_details={
                "description": "Super Deluxe Executive Suite Room (4 days)",
                "category": "room_rent",
                "unit_price": 14500.0,
                "benchmark_unit_p95": 4800.0,
                "widened_unit_upper_band": 6000.0,
                "pct_above_p95": 202,
                "line_excess_rupees": 34000.0
            }
        )
    ]

    dossier = Dossier(
        claim_id=claim.claim_id,
        risk_score=65,
        verdict=Verdict.REVIEW,
        summary="Audit completed for Claim CLM-G3-POLICYCAP-TEST with combined risk score 65/100 (REVIEW).",
        findings=findings
    )

    return claim, dossier


def test_build_case_file_context_contains_benchmarks_and_computed_details():
    """Context assembly must include itemized benchmark statuses, computed details, and regional upper bands."""
    claim, dossier = _create_sample_g3_claim_and_dossier()
    ctx, finding_map = build_case_file_context(claim, dossier)

    # 1. Finding lookup map includes aliases and finding_ids
    assert "F1" in finding_map
    assert "F-BENCH-TOTAL-P95" in finding_map
    assert "F-BENCH-ITEM-1" in finding_map

    # 2. Line items include category benchmarks and status
    assert "Super Deluxe Executive Suite Room" in ctx
    assert "room_rent" in ctx
    assert "₹4,800.00" in ctx or "Benchmark p95" in ctx

    # 3. Finding computed details are serialized
    assert "Computed Details:" in ctx
    assert "benchmark_p95" in ctx or "71,473.04" in ctx
    assert "line_excess_rupees" in ctx or "34,000.00" in ctx

    # 4. Regional Upper Band is present
    assert "Regional Upper Band" in ctx or "regional upper band" in ctx


def test_chat_numeric_grounding_preserves_valid_benchmark_quotations():
    """Grounding guard must not strip benchmark statistics when computed_details and context numbers are provided."""
    claim, dossier = _create_sample_g3_claim_and_dossier()
    ctx, _ = build_case_file_context(claim, dossier)

    computed_store = {}
    for f in dossier.findings:
        if f.computed_details:
            computed_store.update(f.computed_details)
    for inst in _extract_number_instances(ctx):
        computed_store[f"ctx_{inst['raw']}"] = inst["value"]

    valid_response = (
        "Total claimed amount of ₹132,825.00 exceeds the 95th percentile benchmark of ₹71,473.04 [F-BENCH-TOTAL-P95]. "
        "The room rent unit price was billed at ₹14,500.00 vs benchmark p95 of ₹4,800.00 and policy cap of ₹5,000.00 [F-BENCH-ITEM-1]."
    )

    sanitized, ungrounded = sanitize_text_grounding(valid_response, computed_store, claim)
    assert len(ungrounded) == 0, f"Expected 0 ungrounded, got: {ungrounded}"
    assert "₹132,825.00" in sanitized
    assert "₹71,473.04" in sanitized
    assert "₹14,500.00" in sanitized
    assert "₹4,800.00" in sanitized
    assert "₹5,000.00" in sanitized


def test_chat_numeric_grounding_suppresses_hallucinated_figures():
    """Grounding guard must still catch and suppress ungrounded/hallucinated numerical claims."""
    claim, dossier = _create_sample_g3_claim_and_dossier()
    ctx, _ = build_case_file_context(claim, dossier)

    computed_store = {}
    for f in dossier.findings:
        if f.computed_details:
            computed_store.update(f.computed_details)
    for inst in _extract_number_instances(ctx):
        computed_store[f"ctx_{inst['raw']}"] = inst["value"]

    hallucinated_response = (
        "The room rent unit price was billed at ₹14,500.00 vs benchmark p95 of ₹4,800.00 [F-BENCH-ITEM-1]. "
        "Additionally, the provider charged an ungrounded penalty fee of ₹777,777.00."
    )

    sanitized, ungrounded = sanitize_text_grounding(hallucinated_response, computed_store, claim)
    assert len(ungrounded) == 1
    assert ungrounded[0]["numeric_value"] == 777777.0
    assert "₹777,777.00" not in sanitized
    assert "₹14,500.00" in sanitized  # Valid sentence remains intact


def test_stream_chat_response_quotes_benchmarks_on_g3():
    """Live/mocked stream_chat_response on G3 must quote benchmarks and cite findings."""
    import asyncio
    claim, dossier = _create_sample_g3_claim_and_dossier()

    with patch("backend.app.services.db.db_service.get_claim", return_value=claim), \
         patch("backend.app.services.db.db_service.get_dossier", return_value=dossier), \
         patch("backend.app.services.db.db_service.save_chat_message"):

        async def _run():
            events = []
            async for ev in stream_chat_response(claim.claim_id, "Which prices were above benchmark and by how much?"):
                events.append(ev)
            return events

        events = asyncio.run(_run())
        final_event = next(ev for ev in events if ev.get("done"))
        ans = final_event["answer"]
        cited = final_event["cited_finding_ids"]

        # Assert answer mentions the excess room rent price and benchmark values
        assert "14,500" in ans or "14500" in ans
        assert "4,800" in ans or "4800" in ans or "5,000" in ans or "5000" in ans
        assert "71,473" in ans or "132,825" in ans or "85" in ans or "86" in ans or "202" in ans

        # Assert finding citations were parsed and returned
        assert len(cited) > 0
        assert any(f_id in cited for f_id in ["F-BENCH-ITEM-1", "F-BENCH-TOTAL-P95", "F-POL-ROOM-CAP-1"])
