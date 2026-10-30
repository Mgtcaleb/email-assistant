"""Run locally after placing Google OAuth Desktop credentials at ./credentials.json."""
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
path = Path("credentials.json")
if not path.exists():
    raise SystemExit("Put your downloaded Google OAuth Desktop credentials in ./credentials.json")
flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nOAuth values (copy to Render Environment; do not commit):")
print("GMAIL_CLIENT_ID=" + creds.client_id)
print("GMAIL_CLIENT_SECRET=" + creds.client_secret)
print("GMAIL_REFRESH_TOKEN=" + creds.refresh_token)
