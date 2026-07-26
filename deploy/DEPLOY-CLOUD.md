# Deploy the Auria Fleet on a cloud platform (always-on)

The fleet is a **long-lived worker**, not a web app — it holds a Slack Socket
Mode connection open and runs the orchestrator per message. That rules out
serverless (Vercel/Netlify/Lambda). Use a platform that runs a persistent
process. All three below deploy straight from this repo via the `Dockerfile`.

> **Secrets go in the platform's dashboard, never in the repo or chat.**
> You'll set: `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, and
> (optional) `AURIA_DB_URL`. `SLACK_ALERT_CHANNEL` is already `C0BKTJWUL9K`.

Get your Anthropic key first: <https://console.anthropic.com/settings/keys> → **Create Key**.

---

## Option A — Render (recommended, closest to a "connect repo & go" UX)

1. Push is already done (branch `claude/multi-agent-orchestrator-8127yz`).
2. Go to <https://dashboard.render.com> → **New +** → **Blueprint** → connect this
   GitHub repo. Render reads `render.yaml` and creates a **Background Worker**.
3. When prompted, fill the secret env vars (`ANTHROPIC_API_KEY`,
   `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, and `AURIA_DB_URL` if using Supabase).
4. **Create** → Render builds the Dockerfile and starts the worker.
5. Logs tab should show `Auria fleet online` and `⚡️ Bolt app is running!`.

Background Workers have no public URL — correct, because Socket Mode is
outbound-only. Starter plan is ~$7/mo.

## Option B — Railway

1. <https://railway.app> → **New Project** → **Deploy from GitHub repo** → pick
   this repo/branch. Railway auto-detects the `Dockerfile`.
2. **Variables** tab → add `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`,
   `SLACK_APP_TOKEN`, `SLACK_ALERT_CHANNEL=C0BKTJWUL9K`, and optional
   `AURIA_DB_URL`.
3. Deploy. Check **Deploy Logs** for `Bolt app is running!`.
4. No networking/port config needed (Socket Mode is outbound-only).

## Option C — Fly.io (CLI)  ← this repo ships a ready `fly.toml`

A worker-tuned `fly.toml` (no public HTTP service) is already in the repo, so
deployment is just: create the app, set secrets, deploy.

```bash
# one-time
curl -L https://fly.io/install.sh | sh     # installs flyctl
fly auth login

# from the repo root (uses the committed fly.toml + Dockerfile)
fly launch --copy-config --no-deploy
#   - keeps the existing fly.toml
#   - if it says the app name "auria-fleet" is taken, accept a new unique name
#   - do NOT add a public service/port when asked (Socket Mode is outbound-only)

# set the secrets (never commit these)
fly secrets set \
  ANTHROPIC_API_KEY=sk-ant-... \
  SLACK_BOT_TOKEN=xoxb-... \
  SLACK_APP_TOKEN=xapp-... \
  AURIA_DB_URL="postgresql://postgres:PASSWORD@db.lxuuapitmxjwbbmsrehj.supabase.co:5432/postgres"
  # ^ AURIA_DB_URL optional; omit to use in-container SQLite (resets on redeploy)

fly deploy
fly logs           # look for "Auria fleet online" and "⚡️ Bolt app is running!"
```

The `[[vm]]` block runs one always-on 1 GB machine. Redeploys reconnect Slack
automatically; with `AURIA_DB_URL` set, the fleet's memory survives them.
To scale down when idle isn't wanted — keep it at 1 machine (`fly scale count 1`).

---

## Memory: use the hosted Supabase brain in the cloud

Set `AURIA_DB_URL` so the fleet's memory persists across restarts/redeploys
(otherwise it uses an ephemeral in-container SQLite file that resets on redeploy):

```
AURIA_DB_URL=postgresql://postgres:YOUR_DB_PASSWORD@db.lxuuapitmxjwbbmsrehj.supabase.co:5432/postgres
```

(Password: Supabase → Project Settings → Database → Connection string.)

## Verifying it's live

- Platform logs show `Auria fleet online` + `Bolt app is running!`.
- In Slack, `@auria-fleet hello` in **#auria-ops** → it replies in-thread.
- Redeploys reconnect automatically; with `AURIA_DB_URL` set, memory survives them.

## After go-live

Rotate the Slack tokens if they were ever shared in plain text, and keep the
Anthropic key only in the platform's secret store.
