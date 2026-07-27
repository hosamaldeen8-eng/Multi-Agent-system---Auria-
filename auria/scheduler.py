"""Daily scheduled jobs — fire a callback once a day at a fixed wall-clock time.

Unlike the interval-based ``MonitorLoop``, a ``DailyTask`` runs at a specific
local time each day (e.g. 18:00). Used for the daily material reorder report.
Times are interpreted in the server's local timezone.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

log = logging.getLogger("auria.scheduler")


def _seconds_until(hour: int, minute: int) -> float:
    """Seconds from now until the next occurrence of HH:MM (local time)."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def parse_hhmm(value: str) -> tuple[int, int] | None:
    """Parse 'HH:MM' -> (hour, minute); None if empty/invalid (disables the task)."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        h, m = value.split(":")
        hour, minute = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


class DailyTask:
    def __init__(self, name: str, at: str, callback) -> None:
        self.name = name
        self._at = parse_hhmm(at)
        self._callback = callback  # async callable() -> None
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        assert self._at is not None
        hour, minute = self._at
        log.info("Daily task %r scheduled for %02d:%02d (local)", self.name, hour, minute)
        while True:
            delay = _seconds_until(hour, minute)
            await asyncio.sleep(delay)
            try:
                await self._callback()
            except Exception:  # noqa: BLE001 - a bad run must not kill the schedule
                log.exception("daily task %r failed", self.name)
            # Sleep past the target minute so we don't fire twice in the same minute.
            await asyncio.sleep(61)

    def start(self) -> None:
        if self._at is None:
            log.info("Daily task %r disabled (no valid time configured)", self.name)
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
