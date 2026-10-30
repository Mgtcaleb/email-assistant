#!/usr/bin/env python3
"""
Render 24x7 Keep-Alive & Online Status Monitor.
Pings the Render service every 14 minutes to prevent free-tier spin down
and checks the online health status.
"""

import argparse
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

DEFAULT_URL = os.getenv("RENDER_SERVICE_URL", "https://openclaw-amazon-slack.onrender.com/startupz")

def check_online_status(url: str, timeout: int = 25) -> tuple[bool, int, str, float]:
    """Sends an HTTP GET probe and returns (is_online, status_code, response_text, latency_ms)."""
    start = time.time()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OpenClaw-KeepAlive/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            latency = (time.time() - start) * 1000
            body = res.read().decode("utf-8", errors="replace")[:200]
            return (res.status == 200, res.status, body, latency)
    except urllib.error.HTTPError as e:
        latency = (time.time() - start) * 1000
        return (False, e.code, str(e), latency)
    except Exception as e:
        latency = (time.time() - start) * 1000
        return (False, 0, str(e), latency)

def main():
    parser = argparse.ArgumentParser(description="Keep Render online 24x7 and monitor status")
    parser.add_argument("--url", default=DEFAULT_URL, help="Render service health check URL")
    parser.add_argument("--interval", type=int, default=840, help="Seconds between pings (default 840 = 14m)")
    parser.add_argument("--once", action="store_true", help="Ping once and exit")
    args = parser.parse_args()

    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] Monitoring: {args.url}")

    while True:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        online, code, body, latency = check_online_status(args.url)

        if online:
            print(f"[{timestamp}] 🟢 ONLINE - HTTP {code} ({latency:.1f}ms) - {body.strip()}")
        else:
            print(f"[{timestamp}] 🔴 OFFLINE / UNREACHABLE - Code: {code} ({latency:.1f}ms) - {body.strip()}", file=sys.stderr)

        if args.once:
            sys.exit(0 if online else 1)

        time.sleep(args.interval)

if __name__ == "__main__":
    main()
