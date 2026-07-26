# Auria Multi-Agent Fleet

A small orchestrated team of Claude agents that runs **alongside the Auria
business** — with a unified memory, a shared chat where agents review each
other's work, a main orchestrator that delegates to specialists, and each agent
carrying its own skills, MCP tools, model, and monitoring loops.

Built on the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk).

## What's in the box

- **Orchestrator** — the main agent; plans work and delegates.
- **Specialist subagents**
  - `odoo-ops` — reads Auria's live Odoo (manufacturing, BOMs, stock, projects, accounting).
  - `code-reviewer` — independently reviews another agent's output.
  - `task-verifier` — confirms a task was actually completed, with evidence.
- **Unified memory** (SQLite) shared by every agent: durable facts, a shared
  activity log (the cross-agent chat + peer-review channel), and a task board.
- **Slack bridge** (Socket Mode) for monitoring and two-way communication.
- **Monitoring loops** that run on an interval and alert Slack on real problems.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full picture.

## Requirements

- **Python 3.10+**
- **Node.js 18+** — the Claude Agent SDK runs the Claude Code runtime under the hood.
- An **Anthropic API key**.
- (Optional) a **Slack app** for monitoring/commands, and **Odoo** credentials
  for the Ops agent.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in the values
```

Fill in `.env`:
- `ANTHROPIC_API_KEY` (required)
- `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` (for the Slack service)
- `ODOO_URL` / `ODOO_DB` / `ODOO_USERNAME` / `ODOO_API_KEY` (for the Odoo agent)

## Run

**One-shot** (quickest smoke test — no Slack needed):

```bash
python -m auria.main --once "Ask the odoo-ops agent how many manufacturing orders are open, then have task-verifier confirm the number."
```

**Full service** (Slack + monitoring loop):

```bash
python -m auria.main
```

Then `@mention` the bot in a channel, or DM it. The fleet posts proactive
monitoring alerts to `SLACK_ALERT_CHANNEL`.

## Tests

```bash
pip install pytest
pytest tests/          # memory-store tests run with no external services
```

## Customizing the fleet

- **Add / retune an agent** → edit `auria/fleet.py` (`AgentDefinition`: its own
  `tools`, `mcpServers`, `model`, and skills).
- **Add a data source** → write an in-process MCP server like
  `auria/odoo_server.py` and register it in `auria/orchestrator.py`.
- **Add a monitor** → append to `MONITORS` in `auria/loops.py`.
- **Agent playbooks** live in `.claude/skills/`.

## Safety

The orchestrator runs with `permission_mode="dontAsk"`: only allowlisted,
read-only tools run and everything else is auto-denied. No agent has
`Write`/`Edit`/`Bash`, and the Odoo tools are read-only. Any outward or
irreversible action must be explicitly requested by a human.
