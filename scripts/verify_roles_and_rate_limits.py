#!/usr/bin/env python3
"""
Verify live Cloud Run role permissions and chat rate limits.
Usage:
    python scripts/verify_roles_and_rate_limits.py [TARGET_URL]
"""
import sys
import json
import urllib.request
import urllib.error

TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else "https://drishti-app-6lmavyq52q-el.a.run.app"

def make_req(endpoint: str, method: str = "GET", token: str = "dev-token", body: dict = None):
    url = f"{TARGET_URL.rstrip('/')}{endpoint}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)

def main():
    print("=" * 80)
    print(f"VERIFY ROLES & RATE LIMITS ON LIVE CLOUD RUN: {TARGET_URL}")
    print("=" * 80)

    # Health check
    status, body = make_req("/api/health")
    print(f"[*] /api/health -> Status {status}")
    assert status == 200, f"Health check failed with status {status}"

    # 1. USER ROLE TESTS (token: user-token)
    print("\n--- Testing 'user' Role (token: user-token) ---")
    
    # 1a. Upload claim forbidden (403)
    status, body = make_req("/api/claims", method="POST", token="user-token", body={
        "claim_id": "TEST-USER-FAIL",
        "policy_id": "POL-001",
        "claimant_name": "Test User",
        "hospital_name": "Test Hospital",
        "total_claimed": 10000,
        "admission_date": "2026-03-01",
        "discharge_date": "2026-03-03"
    })
    print(f"  [1a] POST /api/claims (Upload) -> Status {status} (Expected 403)")
    assert status == 403, f"Expected 403 for user role on create_claim, got {status}: {body}"
    print("       ✓ Correctly blocked with 403 Forbidden")

    # 1b. Analyze claim forbidden (403)
    status, body = make_req("/api/claims/CLM-G1-CLEAN-DEMO/analyze", method="POST", token="user-token")
    print(f"  [1b] POST /api/claims/CLM-G1-CLEAN-DEMO/analyze -> Status {status} (Expected 403)")
    assert status == 403, f"Expected 403 for user role on analyze, got {status}: {body}"
    print("       ✓ Correctly blocked with 403 Forbidden")

    # 1c. Chat allowed (200)
    status, body = make_req("/api/claims/CLM-G1-CLEAN-DEMO/chat", method="POST", token="user-token", body={"message": "What is the status?"})
    print(f"  [1c] POST /api/claims/CLM-G1-CLEAN-DEMO/chat -> Status {status} (Expected 200)")
    assert status == 200, f"Expected 200 for user role on chat, got {status}: {body}"
    print("       ✓ User can chat successfully")

    # 1d. Rate limit enforcement on user role (10 req / min)
    print("  [1d] Testing user role chat rate limit (10 requests/min max)...")
    rate_limited = False
    for i in range(1, 26):
        status, body = make_req("/api/claims/CLM-G1-CLEAN-DEMO/chat", method="POST", token="user-rate-token", body={"message": f"Ping {i}"})
        if status == 429:
            rate_limited = True
            print(f"       ✓ Hit 429 Rate Limit on request #{i}: {body.strip()}")
            break
    assert rate_limited, "Expected 429 Too Many Requests for user role exceeding 10 req/min"

    # 2. OFFICER ROLE TESTS (token: officer-token)
    print("\n--- Testing 'officer' Role (token: officer-token) ---")
    status, body = make_req("/api/claims/CLM-G1-CLEAN-DEMO/chat", method="POST", token="officer-token", body={"message": "Officer query test"})
    print(f"  [2a] POST /api/claims/CLM-G1-CLEAN-DEMO/chat -> Status {status} (Expected 200)")
    assert status == 200, f"Expected 200 for officer role on chat, got {status}: {body}"
    print("       ✓ Officer can chat successfully")

    status, body = make_req("/api/claims/CLM-G1-CLEAN-DEMO/analyze", method="POST", token="officer-token")
    print(f"  [2b] POST /api/claims/CLM-G1-CLEAN-DEMO/analyze -> Status {status} (Expected 200, Not 403)")
    assert status == 200, f"Expected 200 for officer role on analyze, got {status}: {body}"
    print("       ✓ Officer is authorized to analyze claims")

    # 3. ADMIN ROLE TESTS (token: admin-token)
    print("\n--- Testing 'admin' Role (token: admin-token) ---")
    status, body = make_req("/api/claims/CLM-G1-CLEAN-DEMO/chat", method="POST", token="admin-token", body={"message": "Admin query test"})
    print(f"  [3a] POST /api/claims/CLM-G1-CLEAN-DEMO/chat -> Status {status} (Expected 200)")
    assert status == 200, f"Expected 200 for admin role on chat, got {status}: {body}"
    print("       ✓ Admin can chat successfully")

    status, body = make_req("/api/claims/CLM-G1-CLEAN-DEMO/analyze", method="POST", token="admin-token")
    print(f"  [3b] POST /api/claims/CLM-G1-CLEAN-DEMO/analyze -> Status {status} (Expected 200, Not 403)")
    assert status == 200, f"Expected 200 for admin role on analyze, got {status}: {body}"
    print("       ✓ Admin is authorized to analyze claims")

    print("\n" + "=" * 80)
    print("✓ ALL ROLE & RATE LIMIT CHECKS PASSED ON LIVE CLOUD RUN!")
    print("=" * 80)

if __name__ == "__main__":
    main()
