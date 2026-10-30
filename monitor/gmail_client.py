import base64, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def _credentials():
    required = ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError("Missing Gmail OAuth environment variables: " + ", ".join(missing))
    return Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        scopes=SCOPES,
    )

def _decode_part(part):
    data = part.get("body", {}).get("data")
    if data:
        try:
            return base64.urlsafe_b64decode(data + "===" ).decode("utf-8", "replace")
        except Exception:
            return ""
    out = ""
    for child in part.get("parts", []) or []:
        out += "\n" + _decode_part(child)
    return out

def _headers(payload):
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

def fetch_messages(query: str, max_results=100):
    service = build("gmail", "v1", credentials=_credentials(), cache_discovery=False)
    messages = []
    page_token = None
    while len(messages) < max_results:
        result = service.users().messages().list(
            userId="me", q=query, maxResults=min(100, max_results - len(messages)),
            pageToken=page_token
        ).execute()
        for item in result.get("messages", []):
            msg = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
            payload = msg.get("payload", {})
            headers = _headers(payload)
            messages.append({
                "id": msg["id"],
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "date": headers.get("date", ""),
                "body": _decode_part(payload)[:60000],
            })
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return messages
