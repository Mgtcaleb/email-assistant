#!/bin/bash
set -Eeuo pipefail

DATA_DIR_PATH="${DATA_DIR:-/data}"
STATE_DIR_PATH="${OPENCLAW_STATE_DIR:-/data/.openclaw}"
WORKSPACE_DIR_PATH="${OPENCLAW_WORKSPACE_DIR:-/data/workspace}"

# Create all required OpenClaw subdirectories. OpenClaw uses non-recursive mkdirSync
# for temporary lockfiles, which throws ENOENT if .openclaw/tmp does not exist.
mkdir -p "$DATA_DIR_PATH" "$STATE_DIR_PATH" "$STATE_DIR_PATH/tmp" "$STATE_DIR_PATH/state" "$WORKSPACE_DIR_PATH"
chmod -R 777 "$DATA_DIR_PATH" 2>/dev/null || true

# Start Gmail polling in the background.
python3 -m monitor.main &
MONITOR_PID=$!

cleanup() {
  kill "$MONITOR_PID" 2>/dev/null || true
  wait "$MONITOR_PID" 2>/dev/null || true
}
trap cleanup EXIT TERM INT

# Ensure OPENCLAW_GATEWAY_TOKEN is available; generate fallback to prevent startup crash
if [ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]; then
  OPENCLAW_GATEWAY_TOKEN=$(node -e "console.log(crypto.randomBytes(32).toString('hex'))")
  echo "[start.sh] Notice: OPENCLAW_GATEWAY_TOKEN was not configured. Auto-generated token: ${OPENCLAW_GATEWAY_TOKEN}"
fi

# Render requires a service to listen on 0.0.0.0 and dynamically respects its PORT variable (default 10000).
GATEWAY_PORT="${PORT:-${OPENCLAW_GATEWAY_PORT:-10000}}"
node "$(npm root -g)/openclaw/openclaw.mjs" gateway \
  --allow-unconfigured \
  --bind lan \
  --port "$GATEWAY_PORT" \
  --token "$OPENCLAW_GATEWAY_TOKEN" \
  --verbose
