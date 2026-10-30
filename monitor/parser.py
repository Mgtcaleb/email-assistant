import re
from email.utils import parsedate_to_datetime

from datetime import datetime, date, timedelta

ORDER_RE = re.compile(r"\b(\d{3}-\d{7}-\d{7})\b")
ETA_PATTERNS = [
    re.compile(r"(?:arriving|expected delivery|delivery date|deliver(?:y|ed)? by|guaranteed delivery|estimated delivery)\s*(?:on|:)?\s*(today|tomorrow)(?:\s+by\s+[^\n\r,.<]+)?", re.I),
    re.compile(r"(?:arriving|expected delivery|delivery date|deliver(?:y|ed)? by|guaranteed delivery|estimated delivery)\s*(?:on|:)?\s*(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[,\s]+)?([A-Z][a-z]{2,8}\s+\d{1,2}(?:,\s*\d{4})?|\d{1,2}\s+[A-Z][a-z]{2,8}(?:\s+\d{4})?)", re.I),
    re.compile(r"(?:arriving|expected delivery|delivery date)\s*(?:on|:)?\s*(\d{4}-\d{2}-\d{2})", re.I),
]

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

def parse_eta_date(eta_str: str, ref_date: date = None) -> date | None:
    """Parses an ETA string into a datetime.date object relative to ref_date."""
    if not eta_str:
        return None
    ref = ref_date or date.today()
    s = eta_str.lower().strip()

    if "today" in s:
        return ref
    if "tomorrow" in s:
        return ref + timedelta(days=1)

    # ISO format YYYY-MM-DD
    iso_match = re.search(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b", s)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    # Day Month [Year] e.g. '31 October 2026', '31 Oct'
    m1 = re.search(r"\b(\d{1,2})\s+([a-z]{3,9})(?:\s+(\d{4}))?\b", s)
    if m1 and m1.group(2) in MONTH_MAP:
        d = int(m1.group(1))
        m = MONTH_MAP[m1.group(2)]
        y = int(m1.group(3)) if m1.group(3) else ref.year
        if not m1.group(3) and m < ref.month:
            y += 1
        try:
            return date(y, m, d)
        except ValueError:
            pass

    # Month Day [Year] e.g. 'October 31, 2026', 'Oct 31'
    m2 = re.search(r"\b([a-z]{3,9})\s+(\d{1,2})(?:[,\s]+(\d{4}))?\b", s)
    if m2 and m2.group(1) in MONTH_MAP:
        m = MONTH_MAP[m2.group(1)]
        d = int(m2.group(2))
        y = int(m2.group(3)) if m2.group(3) else ref.year
        if not m2.group(3) and m < ref.month:
            y += 1
        try:
            return date(y, m, d)
        except ValueError:
            pass

    return None

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
    ref_date = None
    if internal_date:
        try:
            ref_date = parsedate_to_datetime(internal_date).date()
        except Exception:
            pass
    eta_d = parse_eta_date(eta, ref_date=ref_date)
    marketplace = "amazon.com" if "amazon.com" in sender.lower() or "amazon.com" in full.lower() else "amazon.in"
    return [{
        "order_id": oid,
        "status": status,
        "eta": eta,
        "eta_date": eta_d.isoformat() if eta_d else None,
        "marketplace": marketplace
    } for oid in ids]
