"""Bot configuration dataclass."""

import os
from dataclasses import dataclass


@dataclass
class BotConfig:
    """Core bot configuration from environment."""

    bot_token: str
    authorized_chat_ids: list[int]
    ignored_chat_ids: list[int]
    forward_unauthorized_to: int | None
    sentry_dsn: str

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables."""
        authorized_ids = [
            int(id) for id in os.environ["AUTHORIZED_CHAT_IDS"].split(",")
        ]
        ignored_ids = [
            int(id) for id in os.environ.get("IGNORED_CHAT_IDS", "").split(",") if id
        ]
        forward_to = os.environ.get("FORWARD_UNAUTHORIZED_TO")

        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            authorized_chat_ids=authorized_ids,
            ignored_chat_ids=ignored_ids,
            forward_unauthorized_to=int(forward_to) if forward_to else None,
            sentry_dsn=os.environ.get("SENTRY_DSN", ""),
        )
