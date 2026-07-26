"""Scheduled monitoring loops — the fleet's autonomous heartbeat.

On a fixed interval, the orchestrator runs a set of monitoring prompts (e.g.
scan Odoo for problems), and anything worth a human's attention is posted to
Slack. This is the "loop system" that keeps the fleet running alongside the
business without someone having to ask.

Add or edit monitors in ``MONITORS`` below.
"""

from __future__ import annotations

import asyncio
import logging

from .orchestrator import Orchestrator
from .settings import settings

log = logging.getLogger("auria.loops")

# Each monitor is a standing instruction the orchestrator runs every tick.
# Keep them read-only and phrased so a boring result stays quiet.
MONITORS: list[dict[str, str]] = [
    {
        "name": "odoo-manufacturing-health",
        "prompt": (
            "Run a routine Odoo operations check via the odoo-ops agent: look for "
            "manufacturing orders that are late or blocked, and stock that is below "
            "reorder level. Summarize only genuine problems. If everything is normal, "
            "reply with exactly 'ALL CLEAR' and nothing else."
        ),
    },
]


class MonitorLoop:
    def __init__(self, orchestrator: Orchestrator, alert) -> None:
        self.orchestrator = orchestrator
        self.alert = alert  # async callable(text) -> None
        self._task: asyncio.Task | None = None

    async def _tick(self) -> None:
        for monitor in MONITORS:
            try:
                result = await self.orchestrator.handle(
                    monitor["prompt"], session_id=f"loop:{monitor['name']}"
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("monitor %s failed", monitor["name"])
                await self.alert(f":warning: Monitor `{monitor['name']}` errored: {exc}")
                continue
            if result and "ALL CLEAR" not in result.upper():
                await self.alert(f":rotating_light: *{monitor['name']}*\n{result}")
            else:
                log.info("monitor %s: all clear", monitor["name"])

    async def _run(self) -> None:
        interval = settings.loop_interval_seconds
        log.info("Monitor loop started (every %ss)", interval)
        while True:
            await asyncio.sleep(interval)
            await self._tick()

    def start(self) -> None:
        if settings.loop_interval_seconds <= 0:
            log.info("Monitor loop disabled (AURIA_LOOP_INTERVAL_SECONDS=0)")
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
