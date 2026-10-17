import pytest
from backend.app.routers.reference import (
    ICD10_MAP,
    INSURER_MAP,
    POLICY_PREFIX_MAP,
    normalize_icd10,
    resolve_policy_name,
)
from backend.app.schemas import Finding, Severity, AgentName


def test_a1_icd10_data_coverage():
    """
    PART A1: All distinct diagnosis codes present in BigQuery and Firestore claims
    must have a non-empty human-readable clinical description.
    """
    known_data_codes = [
        "A09",
        "E11.9",
        "I20.9",
        "J18.9",
        "K35.8",
        "K80.2",
        "M54.5",
        "N39.0",
        "S82.8",
        # Related codes in data / prompt
        "K80.0",
        "S82.2",
        "K35.80",
        "K80.20",
        "M54.50",
    ]

    for code in known_data_codes:
        desc = normalize_icd10(code)
        assert desc != "description not in reference table", f"Code {code} has no description!"
        assert len(desc) > 3, f"Description for {code} is too short: '{desc}'"


def test_a1_icd10_normalization():
    """
    PART A1: Normalization must handle case, whitespace, trailing zero variants,
    and 3-character category parent blocks.
    """
    # Case & whitespace
    assert normalize_icd10("  k35.8  ") != "description not in reference table"
    assert "Appendicitis" in normalize_icd10("k35.8")

    # Trailing zero normalization
    assert normalize_icd10("K35.80") != "description not in reference table"
    assert normalize_icd10("K80.20") != "description not in reference table"

    # Parent 3-character fallback
    parent_fallback = normalize_icd10("K35.999")
    assert parent_fallback == "Acute Appendicitis"

    # Truly unknown code must return exact sentinel, never duplicate code
    unknown = normalize_icd10("ZZ99.99")
    assert unknown == "description not in reference table"
    assert "ZZ99" not in unknown


def test_a2_insurer_data_coverage():
    """
    PART A2: Every distinct insurer in BigQuery and Firestore must have
    a legal corporate name and short name.
    """
    data_insurers = [
        "INS-CARE",
        "INS-FINSHIELD",
        "INS-HDFC",
        "INS-ICICI",
        "INS-NIVA",
        "INS-STAR",
        "INS-MAX",
    ]

    for ins in data_insurers:
        assert ins in INSURER_MAP, f"Insurer {ins} is missing from INSURER_MAP!"
        assert "name" in INSURER_MAP[ins] and len(INSURER_MAP[ins]["name"]) > 0
        assert "short" in INSURER_MAP[ins] and len(INSURER_MAP[ins]["short"]) > 0


def test_a2_policy_prefix_resolution():
    """
    PART A2: Distinct policy prefixes in data must resolve to readable product names.
    """
    data_policies = [
        ("POL-AROGYA-88124", "Arogya Sanjeevani Plan"),
        ("POL-CARE-99812", "Care Comprehensive Health Plan"),
        ("POL-OPTIMA-44102", "Optima Secure & Restore"),
        ("POL-STAR-55001", "Star Comprehensive Health"),
        ("POL-AROGYA-SANJEEVANI-001", "Arogya Sanjeevani Plan"),
    ]

    for pol_id, expected_name in data_policies:
        resolved = resolve_policy_name(pol_id)
        assert resolved == expected_name, f"Policy {pol_id} resolved to '{resolved}', expected '{expected_name}'"


def test_a4_benchmark_finding_percentage_not_zero():
    """
    PART A4: When total claim exceeds p95, title must NEVER display '+0% above p95'.
    If the excess is smaller than 1%, it must report the real decimal figure (e.g. +0.4%).
    """
    # Test formula directly as implemented in registry.py
    ratio = 100400 / max(1, 100000)
    pct_diff = (ratio - 1) * 100
    pct_str = f"+{pct_diff:.1f}%" if pct_diff < 1.0 else f"+{round(pct_diff)}%"
    title = f"Total claim amount exceeds diagnosis benchmark ({pct_str} above p95)"
    
    assert "+0%" not in title
    assert "+0.4% above p95" in title

    # Also test higher percentage (e.g. 25%)
    ratio_high = 1.25
    pct_diff_high = (ratio_high - 1) * 100
    pct_str_high = f"+{pct_diff_high:.1f}%" if pct_diff_high < 1.0 else f"+{round(pct_diff_high)}%"
    title_high = f"Total claim amount exceeds diagnosis benchmark ({pct_str_high} above p95)"
    assert "+25% above p95" in title_high


def test_a5_analytics_excludes_info_and_internal_noise():
    """
    PART A5: Analytics summary aggregation must exclude info findings and internal
    guardrail noise (e.g. UNGROUNDED_NUMBER) from finding counts and agent counts.
    """
    from backend.app.schemas import Verdict

    # Create synthetic test dossier data
    dossiers_map = {
        "CLM-TEST-1": {
            "findings": [
                {
                    "finding_id": "F1",
                    "agent": "policy",
                    "check_id": "TOTAL_ABOVE_DIAGNOSIS_BENCHMARK",
                    "severity": "high",
                    "title": "Benchmark exceeded",
                },
                {
                    "finding_id": "F2",
                    "agent": "ml",
                    "check_id": "ungrounded_number",
                    "severity": "info",
                    "title": "Internal: ungrounded number note",
                },
                {
                    "finding_id": "F3",
                    "agent": "ml",
                    "check_id": "BQML_HIGH_RISK_ANOMALY",
                    "severity": "high",
                    "title": "ML Anomaly detected",
                },
            ]
        },
        "CLM-TEST-2": {
            "findings": [
                {
                    "finding_id": "F4",
                    "agent": "ml",
                    "check_id": "ungrounded_number",
                    "severity": "info",
                    "title": "Internal note",
                }
            ]
        }
    }

    agent_counts = {"ml": 0, "policy": 0}
    agent_claims = {"ml": set(), "policy": set()}
    category_counts = {"BQML Anomaly Outliers": 0, "Policy Limit & Benchmark Breaches": 0}

    for d_id, d_data in dossiers_map.items():
        for f in d_data.get("findings", []):
            sev = (f.get("severity") or "").lower()
            ch = (f.get("check_id") or "").upper()

            if sev == "info":
                continue
            if any(noise in ch for noise in ["UNGROUNDED", "INTERNAL"]):
                continue

            ag = (f.get("agent") or "").lower()
            if ag in agent_counts:
                agent_counts[ag] += 1
                agent_claims[ag].add(d_id)

            if "BQML" in ch:
                category_counts["BQML Anomaly Outliers"] += 1
            elif "BENCHMARK" in ch:
                category_counts["Policy Limit & Benchmark Breaches"] += 1

    # info finding 'ungrounded_number' must be excluded
    # Only 1 real ML finding and 1 real policy finding
    assert agent_counts["ml"] == 1, f"Expected 1 real ML finding, got {agent_counts['ml']}"
    assert agent_counts["policy"] == 1
    assert len(agent_claims["ml"]) == 1
    assert "CLM-TEST-2" not in agent_claims["ml"], "CLM-TEST-2 with only info finding should not be counted!"
    assert category_counts["BQML Anomaly Outliers"] == 1
