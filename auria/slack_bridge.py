"""Slack bridge — monitoring and two-way communication for the fleet.

Runs a Slack app in Socket Mode (no public URL required). Humans talk to the
fleet by @mentioning the bot in a channel or DMing it; the orchestrator's reply
is posted back in-thread. The fleet also posts proactive monitoring alerts to a
configured channel via ``post_alert``.
"""

from __future__ import annotations

import logging

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from .orchestrator import Orchestrator
from .settings import settings

log = logging.getLogger("auria.slack")

_MENTION_STRIP = "<@"


def _clean(text: str, bot_user_id: str | None) -> str:
    """Remove the bot mention token from an incoming message."""
    if bot_user_id:
        text = text.replace(f"<@{bot_user_id}>", "")
    return text.strip()


class SlackBridge:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator
        self.app = AsyncApp(token=settings.slack_bot_token)
        self._bot_user_id: str | None = None
        self._register()

    def _register(self) -> None:
        @self.app.event("app_mention")
        async def on_mention(event, say):  # type: ignore[no-untyped-def]
            await self._respond(event, say)

        @self.app.event("message")
        async def on_message(event, say):  # type: ignore[no-untyped-def]
            # Only handle direct messages here (channel_type == "im");
            # channel mentions are handled by app_mention above.
            if event.get("channel_type") != "im" or event.get("bot_id"):
                return
            await self._respond(event, say)

    async def _respond(self, event: dict, say) -> None:  # type: ignore[no-untyped-def]
        text = _clean(event.get("text", ""), self._bot_user_id)
        if not text:
            return
        thread_ts = event.get("thread_ts") or event.get("ts")
        channel = event.get("channel")
        user = event.get("user", "someone")
        log.info("MENTION-RECEIVED channel=%s user=%s text=%r", channel, user, text[:120])
        await say(text=":gear: Working on it…", thread_ts=thread_ts)
        try:
            reply = await self.orchestrator.handle(
                f"[Slack message from {user}] {text}", session_id=f"slack:{channel}"
            )
            log.info("MENTION-REPLIED channel=%s chars=%d", channel, len(reply))
        except Exception as exc:  # noqa: BLE001 - always report failures to the user
            log.exception("orchestrator failed")
            reply = f":warning: The fleet hit an error: `{type(exc).__name__}: {exc}`"
        await say(text=reply[:39000], thread_ts=thread_ts)

    async def post_alert(self, text: str, channel: str | None = None) -> None:
        """Post a proactive monitoring alert to the alert channel."""
        await self.app.client.chat_postMessage(
            channel=channel or settings.slack_alert_channel, text=text
        )

    async def start(self) -> None:
        auth = await self.app.client.auth_test()
        self._bot_user_id = auth.get("user_id")
        log.info("Slack bridge connected as %s", auth.get("user"))
        handler = AsyncSocketModeHandler(self.app, settings.slack_app_token)
        await handler.start_async()
