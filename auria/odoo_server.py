"""In-process MCP server giving the Odoo Ops agent read access to Auria's Odoo.

Talks to Odoo over its standard external JSON/XML-RPC API. Read-only by design
(search_read / read / count / fields) so the Ops agent can monitor and report
without risk of mutating live data. Add write tools (create/write/unlink) later
only behind explicit human approval.

Configured via ODOO_URL / ODOO_DB / ODOO_USERNAME / ODOO_API_KEY.
"""

from __future__ import annotations

import asyncio
import json
import xmlrpc.client
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from .settings import settings


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2, default=str)}]}


def _error(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}], "is_error": True}


class OdooClient:
    """Minimal blocking Odoo external-API client (used off the event loop)."""

    def __init__(self) -> None:
        self._uid: int | None = None
        self._common = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/common")
        self._models = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/object")

    def _ensure_login(self) -> int:
        if self._uid is None:
            uid = self._common.authenticate(
                settings.odoo_db, settings.odoo_username, settings.odoo_api_key, {}
            )
            if not uid:
                raise RuntimeError("Odoo authentication failed — check ODOO_* env vars.")
            self._uid = uid
        return self._uid

    def execute(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        uid = self._ensure_login()
        return self._models.execute_kw(
            settings.odoo_db, uid, settings.odoo_api_key, model, method, args, kwargs or {}
        )


def build_odoo_server(client: OdooClient | None = None):
    """Create the ``odoo`` MCP server. Returns ``None`` if Odoo is not configured."""
    if not settings.odoo_enabled:
        return None

    client = client or OdooClient()

    async def _run(model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        return await asyncio.to_thread(client.execute, model, method, args, kwargs)

    @tool(
        "odoo_search_read",
        "Search and read records from an Odoo model. `domain` is a JSON list of "
        "Odoo domain triplets, e.g. [[\"state\",\"=\",\"confirmed\"]]. `fields` is a "
        "JSON list of field names. Returns matching records.",
        {"model": str, "domain": str, "fields": str, "limit": int},
    )
    async def odoo_search_read(args: dict[str, Any]) -> dict[str, Any]:
        try:
            domain = json.loads(args.get("domain") or "[]")
            fields = json.loads(args.get("fields") or "[]")
            limit = int(args.get("limit") or 20)
            rows = await _run(
                args["model"], "search_read", [domain], {"fields": fields, "limit": limit}
            )
            return _text(rows)
        except Exception as exc:  # noqa: BLE001 - surface any Odoo/RPC error to the agent
            return _error(f"{type(exc).__name__}: {exc}")

    @tool(
        "odoo_read",
        "Read specific records by id from an Odoo model. `ids` and `fields` are JSON lists.",
        {"model": str, "ids": str, "fields": str},
    )
    async def odoo_read(args: dict[str, Any]) -> dict[str, Any]:
        try:
            ids = json.loads(args["ids"])
            fields = json.loads(args.get("fields") or "[]")
            rows = await _run(args["model"], "read", [ids], {"fields": fields})
            return _text(rows)
        except Exception as exc:  # noqa: BLE001
            return _error(f"{type(exc).__name__}: {exc}")

    @tool(
        "odoo_count",
        "Count records matching a domain on an Odoo model. `domain` is a JSON list of triplets.",
        {"model": str, "domain": str},
    )
    async def odoo_count(args: dict[str, Any]) -> dict[str, Any]:
        try:
            domain = json.loads(args.get("domain") or "[]")
            n = await _run(args["model"], "search_count", [domain])
            return _text({"model": args["model"], "count": n})
        except Exception as exc:  # noqa: BLE001
            return _error(f"{type(exc).__name__}: {exc}")

    @tool(
        "odoo_fields",
        "List the available fields (name, type, label) on an Odoo model. Use to discover schema.",
        {"model": str},
    )
    async def odoo_fields(args: dict[str, Any]) -> dict[str, Any]:
        try:
            info = await _run(
                args["model"], "fields_get", [], {"attributes": ["string", "type", "help"]}
            )
            return _text(info)
        except Exception as exc:  # noqa: BLE001
            return _error(f"{type(exc).__name__}: {exc}")

    return create_sdk_mcp_server(
        name="odoo",
        version="0.1.0",
        tools=[odoo_search_read, odoo_read, odoo_count, odoo_fields],
    )


ODOO_TOOLS = [
    "mcp__odoo__odoo_search_read",
    "mcp__odoo__odoo_read",
    "mcp__odoo__odoo_count",
    "mcp__odoo__odoo_fields",
]
