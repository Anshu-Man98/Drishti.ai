import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "models" in data
    assert "pro" in data["models"]
    assert "flash" in data["models"]


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
