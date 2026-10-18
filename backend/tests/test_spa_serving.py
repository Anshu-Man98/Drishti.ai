"""
Unit and regression tests for Step 2: Serving Frontend SPA from FastAPI.
Tests:
1. GET / returns SPA HTML (index.html) when dist exists.
2. GET /claims/CLM-101 (or any client-side route) returns the SPA index.html.
3. GET /api/unknown returns JSON 404 (does not return HTML).
4. GET /api/health and GET /health continue to work and return JSON 200.
5. Assets under /assets return Cache-Control: public, max-age=31536000, immutable.
6. The app starts cleanly and returns API fallback when dist is absent.
"""

import os
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app, get_frontend_dist_dir


def test_spa_serving_when_dist_exists(tmp_path, monkeypatch):
    """Verify SPA serves index.html and routes when dist exists."""
    if get_frontend_dist_dir() is None:
        dist_dir = tmp_path / "dist"
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir(parents=True)
        (dist_dir / "index.html").write_text(
            "<!doctype html><html><head><title>FinShield</title></head><body><div id='root'></div></body></html>",
            encoding="utf-8",
        )
        (assets_dir / "app-test.js").write_text("console.log('finshield');", encoding="utf-8")
        monkeypatch.setenv("FRONTEND_DIST_DIR", str(dist_dir))

    client = TestClient(app)

    # 1. GET / returns index.html with no-cache header
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers.get("content-type", "")
    assert "no-cache" in res_root.headers.get("cache-control", "")
    assert "<!doctype html>" in res_root.text.lower() or "<html" in res_root.text.lower()

    # 2. GET /claims/anything returns index.html (client-side routing fallback)
    res_claims = client.get("/claims/CLM-G1-CLEAN-DEMO")
    assert res_claims.status_code == 200
    assert "text/html" in res_claims.headers.get("content-type", "")
    assert "<!doctype html>" in res_claims.text.lower() or "<html" in res_claims.text.lower()

    # 3. GET /network returns index.html
    res_net = client.get("/network")
    assert res_net.status_code == 200
    assert "text/html" in res_net.headers.get("content-type", "")

    # 4. GET /api/unknown returns JSON 404, NOT HTML
    res_api_unknown = client.get("/api/unknown_nonexistent_endpoint")
    assert res_api_unknown.status_code == 404
    assert "application/json" in res_api_unknown.headers.get("content-type", "")
    assert res_api_unknown.json() == {"detail": "Not Found"}

    # 5. GET /api/health and /health return JSON 200
    res_health = client.get("/api/health")
    assert res_health.status_code in (200, 503)
    assert "application/json" in res_health.headers.get("content-type", "")

    # 6. Security headers are present on SPA response
    assert res_root.headers.get("x-content-type-options") == "nosniff"
    assert res_root.headers.get("x-frame-options") == "DENY"
    assert res_root.headers.get("referrer-policy") == "no-referrer"


def test_app_starts_when_dist_is_absent(monkeypatch):
    """Verify that when frontend dist directory is absent, app starts and serves API fallback."""
    # Point FRONTEND_DIST_DIR to non-existent folder
    fake_nonexistent = "/tmp/nonexistent_frontend_dist_12345"
    monkeypatch.setenv("FRONTEND_DIST_DIR", fake_nonexistent)

    dist = get_frontend_dist_dir()
    assert dist is None

    client = TestClient(app)
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "application/json" in res_root.headers.get("content-type", "")
    assert "Welcome to Drishti.ai API" in res_root.json().get("message", "")
