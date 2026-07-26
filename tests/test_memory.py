"""Tests for the unified memory store (no Claude/Slack/Odoo needed)."""

import os
import tempfile

from auria.memory import Memory


def _fresh() -> Memory:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Memory(path)


def test_remember_and_recall():
    m = _fresh()
    m.remember("supplier.acme.lead_time", "14 days", scope="odoo", author="odoo-ops")
    hit = m.recall("supplier.acme.lead_time", scope="odoo")
    assert hit is not None
    assert hit["value"] == "14 days"
    assert m.recall("missing") is None


def test_remember_upserts():
    m = _fresh()
    m.remember("k", "v1")
    m.remember("k", "v2")
    assert m.recall("k")["value"] == "v2"


def test_activity_feed_and_search():
    m = _fresh()
    m.log("odoo-ops", "action", "Checked MO-123, it is late")
    m.log("code-reviewer", "review", "PASS: numbers verified")
    feed = m.feed(limit=10)
    assert len(feed) == 2
    assert feed[0]["kind"] == "review"  # newest first
    reviews = m.feed(limit=10, kind="review")
    assert len(reviews) == 1
    assert m.search("late")  # finds the activity entry


def test_task_board():
    m = _fresh()
    t = m.add_task("Reconcile March invoices", assignee="odoo-ops")
    tid = t["id"]
    assert t["status"] == "open"
    m.update_task(tid, status="in_progress", note="pulled 42 invoices")
    m.update_task(tid, status="done")
    done = m.list_tasks(status="done")
    assert any(x["id"] == tid for x in done)
