import os, requests

def send_alert(order, previous=None, dry_run=False):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError("SLACK_WEBHOOK_URL is not configured")
    status = order["status"].replace("_", " ").title()
    title = "Amazon order update"
    if previous is None:
        title = "New Amazon order detected"
    elif previous.get("status") != order.get("status"):
        title = f"Amazon order {status}"
    elif previous.get("eta") != order.get("eta"):
        title = "Amazon delivery ETA changed"
    lines = [
        f"*{title}*",
        f"*Order ID:* `{order['order_id']}`",
        f"*Marketplace:* {order['marketplace']}",
        f"*Status:* {status}",
        f"*Expected delivery:* {order.get('eta') or 'Not found in email'}",
    ]
    if previous and previous.get("status") != order.get("status"):
        lines.append(f"*Previous status:* {previous.get('status','UNKNOWN').replace('_',' ').title()}")
    payload = {"text": "\n".join(lines)}
    if dry_run:
        print("[DRY RUN] Slack alert: " + payload["text"].replace("\n", " | "), flush=True)
        return
    response = requests.post(webhook, json=payload, timeout=20)
    response.raise_for_status()
    if response.text.strip().lower() != "ok":
        raise RuntimeError(f"Slack webhook returned unexpected response: {response.text[:200]}")
    print(f"Slack alert sent for order {order['order_id']}", flush=True)

def send_online_alert(details=None, dry_run=False):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        print("[WARNING] SLACK_WEBHOOK_URL is not configured; cannot send online alert", flush=True)
        return
    details = details or {}
    lines = [
        "🟢 *OpenClaw Amazon Monitor is ONLINE*",
        "*Status:* Active & Monitoring Gmail",
        f"*Port:* `{details.get('port', os.getenv('PORT', '10000'))}`",
        f"*Poll Interval:* {details.get('poll_interval', os.getenv('POLL_SECONDS', '300'))}s",
        f"*Lookback Days:* {details.get('lookback_days', os.getenv('INITIAL_LOOKBACK_DAYS', '3'))}",
        f"*Marketplaces:* {os.getenv('AMAZON_MARKETS', 'amazon.in,amazon.com')}",
    ]
    if dry_run or os.getenv("DRY_RUN", "false").lower() == "true":
        lines.append("_Mode: DRY RUN (alerts will be logged, not posted)_")
    payload = {"text": "\n".join(lines)}
    if dry_run:
        print("[DRY RUN] Slack online alert: " + payload["text"].replace("\n", " | "), flush=True)
        return
    try:
        response = requests.post(webhook, json=payload, timeout=15)
        response.raise_for_status()
        print("Slack online status alert sent successfully", flush=True)
    except Exception as e:
        print(f"[WARNING] Failed to send Slack online alert: {e}", flush=True)

def send_heartbeat_alert(stats=None, dry_run=False):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    stats = stats or {}
    lines = [
        "💓 *OpenClaw Monitor Heartbeat*",
        "*Status:* Healthy & Running 24x7",
        f"*Uptime:* {stats.get('uptime', 'N/A')}",
        f"*Orders Tracked:* {stats.get('orders_count', 0)}",
        f"*Last Poll:* {stats.get('last_poll', 'Just now')}",
    ]
    payload = {"text": "\n".join(lines)}
    if dry_run:
        print("[DRY RUN] Slack heartbeat: " + payload["text"].replace("\n", " | "), flush=True)
        return
    try:
        response = requests.post(webhook, json=payload, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"[WARNING] Failed to send heartbeat alert: {e}", flush=True)

def send_daily_summary_slack(summary_data: dict, dry_run=False):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        print("[WARNING] SLACK_WEBHOOK_URL is not configured; cannot send daily summary", flush=True)
        return

    today_str = summary_data.get("today_str", "Today")
    day1_str = summary_data.get("day1_str", "Tomorrow (+1 Day)")
    day2_str = summary_data.get("day2_str", "Day After Tomorrow (+2 Days)")
    date_heading = summary_data.get("date_heading", "")

    today_orders = summary_data.get("today_orders", [])
    day1_orders = summary_data.get("day1_orders", [])
    day2_orders = summary_data.get("day2_orders", [])

    total = len(today_orders) + len(day1_orders) + len(day2_orders)

    lines = [
        "📦 *Amazon.in Delivery Summary (10:00 AM IST)*",
        f"📅 _{date_heading}_",
        "",
        f"*Today ({today_str}):* {len(today_orders)} order{'s' if len(today_orders) != 1 else ''} expected",
    ]
    if today_orders:
        for o in today_orders:
            lines.append(f"  • `{o['order_id']}` | *Status:* {o['status'].replace('_', ' ').title()} | *ETA:* {o.get('eta') or 'Today'}")
    else:
        lines.append("  • _No orders scheduled_")

    lines.append("")
    lines.append(f"*Tomorrow ({day1_str}):* {len(day1_orders)} order{'s' if len(day1_orders) != 1 else ''} expected")
    if day1_orders:
        for o in day1_orders:
            lines.append(f"  • `{o['order_id']}` | *Status:* {o['status'].replace('_', ' ').title()} | *ETA:* {o.get('eta') or 'Tomorrow'}")
    else:
        lines.append("  • _No orders scheduled_")

    lines.append("")
    lines.append(f"*Day After Tomorrow ({day2_str}):* {len(day2_orders)} order{'s' if len(day2_orders) != 1 else ''} expected")
    if day2_orders:
        for o in day2_orders:
            lines.append(f"  • `{o['order_id']}` | *Status:* {o['status'].replace('_', ' ').title()} | *ETA:* {o.get('eta') or 'In 2 days'}")
    else:
        lines.append("  • _No orders scheduled_")

    lines.append("")
    lines.append(f"_Total Amazon.in orders expected over next 3 days: {total}_")

    payload = {"text": "\n".join(lines)}
    if dry_run or os.getenv("DRY_RUN", "false").lower() == "true":
        print("[DRY RUN] Slack Daily Summary:\n" + payload["text"], flush=True)
        return

    try:
        response = requests.post(webhook, json=payload, timeout=20)
        response.raise_for_status()
        print(f"Daily 10 AM IST summary sent to Slack (total {total} orders)", flush=True)
    except Exception as e:
        print(f"[ERROR] Failed to post daily summary to Slack: {e}", flush=True)
        raise
