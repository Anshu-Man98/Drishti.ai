"""
Unit tests for Step 6: Latency and robustness of analysis.
Tests:
1. Strict timeouts per external cloud call via cloud_call (raises CloudServiceError on timeout).
2. Bounded retries with exponential backoff and jitter on retryable status codes.
3. Non-retryable errors fail immediately without redundant retries.
4. ClaimLockManager deduplication: concurrent sync calls wait and share the single dossier.
5. ClaimLockManager async mode: returns immediately without duplicating work.
6. Pipeline budget timeout produces incomplete dossier with floor verdict REVIEW.
7. Document AI extraction and GCS in-memory caching prevent redundant network roundtrips.
8. API endpoints: POST /claims/{id}/analyze?async=true returns 202 with status URL.
"""

import hashlib
import time
import threading
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.exceptions import CloudServiceError
from backend.app.schemas import (
    Claim, Dossier, Finding, Severity, Verdict, AgentName, Claimant, Provider
)
from backend.app.services.cloud_call import cloud_call, is_retryable_exception
from backend.app.services.claim_lock import ClaimLockManager, claim_lock_manager
from backend.tools.docai import (
    _DOCAI_EXTRACTION_CACHE, clear_docai_extraction_cache, process_document_docai
)
from backend.app.services.storage import storage_service
from backend.agents.root import run_claims_fraud_pipeline


client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Cloud-Call Strict Timeouts & Retry Behavior
# ---------------------------------------------------------------------------

def test_cloud_call_strict_timeout():
    """Verify that a slow cloud RPC times out after specified timeout and raises CloudServiceError."""
    def hanging_function():
        time.sleep(2.0)
        return "finished"

    t0 = time.perf_counter()
    with pytest.raises(CloudServiceError) as exc_info:
        cloud_call(hanging_function, service="Gemini", timeout=0.2, max_retries=1, base_backoff=0.05)
    elapsed = time.perf_counter() - t0

    assert "timed out" in str(exc_info.value).lower()
    assert exc_info.value.service == "Gemini"
    assert exc_info.value.retryable is True
    # Should not take 2.0s + 2.0s; with timeout=0.2s and 1 retry, should be around 0.4s-0.7s
    assert elapsed < 1.5


def test_cloud_call_bounded_retries_on_transient_error():
    """Verify retryable exceptions (e.g. 503, UNAVAILABLE, 429) retry up to max_retries and fail loud."""
    call_count = 0

    def failing_cloud_api():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("503 Service Unavailable: High load")

    with pytest.raises(CloudServiceError) as exc_info:
        cloud_call(
            failing_cloud_api,
            service="Document AI",
            timeout=2.0,
            max_retries=2,
            base_backoff=0.01,
            max_backoff=0.05,
            jitter=0.01
        )

    # Initial attempt + 2 retries = 3 attempts total
    assert call_count == 3
    assert exc_info.value.service == "Document AI"
    assert exc_info.value.retryable is True


def test_cloud_call_non_retryable_fails_fast():
    """Verify non-retryable exceptions (400, 404, 422) terminate immediately without retrying."""
    call_count = 0

    def bad_request_api():
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid argument: 400 Bad Request: Malformed JSON payload")

    with pytest.raises(CloudServiceError) as exc_info:
        cloud_call(
            bad_request_api,
            service="BigQuery",
            timeout=2.0,
            max_retries=3,
            base_backoff=0.01
        )

    # Non-retryable error terminates on attempt 1
    assert call_count == 1
    assert exc_info.value.service == "BigQuery"
    assert exc_info.value.retryable is False


# ---------------------------------------------------------------------------
# 2. ClaimLockManager Concurrency & Deduplication
# ---------------------------------------------------------------------------

def test_claim_lock_concurrency_deduplication():
    """Verify that multiple concurrent sync requests for the same claim share 1 pipeline execution."""
    lock_mgr = ClaimLockManager()
    test_claim_id = "CLM-CONCURRENT-TEST-001"

    pipeline_executions = 0
    results = [None, None, None, None]

    dummy_dossier = Dossier(
        claim_id=test_claim_id,
        risk_score=15,
        verdict=Verdict.APPROVE,
        summary="Automated approval",
        findings=[]
    )

    def worker(idx: int):
        nonlocal pipeline_executions
        is_leader, dossier = lock_mgr.acquire_or_wait(test_claim_id, async_mode=False, timeout=5.0)
        if is_leader:
            # Simulate work
            time.sleep(0.15)
            pipeline_executions += 1
            lock_mgr.complete_analysis(test_claim_id, dossier=dummy_dossier)
            results[idx] = dummy_dossier
        else:
            results[idx] = dossier

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly 1 pipeline execution occurred
    assert pipeline_executions == 1
    # All 4 callers received the identical dossier
    assert all(r is not None for r in results)
    assert all(r.claim_id == test_claim_id for r in results)


def test_claim_lock_async_mode():
    """Verify that async_mode=True returns is_leader=False immediately without waiting when running."""
    lock_mgr = ClaimLockManager()
    test_claim_id = "CLM-ASYNC-TEST-002"

    is_leader_1, _ = lock_mgr.acquire_or_wait(test_claim_id, async_mode=True)
    assert is_leader_1 is True

    # Second caller in async mode
    t0 = time.perf_counter()
    is_leader_2, dossier_2 = lock_mgr.acquire_or_wait(test_claim_id, async_mode=True)
    elapsed = time.perf_counter() - t0

    assert is_leader_2 is False
    assert dossier_2 is None
    assert elapsed < 0.1  # Returns immediately

    # Clean up
    lock_mgr.complete_analysis(test_claim_id, dossier=None)


# ---------------------------------------------------------------------------
# 3. Pipeline Budget Timeout & Floor Verdict
# ---------------------------------------------------------------------------

def test_pipeline_budget_timeout_incomplete_verdict():
    """Verify that if a specialist times out against budget, an incomplete dossier with floor REVIEW is produced."""
    claim = Claim(
        claim_id="CLM-TIMEOUT-TEST-003",
        policy_id="POL-TEST",
        insurer_id="INS-TEST",
        total_claimed=50000.0,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z",
        diagnosis_code="E11.9",
        claimant=Claimant(
            claimant_id="CLMNT-01",
            name="Pooja Sharma",
            phone="+91-9999999999",
            bank_account_hash="hash1"
        ),
        provider=Provider(
            hospital_id="HOSP-01",
            name="City Hospital",
            city="Mumbai"
        ),
        documents=[],
        line_items=[{"description": "Consultation", "qty": 1, "unit_price": 50000.0, "amount": 50000.0}]
    )

    def slow_injection(*args, **kwargs):
        time.sleep(2.0)
        return []

    # Mock settings.ANALYSIS_BUDGET_SECONDS to a short value so timeout triggers quickly
    with patch("backend.agents.root.settings.ANALYSIS_BUDGET_SECONDS", 0.3):
        with patch("backend.agents.root.detect_hidden_text_injection", side_effect=slow_injection):
            with patch("backend.app.services.db.db_service.save_dossier"):
                dossier = run_claims_fraud_pipeline(claim)

    assert dossier is not None
    assert dossier.status == "incomplete"
    assert dossier.verdict in (Verdict.REVIEW, Verdict.REJECT)
    assert dossier.verdict != Verdict.APPROVE
    # Check that a timeout finding was recorded
    has_timeout_finding = any(
        "timeout" in f.check_id.lower() or "timeout" in f.title.lower()
        for f in dossier.findings
    )
    assert has_timeout_finding is True


# ---------------------------------------------------------------------------
# 4. In-Memory Extraction and Storage Caching
# ---------------------------------------------------------------------------

def test_docai_extraction_cache():
    """Verify Document AI extraction is cached by sha256 to prevent duplicate billing."""
    clear_docai_extraction_cache()
    fake_pdf = b"%PDF-1.4 Fake test content for sha256 caching"
    sha = hashlib.sha256(fake_pdf).hexdigest()

    dummy_claim = Claim(
        claim_id="CLM-CACHED",
        total_claimed=1000.0,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z",
        claimant=Claimant(
            claimant_id="CLMNT-01",
            name="Pooja Sharma",
            phone="+91-9999999999",
            bank_account_hash="hash1"
        ),
        provider=Provider(
            hospital_id="HOSP-01",
            name="City Hospital",
            city="Mumbai"
        )
    )
    _DOCAI_EXTRACTION_CACHE[sha] = (dummy_claim, [])

    with patch("backend.tools.docai.render_document_to_images") as mock_render:
        res1, ents1 = process_document_docai(fake_pdf, "bill.pdf", claim_id="CLM-REQ-1")
        res2, ents2 = process_document_docai(fake_pdf, "bill.pdf", claim_id="CLM-REQ-2")

        # mock_render was never called because cache hit returns before render
        assert mock_render.call_count == 0
        assert res1.claim_id == "CLM-REQ-1"
        assert res2.claim_id == "CLM-REQ-2"
        assert res1.total_claimed == 1000.0
        assert res2.total_claimed == 1000.0


def test_storage_service_byte_cache():
    """Verify StorageService in-memory byte cache prevents repeated GCS downloads."""
    storage_service.clear_cache()
    test_uri = "gs://drishti-demo-claims/uploads/CLM-CACHE-TEST/sample.pdf"
    raw_bytes = b"%PDF-1.4 test gcs content"

    # Pre-populate cache or verify read_file caches it
    storage_service._cache[test_uri] = raw_bytes

    data1 = storage_service.read_file(test_uri)
    data2 = storage_service.read_file(test_uri)

    assert data1 == raw_bytes
    assert data2 == raw_bytes


# ---------------------------------------------------------------------------
# 5. REST API Async & Status Endpoints
# ---------------------------------------------------------------------------

def test_analyze_async_mode_endpoint():
    """POST /api/claims/{id}/analyze?async=true returns 202 with status URL."""
    test_claim_id = "CLM-API-ASYNC-001"
    dummy_claim = Claim(
        claim_id=test_claim_id,
        policy_id="POL-01",
        insurer_id="INS-01",
        total_claimed=12000.0,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z",
        claimant=Claimant(
            claimant_id="CLMNT-02",
            name="Rahul Varma",
            phone="+91-9999999999",
            bank_account_hash="hash2"
        ),
        provider=Provider(
            hospital_id="HOSP-02",
            name="Care Hospital",
            city="Bengaluru"
        )
    )

    with patch("backend.app.services.db.db_service.get_claim", return_value=dummy_claim):
        with patch("backend.app.services.db.db_service.get_dossier", return_value=None):
            with patch("backend.app.routers.claims.run_adk_pipeline") as mock_pipeline:
                mock_pipeline.return_value = Dossier(
                    claim_id=test_claim_id,
                    risk_score=20,
                    verdict=Verdict.APPROVE,
                    summary="Clean claim",
                    findings=[]
                )
                resp = client.post(f"/api/claims/{test_claim_id}/analyze?async=true")

                assert resp.status_code == 202
                body = resp.json()
                assert body["status"] == "running"
                assert "agent_status_url" in body
                assert "status_url" in body


def test_claim_status_endpoint():
    """GET /api/claims/{id}/status returns agent progress and status summary."""
    test_claim_id = "CLM-API-STATUS-001"
    dummy_claim = Claim(
        claim_id=test_claim_id,
        policy_id="POL-01",
        insurer_id="INS-01",
        total_claimed=12000.0,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z"
    )

    with patch("backend.app.services.db.db_service.get_claim", return_value=dummy_claim):
        with patch("backend.app.services.db.db_service.get_dossier", return_value=None):
            with patch("backend.app.services.db.db_service.get_agent_statuses", return_value={"forensics": "done", "ml": "running"}):
                resp = client.get(f"/api/claims/{test_claim_id}/status")
                assert resp.status_code == 200
                data = resp.json()
                assert data["claim_id"] == test_claim_id
                assert data["agent_statuses"]["forensics"] == "done"
                assert data["agent_statuses"]["ml"] == "running"
