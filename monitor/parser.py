import re
from email.utils import parsedate_to_datetime

ORDER_RE = re.compile(r"\b(\d{3}-\d{7}-\d{7})\b")
ETA_PATTERNS = [
    re.compile(r"(?:arriving|expected delivery|delivery date|deliver(?:y|ed)? by)\s*(?:on|:)?\s*([A-Z][a-z]{2,8}\s+\d{1,2}(?:,\s*\d{4})?|\d{1,2}\s+[A-Z][a-z]{2,8}(?:\s+\d{4})?)", re.I),
    re.compile(r"(?:arriving|expected delivery|delivery date)\s*(?:on|:)?\s*(\d{4}-\d{2}-\d{2})", re.I),
]

def detect_status(subject: str, body: str) -> str:
    text = f"{subject}\n{body}".lower()
    # More terminal/specific states first to avoid "not delivered" false matches.
    if re.search(r"\b(cancelled|canceled|order cancellation|has been cancelled)\b", text):
        return "CANCELLED"
    if re.search(r"\b(returned to seller|return completed|refund issued|item returned)\b", text):
        return "RETURNED"
    if re.search(r"\b(out for delivery|driver is delivering|out-for-delivery)\b", text):
        return "OUT_FOR_DELIVERY"
    if re.search(r"\b(delivered|was delivered|has been delivered)\b", text):
        return "DELIVERED"
    if re.search(r"\b(shipped|has shipped|dispatched|on the way|package is on its way)\b", text):
        return "SHIPPED"
    if re.search(r"\b(order placed|order confirmation|we've received your order|your order has been received)\b", text):
        return "ORDER_PLACED"
    return "UNKNOWN"

def extract_eta(text: str):
    for pattern in ETA_PATTERNS:
        match = pattern.search(text)
        if match:
            return " ".join(match.group(1).split())
    return None

def parse_message(subject: str, body: str, sender: str, internal_date: str):
    full = f"{subject}\n{body}"
    ids = list(dict.fromkeys(ORDER_RE.findall(full)))
    if not ids:
        return []
    status = detect_status(subject, body)
    eta = extract_eta(full)
    marketplace = "amazon.com" if "amazon.com" in sender.lower() or "amazon.com" in full.lower() else "amazon.in"
    return [{"order_id": oid, "status": status, "eta": eta, "marketplace": marketplace} for oid in ids]
