"""Environment-driven configuration for the Auria fleet."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    # Claude
    orchestrator_model: str = field(default_factory=lambda: _env("AURIA_ORCHESTRATOR_MODEL", "claude-opus-4-8"))
    worker_model: str = field(default_factory=lambda: _env("AURIA_WORKER_MODEL", "sonnet"))
    reviewer_model: str = field(default_factory=lambda: _env("AURIA_REVIEWER_MODEL", "opus"))
    effort: str = field(default_factory=lambda: _env("AURIA_EFFORT", "high"))

    # Memory. If AURIA_DB_URL (postgresql://...) is set, the fleet uses the
    # hosted Postgres/Supabase store; otherwise it falls back to the SQLite file.
    db_url: str = field(default_factory=lambda: _env("AURIA_DB_URL"))
    db_path: str = field(default_factory=lambda: _env("AURIA_DB_PATH", "./data/auria_memory.db"))

    # Slack
    slack_bot_token: str = field(default_factory=lambda: _env("SLACK_BOT_TOKEN"))
    slack_app_token: str = field(default_factory=lambda: _env("SLACK_APP_TOKEN"))
    slack_alert_channel: str = field(default_factory=lambda: _env("SLACK_ALERT_CHANNEL", "#auria-ops"))

    # Odoo
    odoo_url: str = field(default_factory=lambda: _env("ODOO_URL", "https://odoo.auria.global"))
    odoo_db: str = field(default_factory=lambda: _env("ODOO_DB", "auria"))
    odoo_username: str = field(default_factory=lambda: _env("ODOO_USERNAME"))
    odoo_api_key: str = field(default_factory=lambda: _env("ODOO_API_KEY"))

    # Loops
    loop_interval_seconds: int = field(
        default_factory=lambda: int(_env("AURIA_LOOP_INTERVAL_SECONDS", "3600") or "0")
    )

    @property
    def slack_enabled(self) -> bool:
        return bool(self.slack_bot_token and self.slack_app_token)

    @property
    def odoo_enabled(self) -> bool:
        return bool(self.odoo_url and self.odoo_db and self.odoo_username and self.odoo_api_key)

    def ensure_data_dir(self) -> None:
        Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
