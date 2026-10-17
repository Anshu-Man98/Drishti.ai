"""
backend/tests/test_fix1_validation.py

Tests for Issue 1: Upload and input validation:
- POST /claims:
    * require at least one file (400)
    * enforce MAX_UPLOAD_MB (413) and total cap (413)
    * check real content magic bytes (415)
    * reject unsupported extensions (415)
    * reject empty files (422)
    * reject corrupt/unreadable files with 422 ("The document could not be read")
    * limit number of files (400)
    * happy path upload (200)
- Distinguish client errors (422) from dependency outages (503 with {"error", "service", "retryable"})
- Chat:
    * reject empty message (422)
    * reject > 2000 chars message (422)
    * reject control characters (422)
- Unknown duel id:
    * GET /duel/{id}/status -> 404
    * GET /duel/{id}/rounds -> 404
"""

import io
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from PIL import Image

from backend.app.main import app
from backend.app.config import settings
from backend.app.exceptions import CloudServiceError

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-adjuster-token"}


def create_valid_pdf_bytes(text: str = "Test Medical Bill") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, text)
    c.save()
    return buf.getvalue()


def create_valid_png_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (50, 50), color="blue")
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_valid_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (50, 50), color="red")
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ==============================================================================
# 1. UPLOAD VALIDATION TESTS
# ==============================================================================

def test_upload_no_files_returns_400():
    """POST /claims with no file must return 400."""
    resp = client.post("/api/claims", data={"claimant_name": "Test User"}, headers=AUTH_HEADERS)
    assert resp.status_code == 400
    assert "At least one file must be uploaded" in resp.json()["detail"]


def test_upload_empty_file_returns_422():
    """POST /claims with 0-byte file must return 422."""
    files = [("files", ("empty.pdf", io.BytesIO(b""), "application/pdf"))]
    resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
    assert resp.status_code == 422
    assert "The document could not be read" in resp.json()["detail"]
    assert "is empty" in resp.json()["detail"]


def test_upload_exceeds_max_file_size_returns_413():
    """POST /claims exceeding MAX_UPLOAD_MB must return 413."""
    # Temporarily set MAX_UPLOAD_MB to 1 MB for testing
    with patch.object(settings, "MAX_UPLOAD_MB", 1):
        big_content = b"%PDF-1.4\n" + b"A" * (1024 * 1024 + 50)
        files = [("files", ("big.pdf", io.BytesIO(big_content), "application/pdf"))]
        resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
        assert resp.status_code == 413
        assert "Payload Too Large" in resp.json()["detail"]


def test_upload_exceeds_total_cap_returns_413():
    """POST /claims exceeding total size cap must return 413."""
    with patch.object(settings, "MAX_TOTAL_UPLOAD_MB", 1), patch.object(settings, "MAX_UPLOAD_MB", 5):
        # Create a valid PDF of ~600 KB by embedding content
        buf1 = io.BytesIO()
        c = canvas.Canvas(buf1)
        for i in range(100):
            c.drawString(50, 700 - (i % 50) * 10, f"Line {i}: " + "X" * 100)
            if i == 49:
                c.showPage()
        c.save()
        base_pdf = buf1.getvalue()
        # Pad after %%EOF
        padded_pdf = base_pdf + b"\n% " + b"Z" * (600 * 1024)

        files = [
            ("files", ("f1.pdf", io.BytesIO(padded_pdf), "application/pdf")),
            ("files", ("f2.pdf", io.BytesIO(padded_pdf), "application/pdf")),
        ]
        resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
        assert resp.status_code == 413
        assert "Total upload size exceeds" in resp.json()["detail"]


def test_upload_exceeds_max_files_returns_400():
    """POST /claims with more than MAX_UPLOAD_FILES must return 400."""
    pdf_bytes = create_valid_pdf_bytes("Test")
    with patch.object(settings, "MAX_UPLOAD_FILES", 3):
        files = [("files", (f"bill_{i}.pdf", io.BytesIO(pdf_bytes), "application/pdf")) for i in range(4)]
        resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert "Maximum 3 files allowed" in resp.json()["detail"]


def test_upload_unsupported_extension_returns_415():
    """POST /claims with unsupported extension must return 415."""
    files = [("files", ("script.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream"))]
    resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
    assert resp.status_code == 415
    assert "Unsupported Media Type" in resp.json()["detail"]


def test_upload_invalid_magic_bytes_returns_415():
    """POST /claims with .pdf extension but non-PDF content must return 415."""
    fake_pdf = b"Hello, this is just plain text disguised as a PDF file."
    files = [("files", ("bill.pdf", io.BytesIO(fake_pdf), "application/pdf"))]
    resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
    assert resp.status_code == 415
    assert "invalid magic bytes" in resp.json()["detail"]


def test_upload_corrupt_pdf_returns_422():
    """POST /claims with corrupt PDF content must return 422 with clear message."""
    corrupt_pdf = b"%PDF-1.5\nMalformed binary junk without xref or trailer\x00\xff\xee"
    files = [("files", ("corrupt.pdf", io.BytesIO(corrupt_pdf), "application/pdf"))]
    resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
    assert resp.status_code == 422
    assert "The document could not be read" in resp.json()["detail"]
    assert "corrupt or unreadable" in resp.json()["detail"]


def test_upload_corrupt_png_returns_422():
    """POST /claims with corrupt PNG content must return 422."""
    corrupt_png = b"\x89PNG\r\n\x1a\nCorrupt header without IHDR chunk\x00\x00"
    files = [("files", ("corrupt.png", io.BytesIO(corrupt_png), "image/png"))]
    resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
    assert resp.status_code == 422
    assert "The document could not be read" in resp.json()["detail"]


def test_upload_dependency_outage_returns_503():
    """Real Document AI outage returns 503 with structured retryable error, no leaked provider text."""
    pdf_bytes = create_valid_pdf_bytes("Test Bill")
    files = [("files", ("bill.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]

    with patch("backend.tools.docai.process_document_docai") as mock_docai:
        mock_docai.side_effect = CloudServiceError(
            service="Document AI",
            message="Document AI service is temporarily unavailable",
            retryable=True
        )
        resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
        assert resp.status_code == 503
        data = resp.json()
        assert data.get("service") == "Document AI"
        assert data.get("retryable") is True


def test_upload_docai_client_error_returns_422_without_leaking_provider_text():
    """Document AI client-side error (e.g. field_violations) returns 422 without leaking raw provider text."""
    pdf_bytes = create_valid_pdf_bytes("Test Bill")
    files = [("files", ("bill.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]

    with patch("backend.tools.docai.process_document_docai") as mock_docai:
        # Simulate Document AI returning field_violations
        mock_docai.side_effect = CloudServiceError(
            service="Document AI",
            message="GoogleAPIError 400: field_violations [FieldViolation(field='raw_document.content')]",
            retryable=False
        )
        resp = client.post("/api/claims", files=files, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert resp.json()["detail"] == "The document could not be read"
        # Ensure raw Google provider string was NOT leaked in response
        assert "field_violations" not in resp.text
        assert "GoogleAPIError" not in resp.text


def test_upload_happy_path():
    """POST /claims with valid PDF returns 200 and created claim."""
    pdf_bytes = create_valid_pdf_bytes("Hospital Bill - Apollo Hospitals Mumbai")
    files = [("files", ("valid_invoice.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    data = {
        "claimant_name": "Ananya Roy",
        "hospital_name": "Apollo Hospitals",
        "city": "Mumbai",
        "total_claimed": "25000.0"
    }
    resp = client.post("/api/claims", data=data, files=files, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "created"
    assert res_data["documents_uploaded"] == 1
    assert res_data["claim_id"].startswith("CLM-")


# ==============================================================================
# 2. CHAT VALIDATION TESTS
# ==============================================================================

def test_chat_empty_message_returns_422():
    """Chat message that is empty or only whitespace returns 422."""
    resp = client.post(
        "/api/claims/CLM-G1-CLEAN-DEMO/chat",
        json={"message": "   \n\t  "},
        headers={**AUTH_HEADERS, "Accept": "application/json"}
    )
    assert resp.status_code == 422


def test_chat_overlong_message_returns_422():
    """Chat message exceeding 2000 characters returns 422."""
    long_msg = "A" * 2005
    resp = client.post(
        "/api/claims/CLM-G1-CLEAN-DEMO/chat",
        json={"message": long_msg},
        headers={**AUTH_HEADERS, "Accept": "application/json"}
    )
    assert resp.status_code == 422


def test_chat_control_characters_returns_422():
    """Chat message with disallowed control characters returns 422."""
    bad_msg = "Hello\x00World\x07Alert"
    resp = client.post(
        "/api/claims/CLM-G1-CLEAN-DEMO/chat",
        json={"message": bad_msg},
        headers={**AUTH_HEADERS, "Accept": "application/json"}
    )
    assert resp.status_code == 422


# ==============================================================================
# 3. DUEL UNKNOWN ID TESTS
# ==============================================================================

def test_duel_unknown_id_status_returns_404():
    """GET /duel/{id}/status for unknown duel must return 404."""
    resp = client.get("/api/duel/duel-does-not-exist-9999/status", headers=AUTH_HEADERS)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_duel_unknown_id_rounds_returns_404():
    """GET /duel/{id}/rounds for unknown duel must return 404."""
    resp = client.get("/api/duel/duel-does-not-exist-9999/rounds", headers=AUTH_HEADERS)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
