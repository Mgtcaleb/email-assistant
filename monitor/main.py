import os, time, logging, argparse
from datetime import datetime, timedelta, timezone
from .gmail_client import fetch_messages
from .parser import parse_message
from .store import connect, is_processed, mark_processed, get_order, save_order
from .slack import send_alert, send_online_alert, send_heartbeat_alert
from .summary import check_10am_ist_trigger, send_daily_summary

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("amazon-monitor")

def gmail_query():
    days = int(os.getenv("INITIAL_LOOKBACK_DAYS", "3"))
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
    return f'after:{after} {{from:(amazon.in) from:(amazon.com) from:(marketplace.amazon)}}'

def poll_once():
    con = connect()
    try:
        messages = fetch_messages(gmail_query(), max_results=20)
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
    parser = argparse.ArgumentParser(description="OpenClaw Amazon Monitor")
    parser.add_argument("--once", action="store_true", help="Run Gmail polling once and exit")
    parser.add_argument("--summary", action="store_true", help="Send 10 AM IST Amazon.in delivery summary now")
    parser.add_argument("--summary-force", action="store_true", help="Force send summary even if sent today")
    args = parser.parse_args()
    
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    if not os.getenv("GMAIL_REFRESH_TOKEN") or not os.getenv("SLACK_WEBHOOK_URL"):
        log.warning("Gmail or Slack credentials missing; monitor will retry after configuration")

    if args.summary:
        sent = send_daily_summary(force=args.summary_force, dry_run=dry_run)
        if sent:
            print("Amazon.in 10 AM IST delivery summary sent successfully.")
        else:
            print("Daily summary was already sent today (use --summary-force to resend).")
        return

    # Send online status alert to Slack when starting 24x7 monitoring
    send_online = os.getenv("SEND_ONLINE_ALERT", "true").lower() == "true"
    if send_online and not args.once:
        try:
            send_online_alert({
                "port": os.getenv("PORT", "10000"),
                "poll_interval": os.getenv("POLL_SECONDS", "300"),
                "lookback_days": os.getenv("INITIAL_LOOKBACK_DAYS", "3"),
            }, dry_run=dry_run)
        except Exception:
            log.exception("Failed to send startup online alert")

    if args.once:
        poll_once()
        return

    interval = max(60, int(os.getenv("POLL_SECONDS", "300")))
    start_time = datetime.now(timezone.utc)
    heartbeat_hours = int(os.getenv("HEARTBEAT_HOURS", "0"))
    last_heartbeat = start_time

    while True:
        try:
            poll_once()
        except Exception:
            log.exception("Gmail polling failed; will retry")

        # Check and send 10:00 AM IST daily delivery summary
        try:
            con = connect()
            try:
                check_10am_ist_trigger(con, dry_run=dry_run)
            finally:
                con.close()
        except Exception:
            log.exception("Error checking 10 AM IST summary trigger")

        if heartbeat_hours > 0:
            now = datetime.now(timezone.utc)
            if (now - last_heartbeat).total_seconds() >= heartbeat_hours * 3600:
                uptime_delta = now - start_time
                hours, remainder = divmod(int(uptime_delta.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                con = connect()
                try:
                    orders_count = con.execute("SELECT count(*) FROM orders").fetchone()[0]
                except Exception:
                    orders_count = 0
                finally:
                    con.close()
                send_heartbeat_alert({
                    "uptime": f"{hours}h {minutes}m",
                    "orders_count": orders_count,
                    "last_poll": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
                }, dry_run=dry_run)
                last_heartbeat = now

        time.sleep(interval)

if __name__ == "__main__":
    main()
