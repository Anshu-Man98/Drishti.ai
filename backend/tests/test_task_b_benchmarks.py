"""
backend/tests/test_task_b_benchmarks.py

Unit tests for Task B: Benchmark-Driven Inflation Check & Fallback Hierarchy.
Tests:
  1. BenchmarkService exact -> block -> chapter -> global fallback hierarchy for diagnosis benchmarks.
  2. BenchmarkService category normalization & fallback hierarchy for category benchmarks.
  3. Exact integer paise arithmetic & no floating point rounding errors.
  4. Emission of the 3 new deterministic findings:
     - TOTAL_ABOVE_DIAGNOSIS_BENCHMARK
     - LINE_ITEM_PRICE_ABOVE_BENCHMARK
     - UNBUNDLED_OR_PADDED_ANCILLARY
  5. Inflation scoring guardrail: high inflation forces at least REVIEW.
"""

import pytest
from backend.services.benchmarks import BenchmarkService, DiagnosisBenchmark, CategoryBenchmark
from backend.tools.registry import check_price_benchmarks, to_paise, to_rupees
from backend.tools.scoring import score_findings
from backend.app.schemas import Finding, AgentName, Severity, Verdict


def test_paise_conversion_accuracy():
    """Verify to_paise and to_rupees conversion accuracy with zero floating-point drift."""
    assert to_paise(74550.0) == 7455000
    assert to_paise(95424.35) == 9542435
    assert to_paise(0.01) == 1
    assert to_paise(0.0) == 0

    assert to_rupees(7455000) == 74550.0
    assert to_rupees(9542435) == 95424.35
    assert to_rupees(1) == 0.01


def test_benchmark_service_diagnosis_fallback_hierarchy():
    """Verify exact -> block -> chapter -> global fallback order."""
    service = BenchmarkService()

    # Exact code match
    b_exact = service.get_diagnosis_benchmark("K35.8")
    assert b_exact.diagnosis_code == "K35.8"
    assert b_exact.fallback_level == "exact"
    assert b_exact.p50 > 0

    # 3-char block fallback (e.g. K35.0 -> falls back to K35 block)
    b_block = service.get_diagnosis_benchmark("K35.0")
    assert b_block.diagnosis_code == "K35"
    assert b_block.fallback_level == "block"

    # 1-char chapter fallback (e.g. K99.9 -> falls back to chapter K)
    b_chapter = service.get_diagnosis_benchmark("K99.9")
    assert b_chapter.diagnosis_code == "K"
    assert b_chapter.fallback_level == "chapter"

    # Global fallback for unseen chapter (e.g. Z99.9 -> global)
    b_global = service.get_diagnosis_benchmark("Z99.9")
    assert b_global.diagnosis_code == "GLOBAL"
    assert b_global.fallback_level == "global"


def test_benchmark_service_category_normalization():
    """Verify deterministic regex/keyword taxonomy for hospital line item descriptions."""
    service = BenchmarkService()

    assert service.normalize_line_item_category("Semi-Private Room Rent (3 days)") == "room_rent"
    assert service.normalize_line_item_category("ICU Bed Charges with Ventilator") == "icu"
    assert service.normalize_line_item_category("Laparoscopic Appendectomy Surgery & OT") == "surgery_ot"
    assert service.normalize_line_item_category("Consultant Surgeon & Anesthetist Visit Fees") == "consultation"
    assert service.normalize_line_item_category("Post-Op Pharmacy & Antibiotic Infusions") == "pharmacy"
    assert service.normalize_line_item_category("MRI Lumbar Spine with Contrast") == "diagnostics"
    assert service.normalize_line_item_category("Disposable Trocar Pack & Surgical Consumables") == "ancillary"


def test_check_price_benchmarks_clean_claim():
    """Verify that a clean claim within benchmarks does not trigger high/critical inflation findings."""
    claim = {
        "claim_id": "CLM-CLEAN-TEST",
        "diagnosis_code": "K35.8",
        "total_claimed": 52000.0,
        "line_items": [
            {"description": "Room Rent", "qty": 3, "unit_price": 4000.0, "amount": 12000.0},
            {"description": "Laparoscopic Appendectomy Surgery & OT", "qty": 1, "unit_price": 28000.0, "amount": 28000.0},
            {"description": "Consultation", "qty": 3, "unit_price": 2000.0, "amount": 6000.0},
            {"description": "Pharmacy", "qty": 1, "unit_price": 5000.0, "amount": 5000.0},
        ]
    }
    res = check_price_benchmarks(claim)
    findings = res.get("findings", [])
    high_findings = [f for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
    assert len(high_findings) == 0, f"Expected 0 high findings on clean claim, got {high_findings}"


def test_check_price_benchmarks_all_three_findings():
    """
    Verify that an inflated claim triggers all 3 required benchmark findings:
      - TOTAL_ABOVE_DIAGNOSIS_BENCHMARK
      - LINE_ITEM_PRICE_ABOVE_BENCHMARK
      - UNBUNDLED_OR_PADDED_ANCILLARY
    """
    claim = {
        "claim_id": "CLM-INFLATED-TEST",
        "diagnosis_code": "K35.8",
        "total_claimed": 98000.0,  # Far above K35.8 p95 (59,644)
        "line_items": [
            {"description": "Semi-Private Room Rent", "qty": 3, "unit_price": 4000.0, "amount": 12000.0},
            {"description": "Laparoscopic Appendectomy Surgery & OT", "qty": 1, "unit_price": 55000.0, "amount": 55000.0}, # > p95 38,627
            {"description": "Consultation", "qty": 3, "unit_price": 2000.0, "amount": 6000.0},
            {"description": "Surgical Consumables & Disposable Trocar Pack", "qty": 1, "unit_price": 13000.0, "amount": 13000.0},
            {"description": "High-Definition Laparoscopy Tower Usage", "qty": 1, "unit_price": 12000.0, "amount": 12000.0},
        ]
    }
    res = check_price_benchmarks(claim)
    findings = res.get("findings", [])
    check_ids = [f.check_id for f in findings]

    assert "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK" in check_ids
    assert "LINE_ITEM_PRICE_ABOVE_BENCHMARK" in check_ids
    assert "UNBUNDLED_OR_PADDED_ANCILLARY" in check_ids

    # Verify severity
    total_finding = next(f for f in findings if f.check_id == "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK")
    assert total_finding.severity == Severity.HIGH


def test_scoring_guardrail_inflation_cannot_approve():
    """Verify that claims with high inflation findings cannot end at APPROVE."""
    finding_bench = Finding(
        finding_id="F-BENCH-1",
        agent=AgentName.POLICY,
        check_id="TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
        severity=Severity.HIGH,
        title="Total claim exceeds benchmark",
        explanation="Total is 50% above p95 benchmark",
        evidence=[],
        confidence=0.95
    )

    # Even with 0 ML probability, high inflation forces REVIEW with risk >= 45
    score, verdict = score_findings([finding_bench], ml_probability=0.0)
    assert verdict == Verdict.REVIEW
    assert score >= 45
