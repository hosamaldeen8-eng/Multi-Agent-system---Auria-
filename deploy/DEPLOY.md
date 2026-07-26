# Deploying the Auria Fleet as an always-on systemd service

This runs the fleet permanently on your own Linux server (Debian/Ubuntu). It
restarts on crash and on boot. Budget ~10 minutes.

> **Why not this cloud session?** The Claude Code web session runs in an
> ephemeral container that's reclaimed when the session ends — a process there
> can't stay up. A server you control is the permanent home.

---

## 0. Prerequisites

- A Linux box you control (Ubuntu 22.04+/Debian 12+), with `sudo` and outbound
  internet.
- An **Anthropic API key** — the headless service authenticates with this, not
  the interactive `claude` login. Create one at
  <https://console.anthropic.com/settings/keys>.

## 1. Get the code onto the server

```bash
git clone https://github.com/hosamaldeen8-eng/Multi-Agent-system---Auria-.git
cd Multi-Agent-system---Auria-
git checkout claude/multi-agent-orchestrator-8127yz
```

## 2. Run the installer

```bash
sudo bash deploy/install.sh
```

It installs Node.js + the Claude Code CLI (the Agent SDK's runtime), builds a
Python venv with the dependencies, writes and **enables** the
`auria-fleet` systemd unit, and creates a `.env` from the template. It does
**not** start the service yet — you add credentials first.

## 3. Create the Slack app (one time, ~4 clicks)

1. Go to <https://api.slack.com/apps> → **Create New App** → **From a manifest**.
2. Pick your workspace, then paste the contents of
   [`deploy/slack-app-manifest.yaml`](slack-app-manifest.yaml). Create the app.
3. **OAuth & Permissions** → **Install to Workspace** → authorize. Copy the
   **Bot User OAuth Token** — it starts with `xoxb-`.
4. **Basic Information** → **App-Level Tokens** → **Generate Token and Scopes** →
   add the scope `connections:write` → generate. Copy that token — it starts
   with `xapp-`.

That's the whole Slack setup — the manifest already turned on Socket Mode and
subscribed to `app_mention` + `message.im`, so there's nothing else to click.

## 4. (Optional) Get an Odoo API key for the Ops agent

In Odoo (odoo.auria.global): click your avatar → **My Profile** →
**Account Security** tab → **New API Key**. Copy it into `ODOO_API_KEY`.
Leave the Odoo vars blank to run without the Ops agent for now.

## 5. Fill in credentials

```bash
nano .env
```

Set at minimum:

```ini
ANTHROPIC_API_KEY=sk-ant-...
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_ALERT_CHANNEL=C0XXXXXXXXX   # channel ID for proactive alerts (see tip below)
# Optional Odoo:
ODOO_URL=https://odoo.auria.global
ODOO_DB=auria
ODOO_USERNAME=bot@auria.global
ODOO_API_KEY=...
```

> **Alert channel tip:** use the channel **ID**, not the name, for reliable
> posting. In Slack, open the channel → click its name → **About** → the ID
> (e.g. `C0XXXXXXXXX`) is at the bottom. Invite the bot to that channel, or rely
> on the `chat:write.public` scope for public channels.

## 6. Start it

```bash
sudo systemctl start auria-fleet
journalctl -u auria-fleet -f          # watch it come online
```

You should see `Auria fleet online`. Now in Slack:

- **@mention** the bot in a channel it's in, or **DM** it → it replies in-thread.
- The monitoring loop runs every `AURIA_LOOP_INTERVAL_SECONDS` and posts real
  problems to your alert channel.

## Operating it

```bash
sudo systemctl status auria-fleet     # health
journalctl -u auria-fleet -f          # live logs
sudo systemctl restart auria-fleet    # after editing .env
sudo systemctl stop auria-fleet       # stop
sudo systemctl disable auria-fleet    # stop auto-start on boot
```

To update to new code:

```bash
cd Multi-Agent-system---Auria- && git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart auria-fleet
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Slack is not configured` and exits | `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` missing in `.env`. |
| Auth / 401 from Anthropic | `ANTHROPIC_API_KEY` missing or invalid. |
| Bot doesn't answer a channel mention | Invite the bot to that channel, and confirm the app is installed. |
| `claude: command not found` in logs | Re-run `sudo npm install -g @anthropic-ai/claude-code`. |
| Odoo tool errors | Check `ODOO_*` values; the API key must belong to `ODOO_USERNAME`. |
| Want it quieter/louder | Tune `AURIA_LOOP_INTERVAL_SECONDS` and `AURIA_EFFORT` in `.env`, then restart. |

The data (shared memory) lives in `./data/auria_memory.db` — back that up if you
care about the fleet's accumulated knowledge and task history.
