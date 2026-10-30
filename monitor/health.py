"""Online status helper and diagnostics for OpenClaw Amazon Monitor."""

import json, os
from datetime import datetime, timezone
from .store import connect

def get_status() -> dict:
    """Returns a dictionary containing online diagnostic metrics."""
    has_gmail = bool(os.getenv("GMAIL_REFRESH_TOKEN") and os.getenv("GMAIL_CLIENT_ID"))
    has_slack = bool(os.getenv("SLACK_WEBHOOK_URL"))
    db_ok = False
    order_count = 0
    processed_count = 0

    try:
        con = connect()
        try:
            order_count = con.execute("SELECT count(*) FROM orders").fetchone()[0]
            processed_count = con.execute("SELECT count(*) FROM processed").fetchone()[0]
            db_ok = True
        finally:
            con.close()
    except Exception as e:
        db_error = str(e)
    else:
        db_error = None

    return {
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "port": int(os.getenv("PORT", "10000")),
        "poll_seconds": int(os.getenv("POLL_SECONDS", "300")),
        "dry_run": os.getenv("DRY_RUN", "false").lower() == "true",
        "configured": {
            "gmail_oauth": has_gmail,
            "slack_webhook": has_slack,
            "database": db_ok,
        },
        "metrics": {
            "tracked_orders": order_count,
            "processed_messages": processed_count,
        },
        "database_error": db_error,
    }

if __name__ == "__main__":
    print(json.dumps(get_status(), indent=2))

