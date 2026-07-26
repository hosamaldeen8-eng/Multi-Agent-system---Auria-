"""Unified memory store shared by every agent in the fleet.

Backed by SQLite. Three tables give the fleet its shared brain:

- ``memories``  : durable key/value facts (scoped), e.g. "supplier X lead time".
- ``activity``  : an append-only shared log — the "shared chat" where agents
                  narrate what they did and post reviews of each other's work.
- ``tasks``     : the shared task board the orchestrator and workers coordinate on.

Every agent talks to this store through the in-process MCP tools defined in
``memory_server.py``, so a fact written by the Odoo agent is immediately
recallable by the reviewer, and vice-versa.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    scope    TEXT NOT NULL DEFAULT 'global',
    key      TEXT NOT NULL,
    value    TEXT NOT NULL,
    author   TEXT NOT NULL DEFAULT 'system',
    updated  TEXT NOT NULL,
    UNIQUE(scope, key)
);

CREATE TABLE IF NOT EXISTS activity (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    agent    TEXT NOT NULL,
    kind     TEXT NOT NULL,          -- note | action | review | alert | decision
    content  TEXT NOT NULL,
    ref      TEXT,                   -- optional link to a task id / entity
    created  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title    TEXT NOT NULL,
    detail   TEXT NOT NULL DEFAULT '',
    assignee TEXT NOT NULL DEFAULT 'orchestrator',
    status   TEXT NOT NULL DEFAULT 'open',   -- open | in_progress | review | done | blocked
    author   TEXT NOT NULL DEFAULT 'orchestrator',
    created  TEXT NOT NULL,
    updated  TEXT NOT NULL
);
"""


@dataclass
class Memory:
    """Thread-safe wrapper around the shared SQLite store."""

    db_path: str

    def __post_init__(self) -> None:
        Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- memories --------------------------------------------------------
    def remember(self, key: str, value: str, scope: str = "global", author: str = "system") -> dict[str, Any]:
        with self._lock:
            self._conn.execute(
                """INSERT INTO memories(scope, key, value, author, updated)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(scope, key) DO UPDATE SET
                       value=excluded.value, author=excluded.author, updated=excluded.updated""",
                (scope, key, value, author, _now()),
            )
            self._conn.commit()
        return {"scope": scope, "key": key, "stored": True}

    def recall(self, key: str, scope: str = "global") -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT scope, key, value, author, updated FROM memories WHERE scope=? AND key=?",
                (scope, key),
            ).fetchone()
        return dict(row) if row else None

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        like = f"%{query}%"
        with self._lock:
            mem = self._conn.execute(
                """SELECT 'memory' AS source, scope, key, value, author, updated AS ts
                   FROM memories WHERE key LIKE ? OR value LIKE ? ORDER BY updated DESC LIMIT ?""",
                (like, like, limit),
            ).fetchall()
            act = self._conn.execute(
                """SELECT 'activity' AS source, agent, kind, content, ref, created AS ts
                   FROM activity WHERE content LIKE ? ORDER BY created DESC LIMIT ?""",
                (like, limit),
            ).fetchall()
        return [dict(r) for r in mem] + [dict(r) for r in act]

    # -- activity / shared chat -----------------------------------------
    def log(self, agent: str, kind: str, content: str, ref: str | None = None) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO activity(agent, kind, content, ref, created) VALUES(?,?,?,?,?)",
                (agent, kind, content, ref, _now()),
            )
            self._conn.commit()
            entry_id = cur.lastrowid
        return {"logged": True, "id": entry_id}

    def feed(self, limit: int = 25, kind: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if kind:
                rows = self._conn.execute(
                    "SELECT id, agent, kind, content, ref, created FROM activity WHERE kind=? ORDER BY id DESC LIMIT ?",
                    (kind, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, agent, kind, content, ref, created FROM activity ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # -- tasks -----------------------------------------------------------
    def add_task(self, title: str, detail: str = "", assignee: str = "orchestrator", author: str = "orchestrator") -> dict[str, Any]:
        ts = _now()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO tasks(title, detail, assignee, status, author, created, updated) VALUES(?,?,?,?,?,?,?)",
                (title, detail, assignee, "open", author, ts, ts),
            )
            self._conn.commit()
            task_id = cur.lastrowid
        return {"id": task_id, "title": title, "assignee": assignee, "status": "open"}

    def list_tasks(self, status: str | None = None, assignee: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        clauses, params = [], []
        if status:
            clauses.append("status=?")
            params.append(status)
        if assignee:
            clauses.append("assignee=?")
            params.append(assignee)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT id, title, detail, assignee, status, author, created, updated FROM tasks {where} ORDER BY id DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def update_task(self, task_id: int, status: str | None = None, note: str | None = None, assignee: str | None = None) -> dict[str, Any]:
        sets, params = ["updated=?"], [_now()]
        if status:
            sets.append("status=?")
            params.append(status)
        if assignee:
            sets.append("assignee=?")
            params.append(assignee)
        if note:
            sets.append("detail = detail || ?")
            params.append(f"\n[{_now()}] {note}")
        params.append(task_id)
        with self._lock:
            self._conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", params)
            self._conn.commit()
            row = self._conn.execute(
                "SELECT id, title, assignee, status FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
        return dict(row) if row else {"error": f"task {task_id} not found"}

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def open_memory():
    """Return the shared store, picking Postgres/Supabase when configured.

    Uses ``PostgresMemory`` when ``AURIA_DB_URL`` is set (hosted, durable,
    shared), otherwise the local SQLite ``Memory`` (zero-config default).
    """
    from .settings import settings

    if settings.db_url:
        from .pg_memory import PostgresMemory

        return PostgresMemory(settings.db_url)
    return Memory(settings.db_path)
