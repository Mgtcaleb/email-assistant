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
