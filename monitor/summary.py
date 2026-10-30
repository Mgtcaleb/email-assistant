"""
Daily 10:00 AM IST Amazon.in Delivery Summary.
Calculates and posts to Slack the number of Amazon.in orders expected:
- Today
- Today + 1 day (Tomorrow)
- Today + 2 days (Day after tomorrow)
"""

import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta, date

from .store import connect, get_active_orders, has_sent_summary_today, record_summary_sent
from .parser import parse_eta_date
from .slack import send_daily_summary_slack

log = logging.getLogger("amazon-summary")
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now() -> datetime:
    """Returns the current datetime in Indian Standard Time (UTC+05:30)."""
    return datetime.now(IST)

def build_amazon_in_summary(con=None, ref_date: date = None) -> dict:
    """
    Calculates expected Amazon.in deliveries for today, today+1, and today+2 in IST.
    """
    close_con = False
    if con is None:
        con = connect()
        close_con = True

    try:
        ist_now = get_ist_now()
        today = ref_date or ist_now.date()
        day1 = today + timedelta(days=1)
        day2 = today + timedelta(days=2)

        today_orders = []
        day1_orders = []
        day2_orders = []
        other_orders = []

        active_orders = get_active_orders(con, marketplace="amazon.in")

        for order in active_orders:
            # Resolve eta_date
            eta_str = order.get("eta")
            eta_date_str = order.get("eta_date")
            eta_d = None

            if eta_date_str:
                try:
                    eta_d = date.fromisoformat(eta_date_str)
                except ValueError:
                    eta_d = None

            if not eta_d and eta_str:
                eta_d = parse_eta_date(eta_str, ref_date=today)

            if eta_d == today:
                today_orders.append(order)
            elif eta_d == day1:
                day1_orders.append(order)
            elif eta_d == day2:
                day2_orders.append(order)
            else:
                other_orders.append(order)

        return {
            "date_heading": ist_now.strftime("%A, %d %b %Y"),
            "today_date": today.isoformat(),
            "today_str": today.strftime("%d %b"),
            "day1_str": day1.strftime("%d %b, +1 Day"),
            "day2_str": day2.strftime("%d %b, +2 Days"),
            "today_orders": today_orders,
            "day1_orders": day1_orders,
            "day2_orders": day2_orders,
            "other_orders_count": len(other_orders),
            "total_expected": len(today_orders) + len(day1_orders) + len(day2_orders),
        }
    finally:
        if close_con:
            con.close()

def send_daily_summary(force: bool = False, dry_run: bool = False, con = None) -> bool:
    """
    Sends the 10:00 AM IST delivery summary to Slack.
    Guarantees idempotency: sends at most once per calendar day unless force=True.
    """
    close_con = False
    if con is None:
        con = connect()
        close_con = True

    try:
        ist_now = get_ist_now()
        today_str = ist_now.date().isoformat()

        if not force and has_sent_summary_today(con, today_str):
            log.info("Daily summary for %s already sent today; skipping", today_str)
            return False

        summary = build_amazon_in_summary(con=con, ref_date=ist_now.date())
        send_daily_summary_slack(summary, dry_run=dry_run)

        if not dry_run:
            details_json = json.dumps({
                "today": len(summary["today_orders"]),
                "day1": len(summary["day1_orders"]),
                "day2": len(summary["day2_orders"]),
            })
            record_summary_sent(
                con,
                today_str,
                len(summary["today_orders"]),
                len(summary["day1_orders"]),
                len(summary["day2_orders"]),
                details=details_json,
            )
            con.commit()
            log.info("Recorded daily summary for %s in database", today_str)

        return True
    finally:
        if close_con:
            con.close()

def check_10am_ist_trigger(con, dry_run: bool = False) -> bool:
    """
    Checks if current IST time is 10:00 AM or later and sends summary if not yet sent today.
    """
    ist_now = get_ist_now()
    # Trigger at 10:00 AM IST or later
    if ist_now.hour >= 10:
        today_str = ist_now.date().isoformat()
        if not has_sent_summary_today(con, today_str):
            log.info("10 AM IST reached (%s IST); generating daily Amazon.in delivery summary", ist_now.strftime("%H:%M:%S"))
            return send_daily_summary(force=False, dry_run=dry_run, con=con)
    return False

def main():
    parser = argparse.ArgumentParser(description="Amazon.in 10 AM IST Delivery Summary")
    parser.add_argument("--force", action="store_true", help="Send even if already sent today")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without posting to Slack")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    dry_run = args.dry_run or os.getenv("DRY_RUN", "false").lower() == "true"
    sent = send_daily_summary(force=args.force, dry_run=dry_run)
    if sent:
        print("Daily summary processed successfully.")
    else:
        print("Daily summary was already sent today (use --force to resend).")

if __name__ == "__main__":
    main()
