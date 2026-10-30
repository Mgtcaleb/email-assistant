#!/bin/bash
set -Eeuo pipefail

mkdir -p "${DATA_DIR:-/data}" "${OPENCLAW_STATE_DIR:-/data/.openclaw}" "${OPENCLAW_WORKSPACE_DIR:-/data/workspace}"

# Start the Gmail monitor in the background. It has its own retry loop.
python3 -m monitor.main &
MONITOR_PID=$!

# Run the official OpenClaw Gateway as the container's foreground process.
cleanup() {
  kill "$MONITOR_PID" 2>/dev/null || true
  wait "$MONITOR_PID" 2>/dev/null || true
}
trap cleanup EXIT TERM INT

node "$(npm root -g)/openclaw/openclaw.mjs" gateway --allow-unconfigured --bind auto --port "${OPENCLAW_GATEWAY_PORT:-8080}" --token "${OPENCLAW_GATEWAY_TOKEN:?OPENCLAW_GATEWAY_TOKEN is required}"
