# Auria Fleet — Architecture

A small orchestrated team of Claude agents that runs alongside the Auria
business, built on the **Claude Agent SDK**.

```
                          ┌───────────────────────────┐
        Slack  ◀────────▶ │        Orchestrator       │  (ClaudeSDKClient)
   (mention / DM /        │  plans · delegates · reports
    proactive alerts)     └─────┬──────────┬──────────┘
                                │ Agent tool (delegation)
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                   ▼
        ┌───────────┐    ┌──────────────┐   ┌──────────────┐
        │ odoo-ops  │    │ code-reviewer│   │ task-verifier│   subagents
        └─────┬─────┘    └──────┬───────┘   └──────┬───────┘
              │                 │                  │
        ┌─────▼─────┐           │                  │
        │  Odoo MCP │           │  all agents      │
        │ (XML-RPC) │           ▼  read & write     ▼
        └───────────┘    ┌──────────────────────────────┐
                         │      Unified memory (MCP)     │  SQLite
                         │  facts · shared chat · tasks  │
                         └──────────────────────────────┘
```

## Components

| Piece | File | Role |
|---|---|---|
| **Orchestrator** | `auria/orchestrator.py` | The main agent. A persistent `ClaudeSDKClient` that plans work, delegates to subagents via the `Agent` tool, and reports. Serializes requests so the shared session stays coherent. |
| **Fleet roster** | `auria/fleet.py` | The orchestrator's system prompt + `AgentDefinition`s for each subagent. Each agent has its own persona, model, tool allowlist, and MCP access. |
| **Unified memory** | `auria/memory.py`, `auria/memory_server.py` | SQLite store exposed as an in-process MCP server given to **every** agent. Three surfaces: durable facts, a shared activity log (the cross-agent chat + review channel), and a task board. |
| **Odoo tools** | `auria/odoo_server.py` | Read-only Odoo external-API tools (search_read / read / count / fields) for the Ops agent. |
| **Slack bridge** | `auria/slack_bridge.py` | Socket-Mode app for two-way comms: humans @mention/DM the bot; the fleet posts proactive alerts. |
| **Monitoring loops** | `auria/loops.py` | Scheduled standing instructions the orchestrator runs on an interval; anything non-trivial is pushed to Slack. |

## How the five requirements map

- **Main orchestrator** → `Orchestrator` + the `Agent` tool for delegation.
- **Unified memory** → one SQLite store behind the `memory` MCP server, shared by all agents.
- **Shared chats + review each other's work** → the `activity` log; agents `log_activity` and `read_feed`; `code-reviewer` / `task-verifier` post verdicts (`kind="review"`).
- **Per-agent skills / MCP / model** → each `AgentDefinition` sets its own `tools`, `mcpServers`, `model`, and can preload skills from `.claude/skills/`.
- **Loop systems** → `MonitorLoop` runs monitors on `AURIA_LOOP_INTERVAL_SECONDS`.

## Safety posture

- The orchestrator runs `permission_mode="dontAsk"`: only allowlisted, read-only
  tools run; everything else is auto-denied (no prompt can hang a headless service).
- No agent is granted `Write`, `Edit`, or `Bash`. Odoo tools are read-only.
- Any outward or irreversible action must be explicitly requested by a human.

## Extending

- **New business agent** → add an `AgentDefinition` to `fleet.py` (give it its
  tools/MCP/model) and mention it in the orchestrator prompt.
- **New data source** → build an in-process MCP server like `odoo_server.py`,
  register it in `Orchestrator.__init__`, and grant its tools to the relevant agent.
- **New monitor** → append to `MONITORS` in `loops.py`.
- **Write access to Odoo** → add `create`/`write` tools guarded behind a human
  approval step before enabling.
