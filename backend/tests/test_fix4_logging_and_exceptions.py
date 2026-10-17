"""
Unit and integration tests for Fix 4:
- Silent exception swallowing elimination & logging refactor
- DrishtiError custom hierarchy replacing raw HTTPException(500)
- Upstream cloud service outages (Document AI, Vertex Gemini, BigQuery) must NOT return empty findings silently
- Dossier must be marked status: "incomplete", verdict: "REVIEW", UI agent status: "error", with visible error finding
"""

import json
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import Claim, Provider, Claimant, LineItem, Document, Verdict, Severity, AgentName
from backend.app.exceptions import (
    DrishtiError,
    CloudServiceError,
    DocumentProcessingError,
    StorageError,
    AgentExecutionError,
    AnalyticsError,
    ProvenanceSigningError,
    DatabaseError
)
from backend.app.logging_config import StructuredJsonFormatter
from backend.agents.root import run_claims_fraud_pipeline
from backend.app.services.db import db_service


# ==============================================================================
# 1. DRISHTI EXCEPTION HIERARCHY TESTS
# ==============================================================================

def test_drishti_error_hierarchy():
    base_err = DrishtiError("Base failure", status_code=500, code="base_error", details={"foo": "bar"})
    assert base_err.status_code == 500
    assert base_err.to_dict()["error"] == "Base failure"
    assert base_err.to_dict()["details"] == {"foo": "bar"}

    cloud_err = CloudServiceError("bigquery", "BQ unreachable", retryable=True)
    assert isinstance(cloud_err, DrishtiError)
    assert cloud_err.status_code == 503
    assert cloud_err.to_dict() == {
        "error": "BQ unreachable",
        "service": "bigquery",
        "retryable": True
    }

    storage_err = StorageError("GCS read failed", doc_id="DOC-1")
    assert isinstance(storage_err, DrishtiError)
    assert storage_err.status_code == 500
    assert storage_err.details["doc_id"] == "DOC-1"

    signing_err = ProvenanceSigningError("Ed25519 signing failed", doc_id="DOC-2")
    assert isinstance(signing_err, DrishtiError)
    assert signing_err.status_code == 500

    analytics_err = AnalyticsError("Analytics failed")
    assert isinstance(analytics_err, DrishtiError)
    assert analytics_err.status_code == 500


def test_drishti_error_global_handler():
    client = TestClient(app)
    # When analytics fails, it raises AnalyticsError, which global handler converts to 500 JSON
    with patch("backend.app.services.db.db_service.list_claims", side_effect=RuntimeError("Firestore connection refused")):
        resp = client.get("/api/analytics/summary", headers={"Authorization": "Bearer dev-token-adjuster"})
        assert resp.status_code == 500
        data = resp.json()
        assert "error" in data
        assert data["code"] == "analytics_error"


# ==============================================================================
# 2. STRUCTURED JSON LOGGING TESTS
# ==============================================================================

def test_structured_json_formatter():
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="finshield.test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=42,
        msg="Specialist execution error: %s",
        args=("Connection timed out",),
        exc_info=None
    )
    record.claim_id = "CLM-TEST-001"
    record.specialist_id = "forensics"
    record.latency_ms = 145.25

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "ERROR"
    assert parsed["logger"] == "finshield.test"
    assert "Specialist execution error: Connection timed out" in parsed["message"]
    assert parsed["claim_id"] == "CLM-TEST-001"
    assert parsed["specialist_id"] == "forensics"
    assert parsed["latency_ms"] == 145.25
    assert "timestamp" in parsed


# ==============================================================================
# 3. SIMULATED CLOUD OUTAGE TESTS (Doc AI / Vertex / BigQuery)
# ==============================================================================

@pytest.fixture
def clean_base_claim():
    return Claim(
        claim_id="CLM-OUTAGE-CLEAN-01",
        insurer_id="INS-001",
        policy_id="POL-CARE-001",
        claimant=Claimant(claimant_id="C-101", name="Rohan Verma", phone="+919876543210", bank_account_hash="ba_1234"),
        provider=Provider(hospital_id="H-KCH-01", name="Lotus Care Hospital", city="Kochi", lat=9.9312, lng=76.2673),
        doctor_id="DOC-9001",
        admission_ts=datetime(2026, 9, 10, 9, 0),
        discharge_ts=datetime(2026, 9, 12, 12, 0),
        diagnosis_code="E11.9",
        line_items=[
            LineItem(description="Consultation", qty=2, unit_price=800, amount=1600),
            LineItem(description="Ward Bed Charges", qty=2, unit_price=2500, amount=5000),
        ],
        subtotal=6600,
        tax=0,
        total_claimed=6600,
        documents=[
            Document(doc_id="DOC-01", doc_type="bill", gcs_uri="file:///tmp/dummy.pdf", filename="dummy.pdf", sha256="abc123")
        ]
    )


def test_simulated_bigquery_ml_outage(clean_base_claim):
    """
    Simulated BigQuery outage: ML.EXPLAIN_PREDICT returns 500 / CloudServiceError.
    Pipeline must NOT silently approve with 0 findings.
    Dossier must be status: "incomplete", verdict: "REVIEW", and hold a visible error finding.
    """
    with patch("backend.tools.bq.ml_score") as mock_bqml, \
         patch("backend.app.services.storage.storage_service.read_file", return_value=b"%PDF-1.4 clean doc"):
        mock_bqml.side_effect = CloudServiceError(
            service="bigquery",
            message="500 Internal Server Error: BigQuery ML service is unreachable",
            retryable=True
        )

        dossier = run_claims_fraud_pipeline(clean_base_claim)

        # 1. Dossier must be marked incomplete
        assert dossier.status == "incomplete", f"Expected status 'incomplete' but got '{dossier.status}'"

        # 2. Verdict must NEVER be APPROVE
        assert dossier.verdict == Verdict.REVIEW, f"Expected verdict REVIEW but got {dossier.verdict}"

        # 3. Must hold a visible error finding explaining the failure
        ml_err_finding = next((f for f in dossier.findings if f.check_id in ("AGENT_FAILED:ml", "BQML_SERVICE_FAILURE")), None)
        assert ml_err_finding is not None, "Dossier must contain visible ML failure finding"
        assert ml_err_finding.severity == Severity.HIGH
        assert "BigQuery ML" in ml_err_finding.title
        assert "500" in ml_err_finding.explanation or "unreachable" in ml_err_finding.explanation

        # 4. Agent status in DB must be "error"
        statuses = db_service.get_agent_statuses(clean_base_claim.claim_id)
        assert statuses.get("ml") == "error", f"Expected ml status 'error', got {statuses.get('ml')}"


def test_simulated_vertex_gemini_outage(clean_base_claim):
    """
    Simulated Vertex AI / Gemini outage: live Gemini call throws 500 / CloudServiceError.
    Pipeline must NOT silently swallow the error.
    Dossier must be status: "incomplete", verdict: "REVIEW", forensics agent status: "error".
    """
    with patch("backend.agents.forensics.gemini_visual_review") as mock_gemini, \
         patch("backend.agents.forensics.font_consistency_check", return_value=([{"page": 1, "text": "altered line"}], [])), \
         patch("backend.app.services.storage.storage_service.read_file", return_value=b"%PDF-1.4 clean doc"):
        mock_gemini.side_effect = CloudServiceError(
            service="Gemini",
            message="500 Internal Server Error: Vertex AI Gemini endpoint failure",
            retryable=True
        )

        dossier = run_claims_fraud_pipeline(clean_base_claim)

        # 1. Dossier status must be incomplete
        assert dossier.status == "incomplete"

        # 2. Verdict must NEVER be APPROVE
        assert dossier.verdict == Verdict.REVIEW

        # 3. Must contain visible Forensics failure finding
        foren_err = next((f for f in dossier.findings if f.check_id == "AGENT_FAILED:forensics"), None)
        assert foren_err is not None, "Dossier must contain visible forensics error finding"
        assert "Forensics specialist failed" in foren_err.title
        assert "Vertex AI" in foren_err.explanation or "500" in foren_err.explanation

        # 4. Forensics agent status must be "error"
        statuses = db_service.get_agent_statuses(clean_base_claim.claim_id)
        assert statuses.get("forensics") == "error"


def test_simulated_document_ai_outage():
    """
    Simulated Document AI outage: process_document_docai returns 500 / CloudServiceError.
    Pipeline must NOT return empty findings or approve silently.
    Dossier must be status: "incomplete", verdict: "REVIEW", with visible DocAI error finding.
    """
    unextracted_claim = Claim(
        claim_id="CLM-OUTAGE-DOCAI-01",
        insurer_id="INS-001",
        policy_id="POL-001",
        claimant=Claimant(claimant_id="C-99", name="Aarav Sharma", phone="+919876543210", bank_account_hash="ba_5678"),
        provider=Provider(hospital_id="H-01", name="City Hospital", city="Delhi"),
        total_claimed=0.0,
        documents=[
            Document(doc_id="DOC-UNEXTRACTED", doc_type="bill", gcs_uri="file:///tmp/unextracted.pdf", filename="bill.pdf", sha256="123")
        ]
    )

    with patch("backend.tools.docai.process_document_docai") as mock_docai, \
         patch("backend.app.services.storage.storage_service.read_file", return_value=b"%PDF-1.4 raw document"):
        mock_docai.side_effect = CloudServiceError(
            service="Document AI",
            message="500 Internal Server Error: Document AI processor is unavailable",
            retryable=True
        )

        dossier = run_claims_fraud_pipeline(unextracted_claim)

        # 1. Dossier status must be incomplete
        assert dossier.status == "incomplete"

        # 2. Verdict must NEVER be APPROVE
        assert dossier.verdict == Verdict.REVIEW

        # 3. Must contain visible error finding
        err_finding = next((f for f in dossier.findings if "docai" in f.check_id.lower() or "unreadable" in f.check_id.lower()), None)
        assert err_finding is not None
        assert err_finding.severity == Severity.HIGH

        # 4. Agent status shows error
        statuses = db_service.get_agent_statuses(unextracted_claim.claim_id)
        assert statuses.get("forensics") == "error"


def test_simulated_warehouse_crossref_outage(clean_base_claim):
    """
    Simulated BigQuery warehouse outage during crossref duplicate queries.
    Specialist must handle gracefully without crashing root pipeline,
    recording agent error status and holding claim in incomplete / REVIEW.
    """
    with patch("backend.tools.bq.bq_warehouse.find_exact_duplicates") as mock_exact, \
         patch("backend.app.services.storage.storage_service.read_file", return_value=b"%PDF-1.4 clean doc"):
        mock_exact.side_effect = CloudServiceError(
            service="bigquery",
            message="500 Internal Server Error: BigQuery warehouse query failed",
            retryable=True
        )

        dossier = run_claims_fraud_pipeline(clean_base_claim)

        assert dossier.status == "incomplete"
        assert dossier.verdict == Verdict.REVIEW

        cross_err = next((f for f in dossier.findings if f.check_id == "AGENT_FAILED:crossref"), None)
        assert cross_err is not None
        assert "Cross-reference specialist failed" in cross_err.title

        statuses = db_service.get_agent_statuses(clean_base_claim.claim_id)
        assert statuses.get("crossref") == "error"


# ==============================================================================
# 4. AST LINT TEST: NO SILENT EXCEPTION SWALLOWING IN BACKEND
# ==============================================================================

def test_no_silent_exception_swallowing_in_backend():
    """
    AST lint test over backend/ ensuring zero silent broad exception swallowing
    ('except Exception: pass' or bare 'except: pass') ever re-enters the codebase.
    """
    import os
    import ast
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent
    violations = []

    for root, dirs, files in os.walk(backend_dir):
        for f in files:
            if f.endswith(".py"):
                path = Path(root) / f
                rel_path = path.relative_to(backend_dir.parent)
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                try:
                    tree = ast.parse(content, filename=str(path))
                except SyntaxError:
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Try):
                        for handler in node.handlers:
                            # Check if handler body is just a Pass
                            is_silent = (
                                len(handler.body) == 1 and
                                (isinstance(handler.body[0], ast.Pass) or
                                 (isinstance(handler.body[0], ast.Expr) and isinstance(getattr(handler.body[0], "value", None), ast.Constant) and handler.body[0].value.value is ...))
                            )
                            if is_silent:
                                is_broad = False
                                if handler.type is None:
                                    is_broad = True
                                elif isinstance(handler.type, ast.Name) and handler.type.id in ("Exception", "BaseException"):
                                    is_broad = True

                                if is_broad:
                                    violations.append(f"{rel_path}:{handler.lineno} silent broad exception pass")

    assert not violations, f"Found {len(violations)} silent exception swallowing sites:\n" + "\n".join(violations)
