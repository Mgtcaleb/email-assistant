#!/bin/bash
set -Eeuo pipefail

mkdir -p "${DATA_DIR:-/data}" "${OPENCLAW_STATE_DIR:-/data/.openclaw}" "${OPENCLAW_WORKSPACE_DIR:-/data/workspace}"

# Start Gmail polling in the background.
python3 -m monitor.main &
MONITOR_PID=$!

cleanup() {
  kill "$MONITOR_PID" 2>/dev/null || true
  wait "$MONITOR_PID" 2>/dev/null || true
}
trap cleanup EXIT TERM INT

# Render requires a service to listen on 0.0.0.0 and on its PORT.
GATEWAY_PORT="${PORT:-${OPENCLAW_GATEWAY_PORT:-8080}}"
node "$(npm root -g)/openclaw/openclaw.mjs" gateway \
  --allow-unconfigured \
  --bind lan \
  --port "$GATEWAY_PORT" \
  --token "${OPENCLAW_GATEWAY_TOKEN:?OPENCLAW_GATEWAY_TOKEN is required}"
