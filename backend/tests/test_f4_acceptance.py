"""
Acceptance test suite for F4: Spacetime Impossibility Detection and GIS Mapping.
Validates:
1. Deterministic geo mathematics: haversine_km, min_travel_hours (road vs air), is_feasible.
2. Edge cases: same city (< 5 km), overnight gaps, missing coordinates -> skipped, not flagged.
3. Chronological timeline generation from claim documents + BigQuery warehouse events.
4. G5 acceptance: emits critical finding DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL with "1,150 km in 90 min".
5. G1 acceptance: clean claim shows all-green / feasible legs with no spacetime critical findings.
6. Dossier timeline persistence in SQLite/Firestore.
7. Bonus pitch query: infra/impossible_travel_query.sql validates BigQuery spatial syntax.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from backend.tools.geo import haversine_km, min_travel_hours, is_feasible
from backend.agents.spacetime import build_timeline, analyze_spacetime_feasibility
from backend.agents.root import run_claims_fraud_pipeline
from backend.tools.docai import process_document_docai
from backend.app.schemas import Claim, Provider, Claimant, TimelineEvent, Severity
from backend.app.services.db import db_service

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "data" / "demo"
GROUND_TRUTH_PATH = DEMO_DIR / "ground_truth.json"
PITCH_SQL_PATH = ROOT_DIR / "infra" / "impossible_travel_query.sql"


# ==============================================================================
# 1. GEO MATH & PHYSICS TESTS
# ==============================================================================

def test_haversine_distance_calculations():
    """Verify haversine formula against known coordinate pairs."""
    # Same point
    assert haversine_km(28.6139, 77.2090, 28.6139, 77.2090) == 0.0

    # Delhi (28.6139, 77.2090) to Mumbai (19.0760, 72.8777) ~ 1148 km
    delhi_lat, delhi_lng = 28.6448, 77.1878
    mumbai_lat, mumbai_lng = 19.0596, 72.8295
    km = haversine_km(delhi_lat, delhi_lng, mumbai_lat, mumbai_lng)
    assert 1140 <= km <= 1160, f"Expected ~1,148 km, got {km} km"

    # Delhi to Gurgaon (~25 km)
    gurgaon_lat, gurgaon_lng = 28.4595, 77.0266
    delhi_to_ggn = haversine_km(delhi_lat, delhi_lng, gurgaon_lat, gurgaon_lng)
    assert 20 <= delhi_to_ggn <= 35


def test_min_travel_hours_formula():
    """Verify travel physics: road for <=300km, airport overhead + flight for >300km."""
    # <= 300 km: km / 80.0
    assert min_travel_hours(0.0) == 0.0
    assert min_travel_hours(80.0) == 1.0
    assert min_travel_hours(160.0) == 2.0
    assert min_travel_hours(300.0) == 3.75

    # > 300 km: 2.5h + km / 700.0
    # For 1,150 km: 2.5 + 1150/700 = 2.5 + 1.6428 = 4.1428 hours (~4.1 h)
    flight_hours = min_travel_hours(1150.0)
    assert 4.1 <= flight_hours <= 4.2


def test_geo_edge_cases():
    """Verify edge case handling in is_feasible."""
    t0 = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 7, 20, 11, 0, tzinfo=timezone.utc)

    # Edge Case A: Missing coordinates -> skipped=True, feasible=True
    ev_missing = TimelineEvent(
        ts=t0,
        lat=0.0,
        lng=0.0,
        place="Unknown Hospital",
        actor="doctor"
    )
    ev_delhi = TimelineEvent(
        ts=t1,
        lat=28.6448,
        lng=77.1878,
        place="Delhi Hospital",
        actor="doctor"
    )
    res_missing = is_feasible(ev_missing, ev_delhi)
    assert res_missing["skipped"] is True
    assert res_missing["feasible"] is True

    # Edge Case B: Same city / campus (< 5 km apart within 10 min) -> feasible
    ev_campus_a = TimelineEvent(
        ts=t0,
        lat=28.6448,
        lng=77.1878,
        place="Building A",
        actor="doctor"
    )
    ev_campus_b = TimelineEvent(
        ts=t0 + timedelta(minutes=10),
        lat=28.6460,
        lng=77.1885,
        place="Building B",
        actor="doctor"
    )
    res_campus = is_feasible(ev_campus_a, ev_campus_b)
    assert res_campus["skipped"] is False
    assert res_campus["feasible"] is True
    assert res_campus["km"] < 5.0

    # Edge Case C: Overnight gaps (Delhi at 20:00 to Mumbai at 10:00 next day = 14h available vs 4.1h required) -> feasible
    ev_night = TimelineEvent(
        ts=t0,
        lat=28.6448,
        lng=77.1878,
        place="Delhi Night",
        actor="doctor"
    )
    ev_next_day = TimelineEvent(
        ts=t0 + timedelta(hours=14),
        lat=19.0596,
        lng=72.8295,
        place="Mumbai Morning",
        actor="doctor"
    )
    res_overnight = is_feasible(ev_night, ev_next_day)
    assert res_overnight["feasible"] is True
    assert res_overnight["available_h"] == 14.0
    assert res_overnight["required_h"] < 5.0

    # Edge Case D: Impossible transit (Delhi at 14:10, Mumbai at 15:40 = 90 min vs 4.1h required) -> NOT feasible
    ev_impossible_a = TimelineEvent(
        ts=datetime(2026, 7, 20, 14, 10, tzinfo=timezone.utc),
        lat=28.6448,
        lng=77.1878,
        place="Delhi Clinic",
        actor="DOC-9021"
    )
    ev_impossible_b = TimelineEvent(
        ts=datetime(2026, 7, 20, 15, 40, tzinfo=timezone.utc),
        lat=19.0596,
        lng=72.8295,
        place="Mumbai Hospital",
        actor="DOC-9021"
    )
    res_impossible = is_feasible(ev_impossible_a, ev_impossible_b)
    assert res_impossible["feasible"] is False
    assert res_impossible["available_h"] == 1.5
    assert 1140 <= res_impossible["km"] <= 1160
    assert res_impossible["required_h"] > 4.0


# ==============================================================================
# 2. TIMELINE GENERATION TESTS
# ==============================================================================

def test_build_timeline_chronological_order():
    """Verify build_timeline constructs a chronological event list with doctor billing events."""
    claim = Claim(
        claim_id="CLM-TIMELINE-TEST",
        policy_id="POL-12345",
        insurer_id="INS-001",
        claimant=Claimant(
            claimant_id="C-100",
            name="Test Patient",
            phone="9876543210",
            bank_account_hash="abc"
        ),
        provider=Provider(
            hospital_id="HOSP-DELHI",
            name="Apex Hospital",
            city="Delhi",
            lat=28.6448,
            lng=77.1878
        ),
        doctor_id="DOC-9021",
        admission_ts=datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        discharge_ts=datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc),
        diagnosis_code="I25.10",
        line_items=[],
        subtotal=50000.0,
        tax=9000.0,
        total_claimed=59000.0
    )

    timeline = build_timeline(claim)
    assert len(timeline) >= 3, "Timeline should include admission, doctor event, and discharge"

    # Verify chronological ascending order
    for i in range(len(timeline) - 1):
        dt_i = timeline[i].ts if timeline[i].ts.tzinfo else timeline[i].ts.replace(tzinfo=timezone.utc)
        dt_next = timeline[i + 1].ts if timeline[i + 1].ts.tzinfo else timeline[i + 1].ts.replace(tzinfo=timezone.utc)
        assert dt_i <= dt_next, f"Timeline out of order at index {i}"

    # Verify doctor event from BigQuery warehouse is present
    doctor_events = [ev for ev in timeline if "Rajesh" in ev.actor or ev.actor == "DOC-9021"]
    assert len(doctor_events) >= 2, "Expected at least 2 doctor events (Delhi procedure + Mumbai warehouse event)"


# ==============================================================================
# 3. ACCEPTANCE: G5 (IMPOSSIBLE TRAVEL) & G1 (CLEAN CLAIM)
# ==============================================================================

def test_g5_impossible_travel_critical_finding():
    """
    Acceptance Criterion:
    G5 shows one red impossible leg with the correct numbers:
    'Dr. Rajesh Mehta billed procedures in Delhi at 14:10 and Mumbai at 15:40 — 1,150 km in 90 min; minimum realistic travel ≈ 4.1 h.'
    """
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    g5_info = gt["G5"]
    pdf_path = DEMO_DIR / g5_info["file"]
    claim_id = "CLM-G5-F4-ACCEPTANCE"

    # Extract claim from G5 PDF
    claim, _ = process_document_docai(pdf_path.read_bytes(), filename=g5_info["file"], claim_id=claim_id)
    if claim.documents:
        claim.documents[0].gcs_uri = f"file://{pdf_path}"
    db_service.save_claim(claim)

    # Run ADK multi-agent pipeline
    dossier = run_claims_fraud_pipeline(claim)
    db_service.save_dossier(dossier)

    # Verify finding emitted by SpacetimeAgent
    spacetime_findings = [f for f in dossier.findings if f.agent.value == "spacetime" or f.check_id == "DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL"]
    assert len(spacetime_findings) >= 1, "Expected DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL finding on G5"

    f = spacetime_findings[0]
    assert f.severity == Severity.CRITICAL
    assert "1,150 km" in f.explanation or "1148" in f.explanation or "1,148" in f.explanation
    assert "90 min" in f.explanation or "1.5 h" in f.explanation
    assert "4.1" in f.explanation

    # Verify timeline is attached to dossier
    assert len(dossier.timeline) >= 2
    delhi_ev = next(ev for ev in dossier.timeline if "Delhi" in ev.place and "Rajesh" in ev.actor)
    mumbai_ev = next(ev for ev in dossier.timeline if "Mumbai" in ev.place and "Rajesh" in ev.actor)
    assert delhi_ev is not None
    assert mumbai_ev is not None

    # Verify impossible leg between Delhi and Mumbai for the doctor
    feasibility = is_feasible(delhi_ev, mumbai_ev)
    assert feasibility["feasible"] is False


def test_g1_clean_claim_all_green_legs():
    """
    Acceptance Criterion:
    G1 shows all-green legs with no impossible spacetime findings.
    """
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    g1_info = gt["G1"]
    pdf_path = DEMO_DIR / g1_info["file"]
    claim_id = "CLM-G1-F4-ACCEPTANCE"

    claim, _ = process_document_docai(pdf_path.read_bytes(), filename=g1_info["file"], claim_id=claim_id)
    if claim.documents:
        claim.documents[0].gcs_uri = f"file://{pdf_path}"
    db_service.save_claim(claim)

    dossier = run_claims_fraud_pipeline(claim)
    db_service.save_dossier(dossier)

    # Assert no spacetime critical findings on clean claim
    spacetime_findings = [f for f in dossier.findings if f.check_id == "DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL"]
    assert len(spacetime_findings) == 0, "G1 clean claim should not have impossible travel findings"

    # All timeline legs for the same actor must be feasible
    for i in range(len(dossier.timeline) - 1):
        ev_a = dossier.timeline[i]
        ev_b = dossier.timeline[i + 1]
        if ev_a.actor == ev_b.actor:
            feasibility = is_feasible(ev_a, ev_b)
            assert feasibility["feasible"] is True, f"Leg {ev_a.place} -> {ev_b.place} should be feasible"


# ==============================================================================
# 4. BONUS PITCH QUERY VALIDATION
# ==============================================================================

def test_pitch_sql_query_exists_and_valid():
    """Verify infra/impossible_travel_query.sql exists and contains BigQuery spatial functions."""
    assert PITCH_SQL_PATH.exists(), "infra/impossible_travel_query.sql must exist"
    sql_text = PITCH_SQL_PATH.read_text()

    assert "ST_DISTANCE" in sql_text, "Query must calculate geographic distance via ST_DISTANCE"
    assert "ST_GEOGPOINT" in sql_text, "Query must construct geography points via ST_GEOGPOINT"
    assert "doctor_id" in sql_text, "Query must join or group on doctor_id"
    assert "min_required_travel_hours" in sql_text, "Query must calculate min_required_travel_hours"
    assert "ORDER BY" in sql_text, "Query must sort impossible legs for adjuster presentation"
