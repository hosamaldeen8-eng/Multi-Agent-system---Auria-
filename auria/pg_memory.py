"""Postgres/Supabase backend for the unified memory.

Drop-in, duck-type compatible with ``auria.memory.Memory`` — same method
signatures and return shapes — but backed by a hosted Postgres database
(e.g. Supabase) so the fleet's brain is durable and shared across restarts and
hosts. Activated by setting ``AURIA_DB_URL`` to a ``postgresql://...`` URL.

Tables live in the ``auria`` schema (see the Supabase migration
``auria_fleet_unified_memory``). Timestamps are returned as ISO strings (cast
``::text`` in queries) so results serialize cleanly through the MCP tools.
"""

from __future__ import annotations

import threading
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - clearer error than a raw ImportError
    raise ImportError(
        "AURIA_DB_URL is set but psycopg is not installed. "
        "Run: pip install 'psycopg[binary]>=3.1'"
    ) from exc

from psycopg.rows import dict_row


class PostgresMemory:
    """Hosted Postgres implementation of the shared memory store."""

    def __init__(self, db_url: str) -> None:
        self._lock = threading.Lock()
        self._conn = psycopg.connect(db_url, autocommit=True, row_factory=dict_row)

    def _exec(self, sql: str, params: tuple = ()) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(sql, params)

    def _one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def _all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    # -- memories --------------------------------------------------------
    def remember(self, key: str, value: str, scope: str = "global", author: str = "system") -> dict[str, Any]:
        self._exec(
            """INSERT INTO auria.memories(scope, key, value, author, updated)
               VALUES(%s, %s, %s, %s, now())
               ON CONFLICT(scope, key) DO UPDATE SET
                   value = excluded.value, author = excluded.author, updated = excluded.updated""",
            (scope, key, value, author),
        )
        return {"scope": scope, "key": key, "stored": True}

    def recall(self, key: str, scope: str = "global") -> dict[str, Any] | None:
        return self._one(
            "SELECT scope, key, value, author, updated::text AS updated "
            "FROM auria.memories WHERE scope=%s AND key=%s",
            (scope, key),
        )

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        like = f"%{query}%"
        mem = self._all(
            """SELECT 'memory' AS source, scope, key, value, author, updated::text AS ts
               FROM auria.memories WHERE key ILIKE %s OR value ILIKE %s
               ORDER BY updated DESC LIMIT %s""",
            (like, like, limit),
        )
        act = self._all(
            """SELECT 'activity' AS source, agent, kind, content, ref, created::text AS ts
               FROM auria.activity WHERE content ILIKE %s ORDER BY created DESC LIMIT %s""",
            (like, limit),
        )
        return mem + act

    # -- activity / shared chat -----------------------------------------
    def log(self, agent: str, kind: str, content: str, ref: str | None = None) -> dict[str, Any]:
        row = self._one(
            "INSERT INTO auria.activity(agent, kind, content, ref) VALUES(%s, %s, %s, %s) RETURNING id",
            (agent, kind, content, ref),
        )
        return {"logged": True, "id": row["id"] if row else None}

    def feed(self, limit: int = 25, kind: str | None = None) -> list[dict[str, Any]]:
        if kind:
            return self._all(
                "SELECT id, agent, kind, content, ref, created::text AS created "
                "FROM auria.activity WHERE kind=%s ORDER BY id DESC LIMIT %s",
                (kind, limit),
            )
        return self._all(
            "SELECT id, agent, kind, content, ref, created::text AS created "
            "FROM auria.activity ORDER BY id DESC LIMIT %s",
            (limit,),
        )

    # -- tasks -----------------------------------------------------------
    def add_task(self, title: str, detail: str = "", assignee: str = "orchestrator", author: str = "orchestrator") -> dict[str, Any]:
        row = self._one(
            "INSERT INTO auria.tasks(title, detail, assignee, author) VALUES(%s, %s, %s, %s) "
            "RETURNING id, title, assignee, status",
            (title, detail, assignee, author),
        )
        return row or {"error": "insert failed"}

    def list_tasks(self, status: str | None = None, assignee: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        clauses, params = [], []
        if status:
            clauses.append("status=%s")
            params.append(status)
        if assignee:
            clauses.append("assignee=%s")
            params.append(assignee)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        return self._all(
            f"SELECT id, title, detail, assignee, status, author, created::text AS created, "
            f"updated::text AS updated FROM auria.tasks {where} ORDER BY id DESC LIMIT %s",
            tuple(params),
        )

    def update_task(self, task_id: int, status: str | None = None, note: str | None = None, assignee: str | None = None) -> dict[str, Any]:
        sets, params = ["updated=now()"], []
        if status:
            sets.append("status=%s")
            params.append(status)
        if assignee:
            sets.append("assignee=%s")
            params.append(assignee)
        if note:
            sets.append("detail = detail || %s")
            params.append(f"\n[{note}]")
        params.append(task_id)
        row = self._one(
            f"UPDATE auria.tasks SET {', '.join(sets)} WHERE id=%s RETURNING id, title, assignee, status",
            tuple(params),
        )
        return row or {"error": f"task {task_id} not found"}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
