#!/usr/bin/env bash
# scripts/verify_live.sh - Runs full post-deploy verification against live Cloud Run URL
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TARGET_URL="${1:-https://drishti-app-6lmavyq52q-el.a.run.app}"

echo "================================================================================"
echo "Drishti AI - Live Verification Runner"
echo "Target: $TARGET_URL"
echo "================================================================================"

if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON_EXEC="$REPO_ROOT/.venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

"$PYTHON_EXEC" "$REPO_ROOT/scripts/verify_live_post_deploy.py" "$TARGET_URL"
