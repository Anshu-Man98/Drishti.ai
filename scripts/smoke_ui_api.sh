#!/usr/bin/env bash
set -euo pipefail

# scripts/smoke_ui_api.sh
# Verifies that Vite dev server proxy on port 3000 correctly forwards /api endpoints
# to backend on port 8000 without path stripping.

HOST="${1:-http://localhost:3000}"
AUTH_HEADER="Authorization: Bearer dev-token-adjuster"

echo "=== Drishti.ai UI-to-API Dev Proxy Smoke Test ==="
echo "Target Host: $HOST"

ENDPOINTS=(
  "/api/health"
  "/api/claims"
  "/api/analytics/summary"
)

ALL_PASSED=true

for ep in "${ENDPOINTS[@]}"; do
  url="${HOST}${ep}"
  status=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$url" || echo "000")
  if [ "$status" -eq 200 ]; then
    echo "  [PASS] $ep -> HTTP 200 OK"
  else
    echo "  [FAIL] $ep -> HTTP $status (Expected 200)"
    ALL_PASSED=false
  fi
done

if [ "$ALL_PASSED" = true ]; then
  echo "All UI dev proxy endpoints verified successfully."
  exit 0
else
  echo "Proxy smoke test failed."
  exit 1
fi
