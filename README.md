# OpenClaw + Amazon Gmail → Slack alerts (Render)

This repository deploys the **official OpenClaw Gateway** plus a small deterministic Gmail monitor in the same Render service. The monitor is the order-alert engine; OpenClaw provides the agent gateway/UI. Alerts go to Slack only.

## What it does
- Polls Gmail every `POLL_SECONDS` (default 300) using Gmail API read-only OAuth.
- Searches recent Amazon order/shipping/delivery messages.
- Extracts Amazon order IDs, marketplace, best-effort ETA, and status.
- Persists state + processed Gmail message IDs in SQLite at `/data/monitor.db`.
- Sends a Slack message only for a new order or a meaningful status/ETA change.
- Never sends email, never posts to WhatsApp/Telegram, and does not access Amazon accounts directly.

**Important limits:** this is email-derived tracking. Amazon may not email every intermediate carrier scan; status/ETA are only as current as the messages Gmail receives. It does not sign in to Amazon or query private Amazon order pages. The parser is heuristic and should be tested against your own Amazon.in / Amazon.com emails before relying on it.

## 1. Create Google OAuth credentials
1. Open https://console.cloud.google.com/ and create/select a project.
2. Enable **Gmail API**.
3. Configure the OAuth consent screen. For personal use, choose External and add your Gmail address as a test user if the app remains in Testing.
4. Create OAuth Client ID → **Desktop app**. Download the JSON as `credentials.json` into `scripts/`.
5. On your Mac, use Python 3.11+:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-oauth.txt
   python scripts/get_refresh_token.py
   ```
6. A browser opens. Sign in to the Gmail account receiving Amazon order emails and approve the read-only Gmail permission.
7. Copy the printed refresh token. Treat it like a password. If Google shows an unverified-app warning during development, proceed only if you created the OAuth project and understand the permissions.
8. For long-running production use, set the OAuth consent screen to **In production** where applicable. Google may require verification for broader distribution; for a private personal app, check the current Google OAuth testing/refresh-token expiry rules.

Do not commit `credentials.json`, token files, or refresh tokens.

## 2. Create Slack webhook
1. In Slack, create a channel such as `#amazon-order-alerts`.
2. Create a Slack app at https://api.slack.com/apps → From scratch.
3. Enable **Incoming Webhooks**, add a webhook to the alert channel, and copy the URL.
4. Keep it private. Anyone with the URL can post to that channel.

## 3. Deploy to Render
1. Create a private GitHub repository and upload this project (do not upload `credentials.json`).
2. In Render, choose **New → Blueprint**, connect the repository, and apply `render.yaml`.
3. Render creates a paid Standard web service (2 GB RAM) with a 1 GB persistent disk. This is intentional: OpenClaw state and SQLite must survive restarts/redeploys. Free Render services cannot use persistent disks and may spin down.
4. In Render → service → Environment, set:
   - `GMAIL_CLIENT_ID`
   - `GMAIL_CLIENT_SECRET`
   - `GMAIL_REFRESH_TOKEN`
   - `GMAIL_USER` (the Gmail account address)
   - `SLACK_WEBHOOK_URL`
   - Optional: `AMAZON_MARKETS=amazon.in,amazon.com`
   - Optional: `POLL_SECONDS=300`
   - Optional: `INITIAL_LOOKBACK_DAYS=30`
   - Optional: `SEND_ONLINE_ALERT=true` (sends a 🟢 ONLINE notification to Slack when started)
   - Optional: `HEARTBEAT_HOURS=12` (sends periodic health status to Slack)
   - Optional: `OPENAI_API_KEY` if you want to configure an OpenAI model for interactive OpenClaw use. The Gmail monitor does not need an LLM key.
5. Save changes and let Render redeploy.
6. Open `https://YOUR-SERVICE.onrender.com/startupz` and confirm the OpenClaw Gateway health check responds successfully (port 10000).
7. Open the service logs. The monitor fetches at most 20 messages per poll and pauses between Gmail message reads to reduce Gmail API quota pressure. The monitor logs Gmail polling and Slack delivery outcomes. A missing-credentials warning means the Gmail/Slack environment variables are not complete. Do not enable verbose email-body logging.

## 4. Keep 24x7 Online & Online Status Feature

Render free tier instances automatically spin down after 15 minutes of inbound HTTP inactivity. To keep your service active 24x7 and monitor its health:

### Automatic 24x7 Keep-Alive via GitHub Actions
- This repository includes `.github/workflows/keep_alive.yml`.
- It triggers automatically every 14 minutes (`*/14 * * * *`) via GitHub Actions, sending a `GET` probe to `https://openclaw-amazon-slack.onrender.com/startupz`.
- This ensures Render never spins down your web service.
- If you use a custom Render service URL, set repository secret `RENDER_SERVICE_URL` in **GitHub → Settings → Secrets and variables → Actions**.
- Add repository secret `SLACK_WEBHOOK_URL` to receive alerts if Render ever goes offline.

### Local / Cron Keep-Alive Script
You can also run the monitor script from any machine or cron job:
```bash
python3 scripts/keep_alive.py --url https://YOUR-SERVICE.onrender.com/startupz
```

### Online Status Slack Alerts
- **Startup Alert**: When the container boots up, it automatically sends a `🟢 OpenClaw Amazon Monitor is ONLINE` card to your configured Slack channel.
- **Heartbeat Alerts**: Set `HEARTBEAT_HOURS=12` (or any interval) to receive periodic status reports with uptime and order tracking metrics.
- **Diagnostic Snapshot**: Run `python3 -m monitor.health` inside the container or locally to inspect SQLite state and connectivity.

## 5. OpenClaw UI
- Render URL: `https://YOUR-SERVICE.onrender.com/`
- Gateway token: Render Dashboard → service → Environment → `OPENCLAW_GATEWAY_TOKEN`.
- The token is a secret. Do not share it or put it in a public URL.
- For interactive agent replies, configure a supported model provider in OpenClaw. The background Gmail monitor works independently.

## 6. Test safely
1. First set `DRY_RUN=true`. The monitor logs what it would post but does not send Slack messages.
2. Confirm the correct Gmail account and Amazon messages are detected.
3. Set `DRY_RUN=false` (or leave unset; default is false) to enable Slack.
4. Use `python -m monitor.main --once` locally to run a one-time poll after configuring `.env` or environment variables.

## 7. Alert behavior
Statuses: `ORDER_PLACED`, `SHIPPED`, `OUT_FOR_DELIVERY`, `DELIVERED`, `CANCELLED`, `RETURNED`, `UNKNOWN`.

The monitor sends an alert for:
- a newly detected order ID;
- a status change;
- an ETA change (when both old and new values are known).

Repeated messages with no meaningful change are suppressed.

## 8. Security / operations
- Gmail OAuth scope is `https://www.googleapis.com/auth/gmail.readonly`.
- The service does not request Gmail send/modify permissions.
- Slack is the only notification destination.
- Store all credentials as Render secret environment variables.
- Keep the Render service private to your team if possible; protect OpenClaw with its generated gateway token.
- Back up `/data/monitor.db` and OpenClaw state periodically.
- A persistent Render disk is attached to one service instance; do not scale this service horizontally.
- Revoke OAuth access in Google Account → Security → Third-party connections if you retire the service.

## Files
- `Dockerfile`: builds Node + OpenClaw + Python monitor runtime.
- `render.yaml`: Render Blueprint, persistent disk, generated gateway token.
- `.github/workflows/keep_alive.yml`: 24x7 keep-alive workflow (runs every 14 mins).
- `monitor/`: Gmail polling, parsing, SQLite state, Slack notifier, online status.
- `scripts/get_refresh_token.py`: one-time local OAuth helper.
- `scripts/keep_alive.py`: standalone keep-alive pinger and status monitor.
