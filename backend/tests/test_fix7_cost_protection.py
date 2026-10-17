"""
Unit tests for Step 7: Cost protection and operations.

Tests:
1. 429 Too Many Requests with Retry-After when rate limit exceeded.
2. 409 Conflict / 202 Accepted on concurrent analysis re-run.
3. BigQuery maximum_bytes_billed guardrail gracefully handled when query scans exceed limit.
4. Gemini LLM token budget hard cap (30,000 tokens) handled gracefully:
   dossier marked incomplete, floored at REVIEW, summary notes budget exceeded, token/cost tracked.
5. 304 Not Modified on unchanged dossier via ETag / If-None-Match.
6. Cache-Control and ETag on page images and fraud network graph.
7. In-process operational telemetry via GET /metrics and GET /health.
"""

import time
from datetime import datetime
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.schemas import (
    Claim, Dossier, Finding, Severity, Verdict, AgentName, Claimant, Provider
)
from backend.app.services.rate_limiter import rate_limit_manager
from backend.app.services.claim_lock import claim_lock_manager
from backend.app.services.token_budget import token_budget_tracker, TokenBudgetExceededError
from backend.app.services.metrics import metrics_service
from backend.app.services.db import db_service
from backend.tools.bq import bq_warehouse
from backend.agents.synthesizer import synthesize_dossier

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_isolation():
    """Resets rate limiter, token budget, and claim locks between tests."""
    settings.RATE_LIMIT_ENABLED = True
    rate_limit_manager.clear()
    token_budget_tracker.clear()
    claim_lock_manager.clear()
    metrics_service.clear()
    yield
    settings.RATE_LIMIT_ENABLED = False
    rate_limit_manager.clear()
    token_budget_tracker.clear()
    claim_lock_manager.clear()
    metrics_service.clear()


# ---------------------------------------------------------------------------
# 1. Rate Limiting (429 with Retry-After)
# ---------------------------------------------------------------------------

def test_rate_limit_manager_sliding_window():
    """Verifies sliding window rate limit calculation and Retry-After header."""
    key = "test_key"
    limit = 3

    # First 3 requests allowed
    for _ in range(limit):
        allowed, retry_after = rate_limit_manager.check(key, max_requests=limit, window_seconds=60.0)
        assert allowed is True
        assert retry_after == 0

    # 4th request blocked
    allowed, retry_after = rate_limit_manager.check(key, max_requests=limit, window_seconds=60.0)
    assert allowed is False
    assert retry_after >= 1
    assert retry_after <= 60


def test_rate_limit_endpoint_returns_429_with_retry_after():
    """Verifies that exceeding per-minute call limit on write endpoints returns 429 with Retry-After."""
    claim_id = "CLM-RATE-LIMIT-CHAT"
    claim = Claim(
        claim_id=claim_id,
        policy_id="POL-TEST",
        insurer_id="INS-TEST",
        total_claimed=15000.0,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z",
        diagnosis_code="E11.9",
        claimant=Claimant(claimant_id="CLMNT-1", name="Test User", phone="+91-9876543210", bank_account_hash="hash1"),
        provider=Provider(hospital_id="HOSP-1", name="City Hospital", city="Pune")
    )
    db_service.save_claim(claim)

    auth = "Bearer test-adjuster-token"
    token_fp = auth[-12:]  # "juster-token"
    # TestClient IP is 'testclient'
    key = f"chat:testclient:{token_fp}"

    # Saturate rate limit for chat
    for _ in range(settings.RATE_LIMIT_CHATS_PER_MIN):
        rate_limit_manager.check(key, max_requests=settings.RATE_LIMIT_CHATS_PER_MIN, window_seconds=60.0)

    # Next chat call must fail with 429
    resp = client.post(
        f"/api/claims/{claim_id}/chat",
        json={"message": "Please explain finding F1."},
        headers={"Authorization": auth}
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    retry_after = int(resp.headers["Retry-After"])
    assert retry_after >= 1
    assert "Rate limit" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Concurrent Analysis Lock (409 Conflict & 202 Accepted)
# ---------------------------------------------------------------------------

def test_concurrent_analysis_returns_409_when_conflict_requested():
    """Verifies that rapid re-run on an active analysis returns 409 Conflict if conflict mode requested."""
    test_claim_id = "CLM-CONCURRENT-LOCK-409"
    claim = Claim(
        claim_id=test_claim_id,
        policy_id="POL-TEST",
        insurer_id="INS-TEST",
        total_claimed=15000.0,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z",
        diagnosis_code="E11.9",
        claimant=Claimant(claimant_id="CLMNT-1", name="Test User", phone="+91-9876543210", bank_account_hash="hash1"),
        provider=Provider(hospital_id="HOSP-1", name="City Hospital", city="Pune")
    )
    db_service.save_claim(claim)

    # Acquire lock to simulate running analysis
    is_leader, _ = claim_lock_manager.acquire_or_wait(test_claim_id, async_mode=True)
    assert is_leader is True
    assert claim_lock_manager.is_running(test_claim_id) is True

    # Concurrent request with X-Conflict-On-Concurrent header
    resp = client.post(
        f"/api/claims/{test_claim_id}/analyze",
        headers={
            "Authorization": "Bearer test-adjuster-token",
            "X-Conflict-On-Concurrent": "true"
        }
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "Analysis already in progress"
    assert body["claim_id"] == test_claim_id


def test_concurrent_analysis_returns_202_without_duplicate_run():
    """Verifies that rapid re-run on an active analysis in async mode returns 202 without spawning duplicates."""
    test_claim_id = "CLM-CONCURRENT-LOCK-202"
    claim = Claim(
        claim_id=test_claim_id,
        policy_id="POL-TEST",
        insurer_id="INS-TEST",
        total_claimed=15000.0,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z",
        diagnosis_code="E11.9",
        claimant=Claimant(claimant_id="CLMNT-1", name="Test User", phone="+91-9876543210", bank_account_hash="hash1"),
        provider=Provider(hospital_id="HOSP-1", name="City Hospital", city="Pune")
    )
    db_service.save_claim(claim)

    # Acquire lock to simulate running analysis
    is_leader, _ = claim_lock_manager.acquire_or_wait(test_claim_id, async_mode=True)
    assert is_leader is True

    # Concurrent request with ?async=true
    resp = client.post(
        f"/api/claims/{test_claim_id}/analyze?async=true",
        headers={"Authorization": "Bearer test-adjuster-token"}
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["claim_id"] == test_claim_id


# ---------------------------------------------------------------------------
# 3. BigQuery Guardrails (maximum_bytes_billed)
# ---------------------------------------------------------------------------

def test_bigquery_maximum_bytes_billed_guardrail():
    """Verifies that BigQuery query jobs carry maximum_bytes_billed guardrail and handle limit exceptions gracefully."""
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.result.side_effect = Exception("Query exceeded limit for bytes billed: 125829120. Limit was 52428800.")
    mock_client.query.return_value = mock_job

    orig_client = bq_warehouse._client
    bq_warehouse._client = mock_client
    try:
        # query_rows should not crash the request; it must return an empty list gracefully
        res = bq_warehouse.query_rows("SELECT * FROM large_table", timeout=5.0)
        assert res == []

        # Verify job_config had maximum_bytes_billed attached
        call_args = mock_client.query.call_args
        cfg = call_args.kwargs.get("job_config")
        assert cfg is not None
        assert getattr(cfg, "maximum_bytes_billed", None) == settings.BQ_MAX_BYTES_BILLED
    finally:
        bq_warehouse._client = orig_client


# ---------------------------------------------------------------------------
# 4. LLM Token Budget Hard Cap & Tracker
# ---------------------------------------------------------------------------

def test_token_budget_tracker_hard_cap_exceeded():
    """Verifies that exceeding the 30,000 token limit raises TokenBudgetExceededError."""
    claim_id = "CLM-TOKEN-TEST-001"
    budget = settings.MAX_CLAIM_LLM_TOKENS  # 30,000

    # Consume 25,000 tokens (within budget)
    total = token_budget_tracker.record_usage(
        claim_id=claim_id,
        prompt_tokens=20000,
        candidate_tokens=5000,
        model="gemini-2.5-flash"
    )
    assert total == 25000

    tokens_spent, cost_usd = token_budget_tracker.get_claim_usage(claim_id)
    assert tokens_spent == 25000
    assert cost_usd > 0.0

    # Consume another 6,000 tokens (total 31,000 > 30,000) -> must raise TokenBudgetExceededError
    with pytest.raises(TokenBudgetExceededError) as exc_info:
        token_budget_tracker.record_usage(
            claim_id=claim_id,
            prompt_tokens=5000,
            candidate_tokens=1000,
            model="gemini-2.5-flash"
        )
    assert exc_info.value.claim_id == claim_id
    assert exc_info.value.tokens_spent == 31000
    assert exc_info.value.token_budget == budget


def test_token_budget_exceeded_handled_gracefully_in_synthesizer():
    """
    Verifies that when LLM token budget is exceeded:
    - Dossier status is 'incomplete'
    - Final verdict floor is REVIEW (never APPROVE)
    - Summary includes note 'LLM token budget exceeded'
    - Dossier captures llm_tokens_spent and cost_usd
    """
    claim_id = "CLM-TOKEN-SYNTH-002"
    claim = Claim(
        claim_id=claim_id,
        policy_id="POL-AROGYA",
        insurer_id="INS-HDFC",
        total_claimed=11917.50,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z",
        diagnosis_code="E11.9",
        claimant=Claimant(claimant_id="CLMNT-1", name="Pooja Sharma", phone="+91-9876543210", bank_account_hash="hash1"),
        provider=Provider(hospital_id="HOSP-1", name="Lotus Care Hospital", city="Kochi")
    )

    # Record 31,000 tokens
    with pytest.raises(TokenBudgetExceededError):
        token_budget_tracker.record_usage(claim_id, 25000, 6000)

    # Synthesize dossier with a TOKEN_BUDGET_EXCEEDED finding
    findings = [
        Finding(
            finding_id="F-ERR-TOKEN-BUDGET",
            agent=AgentName.FORENSICS,
            check_id="TOKEN_BUDGET_EXCEEDED",
            severity=Severity.HIGH,
            title="LLM token budget exceeded",
            explanation=f"LLM token budget exceeded for claim {claim_id}: 31000 > 30000. Dossier marked incomplete.",
            evidence=[],
            confidence=1.0,
            computed_chip="Token Budget Exceeded"
        )
    ]

    dossier = synthesize_dossier(claim=claim, all_findings=findings, ml_score=0.10)

    assert dossier.status == "incomplete"
    assert dossier.verdict == Verdict.REVIEW  # Must floor at REVIEW, never APPROVE
    assert dossier.risk_score >= 45
    assert "LLM token budget exceeded" in dossier.summary
    assert dossier.llm_tokens_spent == 31000
    assert dossier.cost_usd > 0.0


# ---------------------------------------------------------------------------
# 5. Caching and ETags (304 Not Modified)
# ---------------------------------------------------------------------------

def test_dossier_etag_and_304_not_modified():
    """Verifies that GET /claims/{id}/dossier returns ETag and handles 304 Not Modified."""
    claim_id = "CLM-ETAG-TEST-001"
    claim = Claim(
        claim_id=claim_id,
        policy_id="POL-AROGYA",
        insurer_id="INS-HDFC",
        total_claimed=11917.50,
        admission_ts="2026-09-10T09:00:00Z",
        discharge_ts="2026-09-12T12:00:00Z",
        diagnosis_code="E11.9",
        claimant=Claimant(claimant_id="CLMNT-1", name="Pooja Sharma", phone="+91-9876543210", bank_account_hash="hash1"),
        provider=Provider(hospital_id="HOSP-1", name="Lotus Care Hospital", city="Kochi")
    )
    dossier = Dossier(
        claim_id=claim_id,
        risk_score=15,
        verdict=Verdict.APPROVE,
        status="complete",
        summary="Audit completed cleanly.",
        findings=[],
        created_at=datetime.utcnow()
    )
    db_service.save_claim(claim)
    db_service.save_dossier(dossier)

    headers = {"Authorization": "Bearer test-adjuster-token"}

    # 1. First fetch
    resp1 = client.get(f"/api/claims/{claim_id}/dossier", headers=headers)
    assert resp1.status_code == 200
    assert "ETag" in resp1.headers
    assert "Cache-Control" in resp1.headers
    assert "max-age=60" in resp1.headers["Cache-Control"]
    etag = resp1.headers["ETag"]

    # 2. Subsequent fetch with If-None-Match matching ETag -> 304 Not Modified
    headers_with_etag = dict(headers)
    headers_with_etag["If-None-Match"] = etag
    resp2 = client.get(f"/api/claims/{claim_id}/dossier", headers=headers_with_etag)
    assert resp2.status_code == 304
    assert resp2.content == b""  # Zero byte payload on 304
    assert resp2.headers["ETag"] == etag


def test_fraud_network_caching_and_etag():
    """Verifies that GET /graph/rings and /network return ETag and Cache-Control."""
    headers = {"Authorization": "Bearer test-adjuster-token"}

    resp = client.get("/api/graph/rings", headers=headers)
    assert resp.status_code == 200
    assert "ETag" in resp.headers
    assert "Cache-Control" in resp.headers
    etag = resp.headers["ETag"]

    # 304 check on rings
    resp_304 = client.get("/api/graph/rings", headers={**headers, "If-None-Match": etag})
    assert resp_304.status_code == 304

    # /network alias endpoint
    resp_net = client.get("/api/graph/network", headers=headers)
    assert resp_net.status_code == 200


# ---------------------------------------------------------------------------
# 6. Operational Telemetry (/metrics & /health)
# ---------------------------------------------------------------------------

def test_operational_metrics_endpoint():
    """Verifies operational telemetry exposed at GET /metrics and included in GET /health."""
    # Simulate recorded claim activity
    metrics_service.record_analysis(latency_seconds=3.2, success=True, tokens=1500, bq_bytes=204800)
    metrics_service.record_analysis(latency_seconds=5.8, success=True, tokens=2200, bq_bytes=409600)

    # 1. GET /metrics
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_claims_analyzed"] == 2
    assert data["successful_analyses"] == 2
    assert data["failed_analyses"] == 0
    assert data["error_rate"] == 0.0
    assert data["latency_p50_seconds"] > 0.0
    assert data["latency_p95_seconds"] >= data["latency_p50_seconds"]
    assert data["total_llm_tokens"] >= 3700
    assert data["total_bq_bytes_billed"] >= 614400

    # 2. GET /health includes metrics
    resp_health = client.get("/health")
    assert resp_health.status_code in (200, 503)
    health_data = resp_health.json()
    assert "metrics" in health_data
    assert health_data["metrics"]["total_claims_analyzed"] == 2


# ---------------------------------------------------------------------------
# 7. Security Headers Hardening
# ---------------------------------------------------------------------------

def test_security_headers_present_on_api_responses():
    """Validates that security headers (nosniff, DENY, no-referrer) are attached to responses."""
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"


# ---------------------------------------------------------------------------
# 8. Provenance Renaming & Backwards Compatibility
# ---------------------------------------------------------------------------

def test_provenance_letter_issued_before_rename_still_verifies():
    """
    Validates that sanction documents issued with legacy FINSHIELD-DEMO signing
    payloads still verify genuine, and that user-facing API messages state 'Drishti'
    without mentioning 'issued by FinShield'.
    """
    claim_id = "CLM-TEST-PROV-RENAME"
    claim = Claim(
        claim_id=claim_id,
        policy_id="POL-CARE-2026",
        insurer_id="INS-CARE",
        claimant=Claimant(
            claimant_id="CLMNT-P1",
            name="Rahul Sharma",
            phone="+91-9876543210",
            bank_account_hash="bank_hash_prov_test"
        ),
        provider=Provider(
            hospital_id="HOSP-P1",
            name="City Hospital",
            city="Delhi"
        ),
        diagnosis_code="K80.2",
        subtotal=47619.05,
        tax=2380.95,
        total_claimed=50000.0,
        documents=[]
    )
    db_service.save_claim(claim)

    # Issue approval letter
    r_issue = client.post(
        f"/api/claims/{claim_id}/issue-approval",
        json={"amount_paise": 5000000, "notes": "Approved in full."}
    )
    assert r_issue.status_code == 200
    issue_data = r_issue.json()

    # Download PDF
    r_dl = client.get(issue_data["download_url"])
    assert r_dl.status_code == 200
    pdf_bytes = r_dl.content

    # Verify document via /api/provenance/verify
    files = {"file": ("sanction_letter.pdf", pdf_bytes, "application/pdf")}
    r_verify = client.post("/api/provenance/verify", files=files, data={"claim_id": claim_id})
    assert r_verify.status_code == 200
    v_data = r_verify.json()

    assert v_data["status"] == "verified"
    assert "Drishti" in v_data["detail"]
    assert "issued by FinShield" not in v_data["detail"]


# ---------------------------------------------------------------------------
# 9. Synthetic Claims Backend Filtering (include_synthetic)
# ---------------------------------------------------------------------------

def test_synthetic_claims_backend_filtering():
    """
    Validates that GET /claims and GET /analytics/summary filter out synthetic
    claims when include_synthetic=false (default), and include them when include_synthetic=true.
    """
    # 1. Create real upload claim
    real_claim = Claim(
        claim_id="CLM-REAL-UPLOAD-001",
        source="upload",
        policy_id="POL-REAL-1",
        insurer_id="INS-CARE",
        claimant=Claimant(claimant_id="CLMNT-R1", name="Real User", phone="9999999999", bank_account_hash="h1"),
        provider=Provider(hospital_id="HOSP-R1", name="Real Hospital", city="Mumbai"),
        total_claimed=15000.0
    )
    db_service.save_claim(real_claim)

    # 2. Create synthetic demo claim
    demo_claim = Claim(
        claim_id="CLM-G1-DEMO-SYNTH-001",
        source="demo",
        policy_id="POL-DEMO-1",
        insurer_id="INS-CARE",
        claimant=Claimant(claimant_id="CLMNT-D1", name="Demo User", phone="8888888888", bank_account_hash="h2"),
        provider=Provider(hospital_id="HOSP-D1", name="Demo Hospital", city="Pune"),
        total_claimed=25000.0
    )
    db_service.save_claim(demo_claim)

    # Default include_synthetic=false: only real claim returned
    r_claims_default = client.get("/api/claims")
    assert r_claims_default.status_code == 200
    c_ids_default = [c["claim_id"] for c in r_claims_default.json()]
    assert "CLM-REAL-UPLOAD-001" in c_ids_default
    assert "CLM-G1-DEMO-SYNTH-001" not in c_ids_default

    # Explicit include_synthetic=true: both returned
    r_claims_all = client.get("/api/claims?include_synthetic=true")
    assert r_claims_all.status_code == 200
    c_ids_all = [c["claim_id"] for c in r_claims_all.json()]
    assert "CLM-REAL-UPLOAD-001" in c_ids_all
    assert "CLM-G1-DEMO-SYNTH-001" in c_ids_all

    # Analytics summary totals match filtered list
    r_sum_filtered = client.get("/api/analytics/summary?include_synthetic=false")
    assert r_sum_filtered.status_code == 200
    assert r_sum_filtered.json()["total_claims"] == 1
    assert r_sum_filtered.json()["total_amount_claimed"] == 15000.0

    r_sum_all = client.get("/api/analytics/summary?include_synthetic=true")
    assert r_sum_all.status_code == 200
    assert r_sum_all.json()["total_claims"] >= 2
