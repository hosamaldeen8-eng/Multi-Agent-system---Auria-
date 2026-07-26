"""In-process MCP server exposing the unified memory to every agent.

The orchestrator and all subagents are given this server, so they share one
brain: durable facts (``remember``/``recall``/``search_memory``), a shared
activity log that doubles as the cross-agent chat and review channel
(``log_activity``/``read_feed``), and a shared task board
(``add_task``/``list_tasks``/``update_task``).
"""

from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from .memory import Memory


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2, default=str)}]}


def build_memory_server(memory: Memory):
    """Create the ``memory`` MCP server bound to a shared ``Memory`` instance."""

    @tool(
        "remember",
        "Store a durable fact for the whole fleet to reuse later. "
        "Use for stable knowledge (supplier lead times, product quirks, decisions).",
        {"key": str, "value": str, "scope": str, "author": str},
    )
    async def remember(args: dict[str, Any]) -> dict[str, Any]:
        return _text(
            memory.remember(
                key=args["key"],
                value=args["value"],
                scope=args.get("scope") or "global",
                author=args.get("author") or "unknown",
            )
        )

    @tool("recall", "Retrieve a fact previously stored with `remember`.", {"key": str, "scope": str})
    async def recall(args: dict[str, Any]) -> dict[str, Any]:
        hit = memory.recall(key=args["key"], scope=args.get("scope") or "global")
        return _text(hit or {"found": False, "key": args["key"]})

    @tool(
        "search_memory",
        "Full-text search across stored facts and the shared activity log. "
        "Use before starting work to see what the fleet already knows.",
        {"query": str},
    )
    async def search_memory(args: dict[str, Any]) -> dict[str, Any]:
        return _text(memory.search(query=args["query"], limit=int(args.get("limit") or 20)))

    @tool(
        "log_activity",
        "Post to the shared fleet log — the cross-agent chat. Use `kind`: "
        "note | action | review | alert | decision. This is how agents share "
        "what they did and review each other's work.",
        {"agent": str, "kind": str, "content": str, "ref": str},
    )
    async def log_activity(args: dict[str, Any]) -> dict[str, Any]:
        return _text(
            memory.log(
                agent=args.get("agent") or "unknown",
                kind=args.get("kind") or "note",
                content=args["content"],
                ref=args.get("ref") or None,
            )
        )

    @tool(
        "read_feed",
        "Read the most recent entries from the shared fleet log. "
        "Optionally filter by `kind` (e.g. 'review' to see peer reviews).",
        {"limit": int, "kind": str},
    )
    async def read_feed(args: dict[str, Any]) -> dict[str, Any]:
        return _text(memory.feed(limit=int(args.get("limit") or 25), kind=args.get("kind") or None))

    @tool("add_task", "Add a task to the shared board.", {"title": str, "detail": str, "assignee": str, "author": str})
    async def add_task(args: dict[str, Any]) -> dict[str, Any]:
        return _text(
            memory.add_task(
                title=args["title"],
                detail=args.get("detail") or "",
                assignee=args.get("assignee") or "orchestrator",
                author=args.get("author") or "orchestrator",
            )
        )

    @tool("list_tasks", "List tasks on the shared board, optionally filtered.", {"status": str, "assignee": str})
    async def list_tasks(args: dict[str, Any]) -> dict[str, Any]:
        return _text(
            memory.list_tasks(
                status=args.get("status") or None,
                assignee=args.get("assignee") or None,
                limit=int(args.get("limit") or 50),
            )
        )

    @tool(
        "update_task",
        "Update a task's status (open|in_progress|review|done|blocked), reassign it, "
        "or append a progress note.",
        {"task_id": int, "status": str, "note": str, "assignee": str},
    )
    async def update_task(args: dict[str, Any]) -> dict[str, Any]:
        return _text(
            memory.update_task(
                task_id=int(args["task_id"]),
                status=args.get("status") or None,
                note=args.get("note") or None,
                assignee=args.get("assignee") or None,
            )
        )

    server = create_sdk_mcp_server(
        name="memory",
        version="0.1.0",
        tools=[remember, recall, search_memory, log_activity, read_feed, add_task, list_tasks, update_task],
    )
    return server


# Tool names as the SDK exposes them (server name is "memory").
MEMORY_TOOLS = [
    "mcp__memory__remember",
    "mcp__memory__recall",
    "mcp__memory__search_memory",
    "mcp__memory__log_activity",
    "mcp__memory__read_feed",
    "mcp__memory__add_task",
    "mcp__memory__list_tasks",
    "mcp__memory__update_task",
]
