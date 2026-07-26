"""The Orchestrator — the fleet's main agent.

Wraps a persistent ``ClaudeSDKClient`` configured with:
- the orchestrator system prompt and the specialist subagents (fleet.py),
- the unified-memory MCP server (shared by all agents),
- the Odoo MCP server (for the Ops agent),
- a read-only, auto-denied tool policy safe for headless operation.

One orchestrator instance serves the whole process; calls are serialized so the
shared session keeps coherent context across Slack messages and loop ticks.
"""

from __future__ import annotations

import asyncio

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .fleet import ORCHESTRATOR_SYSTEM_PROMPT, build_agents
from .memory import Memory
from .memory_server import MEMORY_TOOLS, build_memory_server
from .odoo_server import ODOO_TOOLS, OdooClient, build_odoo_server
from .settings import settings


def _extract_text(message) -> str:
    """Pull human-readable text out of an SDK message (duck-typed for resilience)."""
    # ResultMessage carries the final assembled result.
    result = getattr(message, "result", None)
    if isinstance(result, str) and result.strip():
        return result
    parts: list[str] = []
    for block in getattr(message, "content", None) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            parts.append(text)
    return "\n".join(parts)


class Orchestrator:
    """Persistent orchestrator agent over the shared fleet."""

    def __init__(self, memory: Memory) -> None:
        self.memory = memory
        self._lock = asyncio.Lock()
        self._client: ClaudeSDKClient | None = None

        mcp_servers: dict[str, object] = {"memory": build_memory_server(memory)}
        allowed_tools = ["Agent", "Read", "Grep", "Glob", *MEMORY_TOOLS]

        odoo_server = build_odoo_server(OdooClient()) if settings.odoo_enabled else None
        if odoo_server is not None:
            mcp_servers["odoo"] = odoo_server
            allowed_tools.extend(ODOO_TOOLS)

        self._options = ClaudeAgentOptions(
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            agents=build_agents(),
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            # Auto-deny anything not on the allowlist — safe for a headless service
            # (no interactive permission prompt can hang the process).
            permission_mode="dontAsk",
            model=settings.orchestrator_model,
            effort=settings.effort,  # low | medium | high | xhigh | max
            setting_sources=["project"],  # load .claude/skills + project CLAUDE.md
            max_turns=40,
        )

    async def connect(self) -> None:
        if self._client is None:
            self._client = ClaudeSDKClient(options=self._options)
            await self._client.connect()

    async def handle(self, prompt: str, session_id: str = "default") -> str:
        """Run one request through the orchestrator and return its final text."""
        await self.connect()
        assert self._client is not None
        async with self._lock:
            await self._client.query(prompt, session_id=session_id)
            final = ""
            async for message in self._client.receive_response():
                text = _extract_text(message)
                if text:
                    final = text  # last non-empty message is the assembled answer
            return final or "(no response)"

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
