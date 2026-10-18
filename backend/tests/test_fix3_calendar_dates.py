"""
backend/tests/test_fix3_calendar_dates.py

Comprehensive tests for Fix 3:
1. Calendar date comparison in Asia/Kolkata (IST), not raw UTC timestamps.
2. Same-day discharge with later hour (e.g., today 11:00 vs audit clock 08:29 IST) is NOT flagged.
3. +1 calendar day tolerance allowed (tomorrow is NOT flagged).
4. Strictly future dates (>= 2 calendar days ahead) emit FUTURE_OR_IMPLAUSIBLE_DATE with Severity.HIGH.
5. Extreme future dates (year >= 2030, e.g. 2031) emit FUTURE_OR_IMPLAUSIBLE_DATE with Severity.CRITICAL.
6. Reversed dates (discharge before admission) emit REVERSED_HOSPITALIZATION_DATES with Severity.CRITICAL.
7. Finding explanation includes formatted calendar dates and timezone:
   "Discharge date 20-Oct-2026 is after today (18-Oct-2026, IST)"
8. Injectable "now" clock support (datetime or string).
9. Full policy agent and scoring pipeline verification for same-day APPROVE vs future REJECT.
"""

import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from backend.app.schemas import Claim, LineItem, Claimant, Provider, Finding, Severity, AgentName, Verdict
from backend.tools.date_utils import parse_flexible_date, is_date_after_reference, IST
from backend.tools.registry import check_dates
from backend.agents.policy import analyze_policy_and_arithmetic
from backend.tools.scoring import score_findings


def test_check_dates_same_day_later_hour():
    """
    Evidence scenario: a bill whose discharge was today at 11:00 was flagged
    under old timestamp logic when audit ran at 08:29 IST.
    Under calendar date logic in IST, same-day discharge must NEVER be flagged.
    """
    ref_now = datetime(2026, 10, 18, 8, 29, 0, tzinfo=IST)

    res = check_dates(
        admission_ts="2026-10-18T09:00:00",
        discharge_ts="2026-10-18T11:00:00",
        bill_date="2026-10-18",
        now=ref_now
    )

    assert res["valid"] is True
    future_findings = [f for f in res["findings"] if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"]
    assert len(future_findings) == 0, f"Expected no future date finding for same-day discharge, got {future_findings}"


def test_check_dates_tomorrow_tolerance():
    """
    Tolerance rule: allow a +1 calendar day tolerance for timezone differences.
    A bill dated tomorrow relative to today in IST must not be flagged.
    """
    ref_now = datetime(2026, 10, 18, 14, 0, 0, tzinfo=IST)

    res = check_dates(
        admission_ts="2026-10-18T10:00:00",
        discharge_ts="2026-10-19T10:00:00",
        bill_date="2026-10-19",
        now=ref_now
    )

    assert res["valid"] is True
    future_findings = [f for f in res["findings"] if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"]
    assert len(future_findings) == 0


def test_check_dates_two_days_ahead_finding():
    """
    Strict future date: 2 days ahead of reference audit date in IST must be flagged.
    Severity: HIGH.
    Explanation format: "Discharge date 20-Oct-2026 is after today (18-Oct-2026, IST)"
    """
    ref_now = datetime(2026, 10, 18, 8, 29, 0, tzinfo=IST)

    res = check_dates(
        admission_ts="2026-10-19T09:00:00",
        discharge_ts="2026-10-20T12:00:00",
        bill_date="2026-10-20",
        now=ref_now
    )

    assert res["valid"] is False
    future_findings = [f for f in res["findings"] if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"]
    assert len(future_findings) == 1

    f = future_findings[0]
    assert f.severity == Severity.HIGH
    assert "Discharge date 20-Oct-2026 is after today (18-Oct-2026, IST)" in f.explanation
    assert "Hospitalization or bill dates occurring in the future represent an impossible timeline" in f.explanation
    assert f.computed_details["diff_days"] == 2
    assert f.computed_details["parsed_calendar_date"] == "2026-10-20"
    assert f.computed_details["reference_calendar_date"] == "2026-10-18"


def test_check_dates_extreme_future_2031_critical():
    """
    Extreme future date: ISO bill date in 2031 must emit Severity.CRITICAL.
    """
    ref_now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=IST)

    res = check_dates(
        admission_ts="2026-10-10",
        discharge_ts="2026-10-12",
        bill_date="2031-03-14",
        now=ref_now
    )

    assert res["valid"] is False
    future_findings = [f for f in res["findings"] if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"]
    assert len(future_findings) == 1
    f = future_findings[0]
    assert f.severity == Severity.CRITICAL
    assert "Bill date 14-Mar-2031 is after today (15-Oct-2026, IST)" in f.explanation
    assert f.computed_details["diff_days"] > 1000


def test_check_dates_reversed_dates_critical():
    """
    Reversed dates: admission occurs after discharge.
    Must emit REVERSED_HOSPITALIZATION_DATES with Severity.CRITICAL.
    """
    ref_now = datetime(2026, 10, 18, 8, 29, 0, tzinfo=IST)

    res = check_dates(
        admission_ts="2026-09-12T12:00:00",
        discharge_ts="2026-09-10T09:00:00",
        now=ref_now
    )

    assert res["valid"] is False
    rev_findings = [f for f in res["findings"] if f.check_id == "REVERSED_HOSPITALIZATION_DATES"]
    assert len(rev_findings) == 1
    assert rev_findings[0].severity == Severity.CRITICAL
    assert "Admission timestamp" in rev_findings[0].explanation


def test_date_parsing_formats_robustness():
    """
    Verify robust date parsing across formats: ISO, dd-Mon-yyyy, dd/mm/yyyy, d-m-yy, month names, 2-digit years.
    """
    ref_now = datetime(2026, 10, 18, 8, 29, 0, tzinfo=IST)

    # Various clean formats representing 15-Oct-2026 (past date)
    valid_past_formats = [
        "2026-10-15",
        "2026-10-15T10:30:00Z",
        "15-Oct-2026",
        "15-October-2026",
        "15/10/2026",
        "15-10-26",
        "October 15, 2026",
        "15th October 2026",
        "15.10.2026",
    ]
    for fmt_str in valid_past_formats:
        res = check_dates(
            admission_ts=fmt_str,
            discharge_ts=fmt_str,
            now=ref_now
        )
        assert res["valid"] is True, f"Failed for format: {fmt_str}"
        assert len([f for f in res["findings"] if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"]) == 0


def test_is_date_after_reference_helper():
    """
    Verify helper function is_date_after_reference obeys calendar dates in IST with tolerance.
    """
    ref_now = datetime(2026, 10, 18, 8, 29, 0, tzinfo=IST)

    # 1. Same-day later hour -> False
    is_fut, parsed, _ = is_date_after_reference("2026-10-18T11:00:00", now=ref_now)
    assert not is_fut

    # 2. Tomorrow (+1 day) -> False (tolerance)
    is_fut, parsed, _ = is_date_after_reference("2026-10-19T10:00:00", now=ref_now)
    assert not is_fut

    # 3. Two days ahead -> True
    is_fut, parsed, _ = is_date_after_reference("2026-10-20T10:00:00", now=ref_now)
    assert is_fut

    # 4. Year 2031 -> True
    is_fut, parsed, _ = is_date_after_reference("2031-03-14", now=ref_now)
    assert is_fut


def test_analyze_policy_same_day_claim_clean():
    """
    End-to-end policy agent run on a claim with same-day discharge at 11:00.
    Must emit NO future date findings.
    """
    ref_now = datetime(2026, 10, 18, 8, 29, 0, tzinfo=IST)

    claim = Claim(
        claim_id="CLM-SAMEDAY-001",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="C1", name="Ramesh Kumar", phone="9876543210", bank_account_hash="h1"),
        provider=Provider(hospital_id="H1", name="City Hospital", city="New Delhi"),
        admission_ts="2026-10-18T09:00:00",
        discharge_ts="2026-10-18T11:00:00",
        subtotal=5000.0,
        tax=250.0,
        total_claimed=5250.0,
        metadata={"now": ref_now.isoformat(), "has_printed_total": True},
        field_sources={"total_claimed": "docai"},
        line_items=[
            LineItem(description="Consultation", qty=1, unit_price=1000.0, amount=1000.0, page=1, source="docai"),
            LineItem(description="Lab tests", qty=1, unit_price=4000.0, amount=4000.0, page=1, source="docai"),
        ]
    )

    findings = analyze_policy_and_arithmetic(claim, now=ref_now)
    future_f = [f for f in findings if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"]
    assert len(future_f) == 0, f"Expected no future date finding, got {future_f}"

    # Full scoring pipeline: should be APPROVE
    risk_score, verdict = score_findings(findings)
    assert verdict == Verdict.APPROVE
    assert risk_score <= 10


def test_analyze_policy_two_days_ahead_rejected():
    """
    End-to-end policy agent run on a claim with discharge 2 days ahead of audit date.
    Must emit FUTURE_OR_IMPLAUSIBLE_DATE at HIGH severity and result in REJECT verdict.
    """
    ref_now = datetime(2026, 10, 18, 8, 29, 0, tzinfo=IST)

    claim = Claim(
        claim_id="CLM-FUTURE-002",
        diagnosis_code="E11.9",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="C2", name="Suresh Patel", phone="9876543211", bank_account_hash="h2"),
        provider=Provider(hospital_id="H2", name="Metro Hospital", city="Mumbai"),
        admission_ts="2026-10-19T09:00:00",
        discharge_ts="2026-10-20T12:00:00",
        subtotal=5000.0,
        tax=250.0,
        total_claimed=5250.0,
        metadata={"now": ref_now.isoformat(), "has_printed_total": True},
        field_sources={"total_claimed": "docai"},
        line_items=[
            LineItem(description="Consultation", qty=1, unit_price=1000.0, amount=1000.0, page=1, source="docai"),
            LineItem(description="Lab tests", qty=1, unit_price=4000.0, amount=4000.0, page=1, source="docai"),
        ]
    )

    findings = analyze_policy_and_arithmetic(claim, now=ref_now)
    future_f = [f for f in findings if f.check_id == "FUTURE_OR_IMPLAUSIBLE_DATE"]
    assert len(future_f) == 1
    assert future_f[0].severity == Severity.HIGH

    risk_score, verdict = score_findings(findings)
    assert verdict == Verdict.REJECT
    assert risk_score >= 85
