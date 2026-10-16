"""
Acceptance test suite for F2: Document AI Extraction + Bounding Box Citations.
Validates:
1. 150 DPI page image rendering via pypdfium2.
2. Extraction accuracy across all 6 golden demo claims against ground_truth.json.
3. Bounding box coordinates on G2 (arithmetic mismatch) total row & line items.
4. Bounding box coordinates on G6 (forged document) altered total row.
5. locate_field helper behavior for mapping logical fields to visual evidence citations.
6. API endpoints: GET /claims/{id}/pages/1 and GET /claims/{id}/entities.
"""

import io
import json
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import Claim, ExtractedEntity, Finding
from backend.tools.docai import (
    render_pdf_to_page_images,
    process_document_docai,
    locate_field
)
from backend.agents.policy import analyze_policy_and_arithmetic
from backend.tools.forensics_tools import font_consistency_check

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "data" / "demo"
GROUND_TRUTH_PATH = DEMO_DIR / "ground_truth.json"

client = TestClient(app)


def test_page_image_rendering_150dpi(tmp_path):
    g1_pdf = (DEMO_DIR / "G1_clean_claim.pdf").read_bytes()
    test_claim_id = "CLM-TEST-RENDER-150DPI"
    
    page_uris = render_pdf_to_page_images(g1_pdf, test_claim_id)
    assert len(page_uris) >= 1
    
    # Verify the generated image file from storage
    from backend.app.services.storage import storage_service
    img_bytes = storage_service.read_file(page_uris[0])
    with Image.open(io.BytesIO(img_bytes)) as im:
        assert im.format == "PNG"
        w, h = im.size
        # A4 at 150 dpi is ~1240 x 1754
        assert 1100 <= w <= 1350, f"Expected ~1240 width at 150 dpi, got {w}"
        assert 1600 <= h <= 1900, f"Expected ~1754 height at 150 dpi, got {h}"


def test_docai_extraction_all_six_golden_claims():
    assert GROUND_TRUTH_PATH.exists()
    gt = json.loads(GROUND_TRUTH_PATH.read_text())

    six_golden_keys = ["G1", "G2", "G3", "G4", "G5", "G6"]
    for key in six_golden_keys:
        info = gt[key]
        pdf_path = DEMO_DIR / info["file"]
        assert pdf_path.exists(), f"Demo PDF {info['file']} missing"
        pdf_bytes = pdf_path.read_bytes()

        claim, entities = process_document_docai(pdf_bytes, filename=info["file"], claim_id=f"CLM-{key}")
        
        # 1. Total claimed matches ground truth exactly
        expected_total = info["total_claimed"]
        assert claim.total_claimed == pytest.approx(expected_total, rel=1e-3), (
            f"{key}: extracted total {claim.total_claimed} != expected {expected_total}"
        )

        # 2. Extracted entities exist with valid bounding boxes
        assert len(entities) >= 5, f"{key}: expected >= 5 entities, got {len(entities)}"
        
        # Check supplier and total amount
        supplier_ent = next((e for e in entities if e.field_name == "supplier_name"), None)
        assert supplier_ent is not None, f"{key}: missing supplier_name"
        assert supplier_ent.bbox is not None
        assert len(supplier_ent.bbox) == 4
        assert 0.0 <= supplier_ent.bbox[0] < supplier_ent.bbox[2] <= 1.0

        total_ent = next((e for e in entities if e.field_name == "total_amount"), None)
        assert total_ent is not None, f"{key}: missing total_amount"
        assert total_ent.bbox is not None
        assert len(total_ent.bbox) == 4
        assert 0.0 <= total_ent.bbox[1] < total_ent.bbox[3] <= 1.0

        # 3. Line items have bboxes
        assert len(claim.line_items) >= 4, f"{key}: expected >= 4 line items"
        for item in claim.line_items:
            assert item.bbox is not None, f"{key}: line item '{item.description}' missing bbox"
            assert len(item.bbox) == 4
            assert 0.0 <= item.bbox[0] < item.bbox[2] <= 1.0


def test_g2_arithmetic_mismatch_bounding_boxes():
    g2_bytes = (DEMO_DIR / "G2_arithmetic_mismatch.pdf").read_bytes()
    claim, entities = process_document_docai(g2_bytes, filename="G2_arithmetic_mismatch.pdf", claim_id="CLM-G2-TEST")

    # 1. locate_field returns valid bboxes for math fields
    doc_id = claim.documents[0].doc_id
    sub_ev = locate_field(doc_id, "subtotal", claim)
    assert sub_ev is not None
    assert sub_ev.bbox is not None and len(sub_ev.bbox) == 4

    tot_ev = locate_field(doc_id, "total_claimed", claim)
    assert tot_ev is not None
    assert tot_ev.bbox is not None and len(tot_ev.bbox) == 4

    # 2. Run policy & arithmetic analysis and verify findings carry evidence bounding boxes
    findings = analyze_policy_and_arithmetic(claim)
    assert len(findings) >= 1
    
    # Should have mismatch on total or subtotal
    math_finding = next((f for f in findings if "MISMATCH" in f.check_id), None)
    assert math_finding is not None
    assert len(math_finding.evidence) >= 1
    ev = math_finding.evidence[0]
    assert ev.bbox is not None
    assert len(ev.bbox) == 4
    assert 0.0 <= ev.bbox[0] < ev.bbox[2] <= 1.0


def test_g6_forged_document_bounding_boxes():
    g6_bytes = (DEMO_DIR / "G6_forged_document.pdf").read_bytes()
    doc_id = "DOC-G6-TEST"
    
    anomalies, findings = font_consistency_check(g6_bytes, doc_id=doc_id)
    assert len(findings) >= 1
    
    # Bounding box should cite the tampered total row
    font_finding = findings[0]
    assert len(font_finding.evidence) >= 1
    bbox = font_finding.evidence[0].bbox
    assert bbox is not None and len(bbox) == 4
    # Total row is located in lower half of the page
    assert bbox[1] > 0.45, f"Expected total row in bottom half of page, got y0={bbox[1]}"


def test_api_page_image_and_entities_endpoints():
    g1_path = DEMO_DIR / "G1_clean_claim.pdf"
    
    # 1. Upload G1 via API
    with open(g1_path, "rb") as f:
        resp = client.post(
            "/claims",
            files={"files": ("G1_clean_claim.pdf", f, "application/pdf")},
            data={"policy_id": "POL-AROGYA-88124", "insurer_id": "INS-HDFC"}
        )
    assert resp.status_code == 200, resp.text
    claim_id = resp.json()["claim_id"]

    # 2. Test GET /claims/{id}/pages/1
    page_resp = client.get(f"/claims/{claim_id}/pages/1")
    assert page_resp.status_code == 200
    assert page_resp.headers["content-type"] == "image/png"
    assert len(page_resp.content) > 10000

    # 3. Test GET /claims/{id}/entities
    ent_resp = client.get(f"/claims/{claim_id}/entities")
    assert ent_resp.status_code == 200
    ent_data = ent_resp.json()
    assert "entities" in ent_data
    assert len(ent_data["entities"]) >= 5
    assert all("bbox" in e for e in ent_data["entities"])
