#!/bin/bash
set -Eeuo pipefail

DATA_DIR_PATH="${DATA_DIR:-/data}"
STATE_DIR_PATH="${OPENCLAW_STATE_DIR:-/data/.openclaw}"
WORKSPACE_DIR_PATH="${OPENCLAW_WORKSPACE_DIR:-/data/workspace}"

# Create all required OpenClaw subdirectories. OpenClaw uses non-recursive mkdirSync
# for temporary lockfiles, which throws ENOENT if .openclaw/tmp does not exist.
mkdir -p "$DATA_DIR_PATH" "$STATE_DIR_PATH" "$STATE_DIR_PATH/tmp" "$STATE_DIR_PATH/state" "$WORKSPACE_DIR_PATH"
chmod -R 777 "$DATA_DIR_PATH" 2>/dev/null || true

# Purge stale OpenClaw runtime lockfiles and leases left by previous containers on persistent volume.
# When a container restarts, Docker creates a new PID namespace inode. Stale leases in openclaw.sqlite
# and *.lock files trigger GatewayLockNamespaceError if checked within 90 seconds.
rm -rf "$STATE_DIR_PATH/tmp"/* /tmp/openclaw* 2>/dev/null || true
find "$STATE_DIR_PATH" -name "*.lock" -delete 2>/dev/null || true
if [ -f "$STATE_DIR_PATH/state/openclaw.sqlite" ]; then
  python3 -c "import sqlite3; con=sqlite3.connect('$STATE_DIR_PATH/state/openclaw.sqlite'); con.execute('DELETE FROM state_leases WHERE scope=\"gateway-owner\" OR key=\"global\"'); con.commit(); con.close()" 2>/dev/null || true
fi

# Configure gateway.trustedProxies so Render internal proxy router (10.x.x.x) is trusted
python3 -c "
import json, os
cfg_path = '$STATE_DIR_PATH/openclaw.json'
cfg = {}
if os.path.exists(cfg_path):
    try:
        with open(cfg_path, 'r') as f: cfg = json.load(f)
    except Exception: cfg = {}
gw = cfg.setdefault('gateway', {})
tp = gw.setdefault('trustedProxies', [])
for c in ['10.0.0.0/8', '172.16.0.0/12', '127.0.0.1']:
    if c not in tp: tp.append(c)
with open(cfg_path, 'w') as f: json.dump(cfg, f, indent=2)
" 2>/dev/null || true

# Start Gmail polling in the background.
python3 -m monitor.main &
MONITOR_PID=$!

cleanup() {
  kill "$MONITOR_PID" 2>/dev/null || true
  wait "$MONITOR_PID" 2>/dev/null || true
  rm -rf "$STATE_DIR_PATH/tmp"/* /tmp/openclaw* 2>/dev/null || true
  find "$STATE_DIR_PATH" -name "*.lock" -delete 2>/dev/null || true
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
