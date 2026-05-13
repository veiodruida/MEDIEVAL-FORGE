#!/usr/bin/env bash
# Phase 05 Plan 12 — France 1066 UAT live runner.
# Closes VERIFICATION Gap 2: live browser session against the live stack.
#
# Usage:   bash scripts/run_france_uat.sh
# Expects: ./backend/pyproject.toml + ./frontend/package.json present (repo root).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/5] Killing any lingering dev servers..."
# Best-effort: ignore failures (no servers running is fine).
pkill -f "medieval-forge" 2>/dev/null || true
pkill -f "uvicorn"        2>/dev/null || true
pkill -f "vite"           2>/dev/null || true
sleep 1

echo "[2/5] Frontend build (catches type errors before Playwright)..."
(cd frontend && npm run build)

echo "[3/5] Starting backend (medieval-forge start) in background..."
medieval-forge start > /tmp/medieval_forge_backend.log 2>&1 &
BACKEND_PID=$!
echo "    backend PID=$BACKEND_PID  log=/tmp/medieval_forge_backend.log"

echo "[4/5] Starting frontend dev server in background..."
(cd frontend && npm run dev > /tmp/medieval_forge_frontend.log 2>&1) &
FRONTEND_PID=$!
echo "    frontend PID=$FRONTEND_PID log=/tmp/medieval_forge_frontend.log"

# Wait for both servers to respond (max 30 s each).
echo "    Waiting for backend (http://localhost:8000/api/v3/regions)..."
for i in {1..30}; do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v3/regions | grep -q "200"; then
    echo "    backend ready"
    break
  fi
  sleep 1
done

echo "    Waiting for frontend (http://localhost:5173)..."
for i in {1..30}; do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 | grep -qE "200|304"; then
    echo "    frontend ready"
    break
  fi
  sleep 1
done

cleanup() {
  echo "[cleanup] Shutting down servers..."
  kill "$BACKEND_PID"  2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "[5/5] Running Playwright spec: france_1066_create_project"
cd frontend
npx playwright test france_1066_create_project --reporter=line
EXITCODE=$?
echo ""
echo "===================="
echo "Playwright exit code: $EXITCODE"
echo "===================="
exit $EXITCODE
