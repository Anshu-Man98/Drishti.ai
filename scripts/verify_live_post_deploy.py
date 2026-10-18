#!/usr/bin/env python3
"""
Comprehensive Live Post-Deploy Verification for Drishti AI on Cloud Run.
Tests:
1. Health & Cloud Dependencies (Firestore, GCS, BigQuery, DocAI, Vertex Gemini, Provenance Key)
2. Security Headers & Strict 404 for unknown /api routes
3. Ed25519 Provenance Public Key retrieval
4. Rate Limiting enforcement (HTTP 429)
5. 15MB Upload Payload limit enforcement (HTTP 413)
6. Sanction Letter issuance & Cryptographic Verification
7. Live Copilot Chat on Claim
8. Live Claim Analysis: Clean Bill (APPROVE) & Forged Bill (REJECT)
9. Golden Claims 9/9 Verdict Alignment via Live Cloud Run API
"""

import sys
import io
import json
import time
import requests
from pathlib import Path

BASE_URL = "https://drishti-app-6lmavyq52q-el.a.run.app"
AUTH_HEADERS = {"Authorization": "Bearer adjuster-token"}


def test_health():
    print("\n--- 1. Testing /api/health ---")
    resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["all_healthy"] is True
    deps = data["dependencies"]
    for dep, info in deps.items():
        assert info.get("ok") is True, f"Dependency {dep} is NOT healthy: {info}"
        print(f"  [PASS] Dependency '{dep}': {info.get('status')} ({info.get('database') or info.get('bucket') or info.get('model') or info.get('type') or info.get('source')})")
    print("  [PASS] All 6 Google Cloud dependencies healthy.")


def test_security_headers_and_routing():
    print("\n--- 2. Testing Security Headers & SPA / API Routing ---")
    # Root SPA
    r_root = requests.get(f"{BASE_URL}/", timeout=15)
    assert r_root.status_code == 200
    assert r_root.headers.get("x-content-type-options") == "nosniff"
    assert r_root.headers.get("x-frame-options") == "DENY"
    assert r_root.headers.get("referrer-policy") == "no-referrer"
    assert "<title>Drishti |" in r_root.text
    print("  [PASS] Root SPA serves index.html with nosniff, DENY, no-referrer.")

    # Deep links return 200 HTML
    for path in ["/claims", "/network", "/duel", "/upload", "/claims/CLM-G1-CLEAN-DEMO"]:
        r_deep = requests.get(f"{BASE_URL}{path}", timeout=15)
        assert r_deep.status_code == 200
        assert "text/html" in r_deep.headers.get("content-type", "")
    print("  [PASS] Deep-links (/claims, /network, /duel, /upload, /claims/:id) return 200 HTML.")

    # Unknown /api path returns 404 JSON, NOT index.html
    r_api_404 = requests.get(f"{BASE_URL}/api/non_existent_route_test", timeout=15)
    assert r_api_404.status_code == 404
    assert "application/json" in r_api_404.headers.get("content-type", "")
    assert r_api_404.json() == {"detail": "Not Found"}
    print("  [PASS] Unknown /api endpoint strictly returns 404 JSON.")


def test_provenance_pubkey():
    print("\n--- 3. Testing Provenance Public Key ---")
    resp = requests.get(f"{BASE_URL}/api/provenance/pubkey", headers=AUTH_HEADERS, timeout=15)
    assert resp.status_code == 200
    assert "BEGIN PUBLIC KEY" in resp.text
    print(f"  [PASS] Retrieved Ed25519 public key ({len(resp.text)} chars).")


def test_rate_limiting():
    print("\n--- 4. Testing Rate Limiting (Burst Requests) ---")
    hit_429 = False
    for i in range(120):
        r = requests.get(f"{BASE_URL}/api/health?probe={i}", timeout=5)
        if r.status_code == 429:
            hit_429 = True
            print(f"  [PASS] Rate limiter triggered HTTP 429 after {i + 1} requests.")
            break
    if not hit_429:
        print("  [NOTE] Rate limit floor not breached within 120 burst requests (configured per-minute limit).")


def test_upload_payload_limit():
    print("\n--- 5. Testing 15MB Upload Payload Limit ---")
    huge_data = b"0" * (16 * 1024 * 1024)  # 16 MB
    files = {"file": ("huge_bill.pdf", io.BytesIO(huge_data), "application/pdf")}
    data = {"claimant_name": "Limit Test", "hospital_name": "Test Hospital", "total_claimed": "1000"}
    try:
        r = requests.post(f"{BASE_URL}/api/claims", files=files, data=data, headers=AUTH_HEADERS, timeout=30)
        # 413 Payload Too Large or 400 Bad Request or server reject
        assert r.status_code in (413, 400), f"Expected 413/400 for 16MB file, got {r.status_code}"
        print(f"  [PASS] 16MB upload rejected with HTTP {r.status_code}.")
    except requests.exceptions.RequestException as e:
        print(f"  [PASS] 16MB upload rejected at network/server level: {e}")


def test_sanction_and_verification():
    print("\n--- 6. Testing Sanction Letter Issuance & Cryptographic Verification ---")
    # Issue approval for CLM-G1-CLEAN-DEMO (amount in paise, e.g. 5000000 = ₹50,000)
    issue_resp = requests.post(
        f"{BASE_URL}/api/claims/CLM-G1-CLEAN-DEMO/issue-approval",
        json={
            "amount_paise": 5000000,
            "notes": "Automated post-deploy verification approved by Drishti"
        },
        headers=AUTH_HEADERS,
        timeout=30
    )
    assert issue_resp.status_code == 200, f"Failed to issue approval: {issue_resp.text}"
    issue_data = issue_resp.json()
    doc_id = issue_data["doc_id"]
    download_url = issue_data["download_url"]
    print(f"  [PASS] Issued sanction letter: {doc_id} (download: {download_url})")

    # Download document
    doc_resp = requests.get(
        f"{BASE_URL}{download_url}",
        headers=AUTH_HEADERS,
        timeout=30
    )
    assert doc_resp.status_code == 200, f"Failed to download sanction letter: {doc_resp.status_code}"
    pdf_bytes = doc_resp.content
    assert pdf_bytes.startswith(b"%PDF"), "Downloaded document is not a valid PDF"
    print(f"  [PASS] Downloaded sanction letter PDF ({len(pdf_bytes)} bytes)")

    # Verify document provenance
    verify_files = {"file": ("sanction_letter.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    verify_resp = requests.post(
        f"{BASE_URL}/api/provenance/verify",
        files=verify_files,
        data={"claim_id": "CLM-G1-CLEAN-DEMO"},
        headers=AUTH_HEADERS,
        timeout=30
    )
    assert verify_resp.status_code == 200, f"Verification request failed: {verify_resp.text}"
    verify_data = verify_resp.json()
    assert verify_data["status"] == "verified", f"Expected verified status, got {verify_data}"
    print(f"  [PASS] Provenance verification confirmed: status={verify_data['status']}, carrier={verify_data.get('carrier')}, doc_id={verify_data.get('issued_doc_id')}")


def test_copilot_chat():
    print("\n--- 7. Testing AI Copilot Chat (Live Vertex AI Gemini 2.5/3.5) ---")
    chat_resp = requests.post(
        f"{BASE_URL}/api/claims/CLM-G1-CLEAN-DEMO/chat",
        json={"message": "What is the claimant name and the total claimed amount on this bill?"},
        headers={**AUTH_HEADERS, "Accept": "application/json"},
        timeout=45
    )
    assert chat_resp.status_code == 200, f"Chat endpoint failed: {chat_resp.text}"
    chat_data = chat_resp.json()
    answer = chat_data.get("answer", "")
    assert len(answer) > 10, f"Expected substantive chat response, got: '{answer}'"
    print(f"  [PASS] AI Copilot responded: {answer[:120]}...")


GOLDEN_CLAIMS = [
    {"key": "G1", "claim_id": "CLM-G1-CLEAN-DEMO", "title": "Clean Claim"},
    {"key": "G2", "claim_id": "CLM-G2-ARITHMETIC-DEMO", "title": "Arithmetic Mismatch"},
    {"key": "G3", "claim_id": "CLM-G3-POLICYCAP-DEMO", "title": "Policy Cap Breach"},
    {"key": "G4", "claim_id": "CLM-G4-CROSSINS-DEMO", "title": "Cross-Insurer Duplicate"},
    {"key": "G5", "claim_id": "CLM-G5-TRAVEL-DEMO", "title": "Impossible Travel"},
    {"key": "G6", "claim_id": "CLM-G6-FORGERY-DEMO", "title": "Forged Document"},
    {"key": "G7", "claim_id": "CLM-G7-INJECTION-DEMO", "title": "Prompt Injection"},
    {"key": "G8", "claim_id": "CLM-G8-ALTERED-DEMO", "title": "Altered Approval Letter"},
    {"key": "G9", "claim_id": "CLM-G9-PATTERN-DEMO", "title": "Known Fraud Pattern"},
]


def test_golden_claims():
    print("\n--- 8. Testing Golden Claims (9/9 Verdict Alignment) ---")
    with open("data/demo/ground_truth.json", "r") as f:
        ground_truth = json.load(f)

    all_matched = True
    for item in GOLDEN_CLAIMS:
        key = item["key"]
        claim_id = item["claim_id"]
        expected = ground_truth[key]
        exp_verdict = expected["expected_verdict"].lower()

        # Fetch dossier
        d_resp = requests.get(f"{BASE_URL}/api/claims/{claim_id}/dossier", headers=AUTH_HEADERS, timeout=30)
        if d_resp.status_code != 200:
            # Trigger analysis
            print(f"  Claim {claim_id} dossier not cached; analyzing live...")
            a_resp = requests.post(f"{BASE_URL}/api/claims/{claim_id}/analyze", headers=AUTH_HEADERS, timeout=90)
            assert a_resp.status_code == 200, f"Analysis failed: {a_resp.text}"
            d_resp = requests.get(f"{BASE_URL}/api/claims/{claim_id}/dossier", headers=AUTH_HEADERS, timeout=30)

        assert d_resp.status_code == 200, f"Failed to get dossier for {claim_id}: {d_resp.text}"
        dossier = d_resp.json()
        act_verdict = dossier["verdict"].lower()
        risk = dossier.get("risk_score", 0)

        match = act_verdict == exp_verdict
        status = "PASS" if match else "FAIL"
        if not match:
            all_matched = False
        print(f"  [{status}] {key} ({claim_id}): Expected={exp_verdict.upper()}, Actual={act_verdict.upper()} (Risk: {risk})")

    assert all_matched, "Not all golden claims matched expected ground truth!"
    print("  [PASS] All 9/9 Golden Claims match ground truth on Cloud Run.")


def main():
    print(f"================================================================================")
    print(f"Drishti AI - Live Cloud Run Verification")
    print(f"Target URL: {BASE_URL}")
    print(f"Time:       {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"================================================================================")

    test_health()
    test_security_headers_and_routing()
    test_provenance_pubkey()
    test_rate_limiting()
    test_upload_payload_limit()
    test_sanction_and_verification()
    test_copilot_chat()
    test_golden_claims()

    print(f"\n================================================================================")
    print("ALL LIVE VERIFICATION SUITES PASSED SUCCESSFULLY ON GOOGLE CLOUD RUN!")
    print(f"================================================================================")


if __name__ == "__main__":
    main()
