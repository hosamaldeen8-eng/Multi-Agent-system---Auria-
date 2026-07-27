"""Entrypoint — wire the fleet together and run it.

Usage:
    python -m auria.main            # run the full service (Slack + monitoring loop)
    python -m auria.main --once "your request"   # one-shot: run a single request and print

The full service requires Slack credentials. The one-shot mode does not, so it's
the quickest way to smoke-test the orchestrator and its agents.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .loops import MonitorLoop
from .memory import open_memory
from .orchestrator import Orchestrator
from .scheduler import DailyTask
from .settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("auria")


async def run_once(prompt: str) -> None:
    memory = open_memory()
    orchestrator = Orchestrator(memory)
    try:
        print(await orchestrator.handle(prompt, session_id="cli"))
    finally:
        await orchestrator.close()
        memory.close()


async def run_service() -> None:
    if not settings.slack_enabled:
        log.error(
            "Slack is not configured. Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN, "
            "or use --once for a one-shot run."
        )
        sys.exit(1)

    from .slack_bridge import SlackBridge  # imported lazily so --once needs no slack deps

    settings.ensure_data_dir()
    memory = open_memory()
    orchestrator = Orchestrator(memory)
    await orchestrator.connect()

    bridge = SlackBridge(orchestrator)
    loop = MonitorLoop(orchestrator, bridge.post_alert)
    loop.start()

    reorder_job = _build_reorder_job(bridge)
    reorder_task = DailyTask("reorder-report", settings.reorder_report_time, reorder_job)
    reorder_task.start()

    log.info("Auria fleet online. Orchestrator=%s, Odoo=%s", settings.orchestrator_model, settings.odoo_enabled)
    try:
        await bridge.start()  # blocks, serving Slack events
    finally:
        await reorder_task.stop()
        await loop.stop()
        await orchestrator.close()
        memory.close()


def _build_reorder_job(bridge):
    """Return an async callback that builds the reorder report and posts the
    summary to Slack. Pure-Python compute (no LLM/token cost)."""
    async def _run() -> None:
        from tools.reorder_report import build_report, slack_summary

        log.info("Running daily reorder report…")
        rows, live = await asyncio.to_thread(build_report, "reorder_report.html")
        await bridge.post_alert(slack_summary(rows, live))
        log.info("Reorder report posted (%d materials, live=%s)", len(rows), live)

    return _run


def main() -> None:
    parser = argparse.ArgumentParser(description="Auria multi-agent fleet")
    parser.add_argument("--once", metavar="PROMPT", help="Run a single request and exit")
    args = parser.parse_args()

    if args.once:
        asyncio.run(run_once(args.once))
    else:
        asyncio.run(run_service())


if __name__ == "__main__":
    main()
