#!/usr/bin/env bash
#
# One-command installer for the Auria fleet as a systemd service.
# Tested on Debian/Ubuntu. Run from the repo checkout:
#
#     sudo bash deploy/install.sh
#
# It installs Node + the Claude Code CLI (the Agent SDK's headless runtime),
# creates a Python venv with the app's deps, writes a systemd unit, and enables
# it. It does NOT start the service — you edit .env with your credentials first.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_USER="${SUDO_USER:-$(id -un)}"
VENV="$APP_DIR/.venv"
PY="$VENV/bin/python"
UNIT="/etc/systemd/system/auria-fleet.service"

echo "==> Auria fleet installer"
echo "    app dir : $APP_DIR"
echo "    run user: $RUN_USER"

need_sudo() { if [ "$(id -u)" -ne 0 ]; then sudo "$@"; else "$@"; fi; }

# --- Node.js -----------------------------------------------------------
if ! command -v node >/dev/null 2>&1; then
  echo "==> Installing Node.js 22 (NodeSource)…"
  curl -fsSL https://deb.nodesource.com/setup_22.x | need_sudo -E bash -
  need_sudo apt-get install -y nodejs
else
  echo "==> Node present: $(node --version)"
fi

# --- Claude Code CLI (Agent SDK runtime) -------------------------------
if ! command -v claude >/dev/null 2>&1; then
  echo "==> Installing Claude Code CLI…"
  need_sudo npm install -g @anthropic-ai/claude-code
else
  echo "==> Claude CLI present: $(claude --version 2>/dev/null | head -1)"
fi

# --- Python venv + deps ------------------------------------------------
echo "==> Ensuring python3-venv…"
need_sudo apt-get install -y python3-venv >/dev/null 2>&1 || true
echo "==> Creating venv at $VENV…"
python3 -m venv "$VENV"
"$PY" -m pip install --upgrade pip >/dev/null
echo "==> Installing Python dependencies…"
"$PY" -m pip install -r "$APP_DIR/requirements.txt"

# --- .env + data dir ---------------------------------------------------
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "==> Created $APP_DIR/.env (chmod 600) — EDIT IT before starting."
else
  echo "==> $APP_DIR/.env already exists — leaving it untouched."
fi
mkdir -p "$APP_DIR/data"
chown -R "$RUN_USER" "$APP_DIR/data" 2>/dev/null || true

# --- systemd unit ------------------------------------------------------
echo "==> Writing $UNIT…"
need_sudo tee "$UNIT" >/dev/null <<UNITEOF
[Unit]
Description=Auria Multi-Agent Fleet
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$PY -m auria.main
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNITEOF

need_sudo systemctl daemon-reload
need_sudo systemctl enable auria-fleet.service

cat <<DONE

==> Installed and enabled (not started yet).

Next steps:
  1. Edit credentials:      nano $APP_DIR/.env
       - ANTHROPIC_API_KEY   (required)
       - SLACK_BOT_TOKEN     (xoxb-…)   see deploy/DEPLOY.md
       - SLACK_APP_TOKEN     (xapp-…)
       - ODOO_* (optional)
  2. Start the service:     sudo systemctl start auria-fleet
  3. Watch the logs:        journalctl -u auria-fleet -f
  4. Restart after edits:   sudo systemctl restart auria-fleet

DONE
