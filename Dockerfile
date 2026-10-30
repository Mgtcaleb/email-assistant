FROM node:24-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONWARNINGS="ignore:::google.api_core._python_version_support" \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000 \
    OPENCLAW_GATEWAY_PORT=10000 \
    OPENCLAW_STATE_DIR=/data/.openclaw \
    OPENCLAW_WORKSPACE_DIR=/data/workspace \
    DATA_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw

WORKDIR /app
COPY requirements.txt .
RUN python3 -m pip install --break-system-packages -r requirements.txt

COPY monitor ./monitor
COPY scripts ./scripts
COPY start.sh ./start.sh
RUN chmod +x /app/start.sh && mkdir -p /data/.openclaw/tmp /data/.openclaw/state /data/workspace

EXPOSE 10000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/start.sh"]
