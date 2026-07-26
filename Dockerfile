# Auria Fleet — container image for always-on deployment.
# Runs the fleet as a long-lived worker (Slack Socket Mode needs no inbound port).
# Works on Render (Background Worker), Railway, Fly.io, or any container host.

FROM python:3.11-slim

# Node.js 22 — the Claude Agent SDK runs the Claude Code CLI under the hood.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite fallback dir (prefer AURIA_DB_URL for hosted Supabase memory).
RUN mkdir -p /app/data
ENV PYTHONUNBUFFERED=1

# No EXPOSE: Socket Mode is outbound-only, so this worker needs no public port.
CMD ["python", "-m", "auria.main"]
