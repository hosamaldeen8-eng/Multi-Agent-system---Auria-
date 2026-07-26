# Run the Auria Fleet locally on Windows (on your Pro subscription)

This runs the fleet on your own Windows PC using **WSL2 (Ubuntu)**. It logs in
with your **Claude Pro/Max subscription** (no API key), so it draws on your
subscription instead of API credit.

**Know the tradeoffs:**
- It's live only while your PC is **on, not asleep, and the terminal is open**.
  Not 24/7. (For always-on, use `deploy/DEPLOY-CLOUD.md` with an API key.)
- Keep the monitoring loop **off** locally (`AURIA_LOOP_INTERVAL_SECONDS=0`) so
  it only uses your subscription when you actually message it — a background
  loop would quietly eat your daily Pro limit.
- Heavy automated use can still hit subscription limits; this is meant for your
  own light, interactive use.

---

## 1. Install WSL2 + Ubuntu (one time)

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

Reboot when it asks. After reboot, **Ubuntu** opens and asks you to create a
Linux username + password (remember the password — it's your `sudo` password).

From now on, do everything in the **Ubuntu** terminal (search "Ubuntu" in Start).

## 2. Install the tools (in Ubuntu)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip curl git

# Node.js 22 (Claude Code runtime)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Claude Code CLI
sudo npm install -g @anthropic-ai/claude-code
```

## 3. Log in with your Pro subscription

```bash
claude
```

On first run it prompts to log in. Choose the **subscription / Claude account**
option (Claude Pro or Max) — **not** "API key". Finish the login in the browser
window it opens. Then type `/exit` to leave Claude Code.

> This is the key step: because you logged in with the subscription and you will
> **not** set `ANTHROPIC_API_KEY`, the fleet uses your Pro plan.

## 4. Get the code

```bash
git clone https://github.com/hosamaldeen8-eng/Multi-Agent-system---Auria-.git
cd Multi-Agent-system---Auria-
git checkout claude/multi-agent-orchestrator-8127yz

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Configure (Slack tokens, NO API key)

```bash
cp .env.example .env
nano .env
```

Set these, then save (Ctrl+O, Enter, Ctrl+X):

```ini
# Leave ANTHROPIC_API_KEY blank / delete the line — that's what makes it use your subscription.
SLACK_BOT_TOKEN=xoxb-...your bot token...
SLACK_APP_TOKEN=xapp-...your app token...
SLACK_ALERT_CHANNEL=C0BKTJWUL9K

# Local: only spend when you message it (no background loop).
AURIA_LOOP_INTERVAL_SECONDS=0

# Optional: hosted memory that survives restarts (else local SQLite file is used).
# AURIA_DB_URL=postgresql://postgres:PASSWORD@db.lxuuapitmxjwbbmsrehj.supabase.co:5432/postgres
```

## 6. Run it

```bash
source .venv/bin/activate      # if not already active
python -m auria.main
```

You should see `Auria fleet online` and `⚡️ Bolt app is running!`. Now in Slack,
`@auria-fleet hello` in **#auria-ops** → it replies in-thread.

**Keep the Ubuntu terminal open** while you want the fleet live. Press **Ctrl+C**
to stop it. To start it again later:

```bash
cd ~/Multi-Agent-system---Auria- && source .venv/bin/activate && python -m auria.main
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Slack is not configured` | `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` missing in `.env`. |
| Auth / login errors from Claude | Re-run `claude`, `/login`, pick the subscription account. |
| `claude: command not found` | Re-run `sudo npm install -g @anthropic-ai/claude-code`. |
| Bot doesn't answer | Make sure it's invited to the channel and the app has `app_mentions:read` (Reinstall to Workspace). |
| Hit your Pro daily limit | The fleet shares your subscription limit — space out usage, or switch to the API deploy for heavier use. |
