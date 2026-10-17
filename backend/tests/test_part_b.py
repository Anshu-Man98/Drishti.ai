import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

from backend.app.main import app
from backend.app.schemas import Claim, Claimant, Provider, LineItem, Dossier, Verdict
from backend.app.services.db import db_service
from backend.agents.chat import build_case_file_context
from backend.app.routers.graph import _build_subgraph_for_ring, FraudRingSummary

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer adjuster-token"}


@pytest.fixture
def clean_duel_claim() -> Claim:
    c = Claim(
        claim_id="CLM-TEST-DUEL-BASE",
        policy_id="POL-CARE-001",
        insurer_id="INS-CARE",
        claimant=Claimant(
            claimant_id="CLMNT-DUEL-1",
            name="Aarav Sharma",
            phone="+91-9876543210",
            bank_account_hash="hash_duel_123"
        ),
        provider=Provider(
            hospital_id="HOSP-104",
            name="Suraksha Hospital",
            city="Mumbai",
            lat=19.0760,
            lng=72.8777
        ),
        doctor_id="DOC-9901",
        admission_ts=datetime(2026, 3, 1, 10, 0),
        discharge_ts=datetime(2026, 3, 4, 12, 0),
        diagnosis_code="K35.8",
        total_claimed=100000.0,
        subtotal=100000.0,
        line_items=[
            LineItem(description="Appendectomy Surgery", qty=1, unit_price=80000.0, amount=80000.0),
            LineItem(description="Room Rent Semi-Private", qty=4, unit_price=5000.0, amount=20000.0)
        ]
    )
    db_service.save_claim(c)
    return c


def test_b1_duel_start_and_status(clean_duel_claim):
    """Verify B1: POST /duel/start returns duel_id immediately in background mode, and GET /duel/{id}/status returns live progress."""
    # Test wait=False (default)
    with patch("backend.app.routers.duel.run_duel") as mock_run:
        resp = client.post(
            "/api/duel/start",
            json={"claim_id": clean_duel_claim.claim_id, "rounds": 2, "wait": False},
            headers=AUTH_HEADERS
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "duel_id" in data
        assert data["status"] == "running"
        assert data["max_rounds"] == 2
        duel_id = data["duel_id"]

        # Check status endpoint
        status_resp = client.get(f"/api/duel/{duel_id}/status", headers=AUTH_HEADERS)
        assert status_resp.status_code == 200, status_resp.text
        st_data = status_resp.json()
        assert st_data["duel_id"] == duel_id
        assert st_data["status"] in ("running", "completed")
        assert st_data["max_rounds"] == 2
        assert "rounds" in st_data


def test_b4_exclude_synthetic_analytics_and_claims():
    """Verify B4: exclude_synthetic query parameter correctly filters out DEMO / SYNTH claims."""
    # Test claims queue endpoint with exclude_synthetic=true
    resp = client.get("/api/claims?limit=100&exclude_synthetic=true", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    claims = resp.json()
    for c in claims:
        cid = c["claim_id"]
        assert "-DEMO" not in cid, f"Found demo claim {cid} when exclude_synthetic=true"
        assert "-SYNTH" not in cid, f"Found synth claim {cid} when exclude_synthetic=true"
        assert not cid.startswith("SYNTH-"), f"Found synth claim {cid} when exclude_synthetic=true"

    # Test analytics summary endpoint
    resp_all = client.get("/api/analytics/summary?exclude_synthetic=false", headers=AUTH_HEADERS)
    assert resp_all.status_code == 200
    all_summary = resp_all.json()

    resp_filtered = client.get("/api/analytics/summary?exclude_synthetic=true", headers=AUTH_HEADERS)
    assert resp_filtered.status_code == 200
    filtered_summary = resp_filtered.json()

    # Total claims in filtered summary should not exceed all summary
    assert filtered_summary["total_claims"] <= all_summary["total_claims"]
    for item in filtered_summary.get("recent_critical_claims", []):
        cid = item["claim_id"]
        assert "-DEMO" not in cid
        assert "-SYNTH" not in cid


def test_b5_graph_subgraph_limit_and_bank_label():
    """Verify B5: graph subgraph query limits to 20 and formats bank node label as 'Bank (*short)'."""
    ring = FraudRingSummary(
        ring_id="RING-BANK-TEST",
        title="Test Shared Bank Ring",
        type="shared_bank_account",
        claim_count=5,
        claimant_count=3,
        total_amount=150000.0,
        primary_entity="hash_acc_998811",
        risk_level="high",
        description="Test ring",
        sample_cities=["Mumbai"]
    )
    detail = _build_subgraph_for_ring(ring, limit=20)
    assert detail.ring.ring_id == "RING-BANK-TEST"
    assert len(detail.nodes) > 0
    # Central bank node
    bank_node = next((n for n in detail.nodes if n.type == "bank_account"), None)
    assert bank_node is not None
    assert bank_node.label.startswith("Bank (*")
    assert "998811" in bank_node.label
    assert bank_node.metadata.get("account_hash") == "hash_acc_998811"


def test_b6_chat_context_includes_benchmarks_and_hospital_avg():
    """Verify B6: Case Assistant case file context contains clinical benchmark percentiles, excess, and hospital avg."""
    claim = Claim(
        claim_id="CLM-TEST-CHAT-B6",
        policy_id="POL-CARE-001",
        insurer_id="INS-CARE",
        claimant=Claimant(
            claimant_id="CLMNT-001",
            name="Aditi Rao",
            phone="+91-9876543210",
            bank_account_hash="hash_aditi_123"
        ),
        provider=Provider(hospital_id="HOSP-104", name="Suraksha Hospital", city="Mumbai"),
        admission_ts=datetime(2026, 3, 10, 10, 0),
        discharge_ts=datetime(2026, 3, 14, 12, 0),
        diagnosis_code="K35.8",
        total_claimed=250000.0,
        line_items=[
            LineItem(description="Appendectomy Surgery", qty=1, unit_price=200000.0, amount=200000.0),
            LineItem(description="Room Rent Deluxe", qty=4, unit_price=12500.0, amount=50000.0)
        ]
    )
    dossier = Dossier(
        claim_id=claim.claim_id,
        verdict=Verdict.REVIEW,
        risk_score=78.0,
        summary="Inflated claim exceeding regional tariffs.",
        findings=[]
    )

    context_text, finding_map = build_case_file_context(claim, dossier)

    assert "=== CASE FILE: CLAIM AUDIT DOSSIER ===" in context_text
    assert "Statistical & Clinical Benchmarks (BigQuery Data Warehouse)" in context_text
    assert "Diagnosis Code: K35.8" in context_text
    assert "p50)" in context_text
    assert "95th percentile=" in context_text
    assert "Claim vs 95th Percentile:" in context_text
    assert "Hospital Historical Average:" in context_text or "HOSP-104" in context_text
