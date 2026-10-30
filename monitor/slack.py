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
