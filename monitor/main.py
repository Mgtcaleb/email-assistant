import os, time, logging, argparse
from datetime import datetime, timedelta, timezone
from .gmail_client import fetch_messages
from .parser import parse_message
from .store import connect, is_processed, mark_processed, get_order, save_order
from .slack import send_alert

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("amazon-monitor")

def gmail_query():
    days = int(os.getenv("INITIAL_LOOKBACK_DAYS", "30"))
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
    return f'after:{after} {{from:(amazon.in) from:(amazon.com) from:(marketplace.amazon)}}'

def poll_once():
    con = connect()
    try:
        messages = fetch_messages(gmail_query(), max_results=100)
        log.info("Fetched %d candidate Gmail messages", len(messages))
        dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        for msg in reversed(messages):
            if is_processed(con, msg["id"]):
                continue
            orders = parse_message(msg["subject"], msg["body"], msg["from"], msg["date"])
            for order in orders:
                previous = get_order(con, order["order_id"])
                changed = previous is None or previous["status"] != order["status"] or (
                    order.get("eta") and previous.get("eta") != order.get("eta")
                )
                if changed:
                    # Do not notify for unclassified content unless it is a newly seen order.
                    if order["status"] != "UNKNOWN" or previous is None:
                        send_alert(order, previous, dry_run=dry_run)
                    save_order(con, order, msg["id"])
            mark_processed(con, msg["id"])
        con.commit()
    finally:
        con.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not os.getenv("GMAIL_REFRESH_TOKEN") or not os.getenv("SLACK_WEBHOOK_URL"):
        log.warning("Gmail or Slack credentials missing; monitor will retry after configuration")
    if args.once:
        poll_once()
        return
    interval = max(60, int(os.getenv("POLL_SECONDS", "300")))
    while True:
        try:
            poll_once()
        except Exception:
            log.exception("Gmail polling failed; will retry")
        time.sleep(interval)

if __name__ == "__main__":
    main()
