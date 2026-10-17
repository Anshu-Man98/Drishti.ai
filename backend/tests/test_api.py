import pytest
from fastapi.testclient import TestClient
from backend.app.main import app, lifespan, probe_cloud_dependencies
from backend.app.config import settings
from backend.app.dependencies import get_current_user

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "models" in data
    assert "pro" in data["models"]
    assert "flash" in data["models"]
    assert "dependencies" in data


def test_health_check_probes_and_security():
    """Validates that /health exposes real dependencies without leaking secrets."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    deps = data["dependencies"]
    expected_deps = ["firestore", "gcs", "bigquery", "documentai", "gemini", "provenance_key"]
    for dep in expected_deps:
        assert dep in deps, f"Missing {dep} in health dependencies"
        assert "status" in deps[dep]

    # Verify no credentials, tokens, or private keys leaked in response text
    raw_text = response.text
    assert "AQ.Ab8RN6" not in raw_text
    assert "finshield-provenance-signing-key" not in raw_text or "source" in raw_text


@pytest.mark.anyio
async def test_startup_fail_fast_when_cloud_required(monkeypatch):
    """
    Validates that if REQUIRE_CLOUD_ON_STARTUP=True and a required cloud
    dependency fails, app lifespan raises RuntimeError citing docs/CLOUD_SETUP.md.
    """
    import backend.app.main as main_module
    old_cached = main_module._CACHED_HEALTH
    try:
        monkeypatch.setattr(settings, "REQUIRE_CLOUD_ON_STARTUP", True)
        
        # Mock probe to simulate unreachable GCS / BigQuery
        def mock_failing_probe():
            return {
                "firestore": {"ok": True, "status": "connected"},
                "gcs": {"ok": False, "status": "unavailable", "detail": "Bucket unreachable"},
                "bigquery": {"ok": False, "status": "unavailable", "detail": "Dataset unreachable"},
                "documentai": {"ok": True, "status": "connected"},
                "gemini": {"ok": True, "status": "connected"},
                "provenance_key": {"ok": True, "status": "configured"}
            }

        monkeypatch.setattr("backend.app.main.probe_cloud_dependencies", mock_failing_probe)

        with pytest.raises(RuntimeError) as exc_info:
            async with lifespan(app):
                pass

        err_text = str(exc_info.value)
        assert "FinShield Cloud Startup Check FAILED" in err_text
        assert "gcs" in err_text
        assert "bigquery" in err_text
        assert "docs/CLOUD_SETUP.md" in err_text
    finally:
        main_module._CACHED_HEALTH = old_cached


def test_allow_dev_tokens_enforcement(monkeypatch):
    """When ALLOW_DEV_TOKENS=False (production mode), dev tokens must be rejected with 401."""
    app.dependency_overrides.clear()
    monkeypatch.setattr(settings, "ALLOW_DEV_TOKENS", False)

    try:
        # Dev token should now fail with 401
        res = client.get("/claims", headers={"Authorization": "Bearer adjuster-token"})
        assert res.status_code == 401
        assert "Invalid authentication token" in res.json().get("detail", "")
    finally:
        # Restore test auth override
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "test-adjuster-1",
            "email": "adjuster@finshield.test",
            "role": "adjuster"
        }


def test_claims_crud_flow():
    # 1. List claims (should return empty or list)
    resp = client.get("/claims")
    assert resp.status_code == 200
    initial_claims = resp.json()

    # 2. Upload/create a claim via multipart form
    claim_payload = {
        "policy_id": "POL-IRDAI-001",
        "insurer_id": "INS-HDFC-ERGO",
        "claimant_id": "CLMNT-1001",
        "claimant_name": "Rohan Verma",
        "claimant_phone": "+91-9876543210",
        "bank_account_hash": "a1b2c3d4e5f60718",
        "hospital_id": "HOSP-MAX-01",
        "hospital_name": "Max Super Speciality Hospital",
        "city": "New Delhi",
        "lat": "28.5284",
        "lng": "77.2185",
        "doctor_id": "DOC-9021",
        "admission_ts": "2026-03-10T09:00:00",
        "discharge_ts": "2026-03-13T18:00:00",
        "diagnosis_code": "I20.9",
        "subtotal": "85000.0",
        "tax": "4250.0",
        "total_claimed": "89250.0",
        "line_items_json": '[{"description": "ICU Room Charges (3 days)", "qty": 3, "unit_price": 15000, "amount": 45000}, {"description": "Angiography & Consumables", "qty": 1, "unit_price": 40000, "amount": 40000}]'
    }

    create_resp = client.post("/claims", data=claim_payload)
    assert create_resp.status_code == 200
    create_data = create_resp.json()
    claim_id = create_data["claim_id"]
    assert claim_id.startswith("CLM-")

    # 3. Retrieve claim
    get_resp = client.get(f"/claims/{claim_id}")
    assert get_resp.status_code == 200
    claim_data = get_resp.json()
    assert claim_data["claim_id"] == claim_id
    assert claim_data["claimant"]["name"] == "Rohan Verma"
    assert len(claim_data["line_items"]) == 2
    assert claim_data["total_claimed"] == 89250.0

    # 4. Trigger analyze
    analyze_resp = client.post(f"/claims/{claim_id}/analyze")
    assert analyze_resp.status_code == 200
    dossier = analyze_resp.json()
    assert dossier["claim_id"] == claim_id
    assert "risk_score" in dossier
    assert "verdict" in dossier

    # 5. Retrieve dossier
    dossier_resp = client.get(f"/claims/{claim_id}/dossier")
    assert dossier_resp.status_code == 200
    assert dossier_resp.json()["claim_id"] == claim_id


def test_fraud_rings_graph_endpoint():
    """Validates that GET /graph/rings queries BigQuery and returns nodes, edges, and real claims."""
    headers = {"Authorization": "Bearer test-token"}
    response = client.get("/graph/rings", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert "rings" in data
    assert len(data["rings"]) > 0
    first_ring = data["rings"][0]
    assert "ring_id" in first_ring
    assert "title" in first_ring
    assert "claim_count" in first_ring
    assert "total_amount" in first_ring

    assert "selected_ring" in data
    sel = data["selected_ring"]
    assert sel is not None
    assert "nodes" in sel
    assert "edges" in sel
    assert "claims" in sel
    assert len(sel["nodes"]) > 0
    assert len(sel["edges"]) > 0
    assert len(sel["claims"]) > 0

    first_node = sel["nodes"][0]
    assert "id" in first_node
    assert "label" in first_node
    assert "type" in first_node

    first_edge = sel["edges"][0]
    assert "source" in first_edge
    assert "target" in first_edge
    assert "type" in first_edge
