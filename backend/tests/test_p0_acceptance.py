import json
from pathlib import Path
import pypdf
import pandas as pd
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_synthetic_claims_data_distribution():
    claims_csv = DATA_DIR / "claims.csv"
    assert claims_csv.exists(), "claims.csv should exist"
    df = pd.read_csv(claims_csv)
    assert len(df) >= 3000, f"Expected at least 3000 claims, got {len(df)}"

    fraud_rate = df["is_fraud"].mean()
    assert 0.10 <= fraud_rate <= 0.15, f"Fraud rate should be ~12%, got {fraud_rate:.2%}"

    expected_types = {
        "clean", "inflated_line_items", "arithmetic_mismatch", "policy_cap_breach",
        "duplicate_bill", "cross_insurer_duplicate", "impossible_travel",
        "shared_bank_account_ring", "forged_document"
    }
    present_types = set(df["fraud_type"].unique())
    assert expected_types.issubset(present_types), f"Missing fraud types: {expected_types - present_types}"


def test_six_golden_demo_pdfs():
    demo_dir = DATA_DIR / "demo"
    expected_files = [
        "G1_clean_claim.pdf",
        "G2_arithmetic_mismatch.pdf",
        "G3_policy_cap_breach.pdf",
        "G4_cross_insurer_duplicate.pdf",
        "G5_impossible_travel.pdf",
        "G6_forged_document.pdf"
    ]
    for fname in expected_files:
        pdf_path = demo_dir / fname
        assert pdf_path.exists(), f"Golden PDF {fname} must exist"
        reader = pypdf.PdfReader(str(pdf_path))
        assert len(reader.pages) >= 1, f"PDF {fname} should have at least 1 page"

    # Verify G6 metadata contains image editor producer
    g6_reader = pypdf.PdfReader(str(demo_dir / "G6_forged_document.pdf"))
    meta = g6_reader.metadata
    assert "Adobe Photoshop" in str(meta.producer), f"G6 producer should be Photoshop, got {meta.producer}"
    assert meta.get("/ModDate") != meta.get("/CreationDate"), "G6 ModDate should differ from CreationDate"


def test_policy_documents_and_rules():
    rules_file = DATA_DIR / "policies" / "rules.json"
    assert rules_file.exists(), "policies/rules.json must exist"
    with open(rules_file) as f:
        rules_data = json.load(f)

    assert "policies" in rules_data
    arogya = rules_data["policies"]["AROGYA_SANJEEVANI"]
    clause_ids = [r["clause_id"] for r in arogya["rules"]]
    assert "Clause 3.1" in clause_ids, "Arogya Sanjeevani must include Clause 3.1 room rent cap"

    # Check synthetic policies
    synth_dir = DATA_DIR / "policies" / "synthetic"
    assert (synth_dir / "care_plus_comprehensive_policy.pdf").exists()
    assert (synth_dir / "optima_shield_standard_policy.pdf").exists()


def test_external_evaluation_datasets():
    # Provider fraud table / dataset
    ext_prov = DATA_DIR / "external" / "kaggle_provider_fraud" / "ext_provider_fraud.csv"
    assert ext_prov.exists(), "ext_provider_fraud.csv must exist"
    df_prov = pd.read_csv(ext_prov)
    assert len(df_prov) > 0, "ext_provider_fraud.csv must have rows"
    assert "is_fraud" in df_prov.columns
    assert "avg_reimbursement" in df_prov.columns
    assert "inpatient_mix" in df_prov.columns

    # Manifests
    fia_manifest = DATA_DIR / "external" / "find_it_again" / "manifest.jsonl"
    assert fia_manifest.exists(), "Find it again manifest must exist"
    with open(fia_manifest) as f:
        fia_rows = [json.loads(line) for line in f if line.strip()]
    assert len(fia_rows) > 0

    aiforge_manifest = DATA_DIR / "external" / "aiforge_doc" / "manifest.jsonl"
    assert aiforge_manifest.exists(), "AIForge-Doc manifest must exist"
    with open(aiforge_manifest) as f:
        aiforge_rows = [json.loads(line) for line in f if line.strip()]
    assert len(aiforge_rows) > 0

    # Licenses
    assert (DATA_DIR / "external" / "LICENSES.md").exists()


def test_seed_and_claims_api_flow():
    # Test uploading G1 clean claim through API
    g1_pdf = DATA_DIR / "demo" / "G1_clean_claim.pdf"
    with open(g1_pdf, "rb") as f:
        pdf_bytes = f.read()

    files = [("files", ("G1_clean_claim.pdf", pdf_bytes, "application/pdf"))]
    data = {
        "policy_id": "POL-AROGYA-88124",
        "insurer_id": "INS-HDFC",
        "claimant_id": "CLMNT-8921",
        "claimant_name": "Rohan Verma",
        "claimant_phone": "+91-9876543210",
        "bank_account_hash": "a1b2c3d4e5f60718",
        "hospital_id": "HOSP-101",
        "hospital_name": "Max Super Speciality Hospital",
        "city": "New Delhi",
        "lat": "28.5284",
        "lng": "77.2185",
        "doctor_id": "DOC-2045",
        "admission_ts": "2026-03-12T09:30:00",
        "discharge_ts": "2026-03-15T11:00:00",
        "diagnosis_code": "K35.8",
        "subtotal": "71000.0",
        "tax": "3550.0",
        "total_claimed": "74550.0",
        "line_items_json": json.dumps([
            {"description": "Semi-Private Room Rent (3 days)", "qty": 3, "unit_price": 4000.0, "amount": 12000.0},
            {"description": "Laparoscopic Appendectomy Surgery & OT", "qty": 1, "unit_price": 45000.0, "amount": 45000.0}
        ])
    }

    res = client.post("/api/claims", data=data, files=files)
    assert res.status_code == 200
    claim_id = res.json()["claim_id"]

    # Verify claim retrieval
    get_res = client.get(f"/api/claims/{claim_id}")
    assert get_res.status_code == 200
    claim_data = get_res.json()
    assert claim_data["claim_id"] == claim_id
    assert len(claim_data["documents"]) == 1

    # Verify document retrieval
    doc_id = claim_data["documents"][0]["doc_id"]
    doc_res = client.get(f"/api/claims/{claim_id}/documents/{doc_id}")
    assert doc_res.status_code == 200
    assert len(doc_res.content) > 0

    # Verify analyze creates dossier
    an_res = client.post(f"/api/claims/{claim_id}/analyze")
    assert an_res.status_code == 200
    dossier = an_res.json()
    assert dossier["claim_id"] == claim_id
    assert dossier["verdict"] in ["approve", "review", "reject"]
