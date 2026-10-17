import os
import pytest
from pathlib import Path
from google.cloud import firestore, storage, bigquery


def test_cloud_client_boundary_isolation_raises_runtime_error():
    """Verify that any attempt to construct real Google Cloud SDK clients raises RuntimeError in test suite."""
    with pytest.raises(RuntimeError, match="CRITICAL TEST ISOLATION VIOLATION: Attempted to construct real google.cloud.firestore.Client"):
        firestore.Client()

    with pytest.raises(RuntimeError, match="CRITICAL TEST ISOLATION VIOLATION: Attempted to construct real google.cloud.storage.Client"):
        storage.Client()

    with pytest.raises(RuntimeError, match="CRITICAL TEST ISOLATION VIOLATION: Attempted to construct real google.cloud.bigquery.Client"):
        bigquery.Client()


def test_ci_workflow_enforces_coverage_threshold():
    """Verify that CI workflow file specifies the required 80% coverage threshold and scope."""
    ci_path = Path(__file__).resolve().parent.parent.parent / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists(), "CI workflow file .github/workflows/ci.yml must exist"
    
    ci_content = ci_path.read_text(encoding="utf-8")
    assert "--cov-fail-under=80" in ci_content, "CI must enforce --cov-fail-under=80"
    assert "--cov=backend/app" in ci_content, "CI must include backend/app coverage"
    assert "--cov=backend/agents" in ci_content, "CI must include backend/agents coverage"
    assert "--cov=backend/tools" in ci_content, "CI must include backend/tools coverage"
    assert "--cov=backend/services" in ci_content, "CI must include backend/services coverage"


def test_pytest_cov_dependency_pinned():
    """Verify that pytest-cov is declared in requirements.txt and locked in requirements.lock."""
    req_txt = (Path(__file__).resolve().parent.parent.parent / "backend" / "requirements.txt").read_text(encoding="utf-8")
    req_lock = (Path(__file__).resolve().parent.parent.parent / "backend" / "requirements.lock").read_text(encoding="utf-8")

    assert "pytest-cov" in req_txt, "pytest-cov must be in backend/requirements.txt"
    assert "pytest-cov==" in req_lock, "pytest-cov must be pinned in backend/requirements.lock"
    assert "coverage==" in req_lock, "coverage must be pinned in backend/requirements.lock"
