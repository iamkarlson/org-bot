"""Bot settings using Pydantic."""

import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Core bot settings from environment."""

    model_config = SettingsConfigDict(
        env_prefix="BOT_",
        case_sensitive=False,
    )

    token: str
    authorized_chat_ids: list[int] = []
    ignored_chat_ids: list[int] = []
    forward_unauthorized_to: int | None = None
    sentry_dsn: str = ""

    @field_validator("authorized_chat_ids", "ignored_chat_ids", mode="before")
    @classmethod
    def parse_comma_separated_ids(cls, v):
        """Parse comma-separated string of IDs into list of integers.

        Handles:
        - Comma-separated strings: '107262564,-1001672520725'
        - JSON arrays: '[107262564,-1001672520725]'
        - Single integers: 123456
        - Already parsed lists: [123456, 789012]
        """
        if isinstance(v, str):
            # Try to parse as JSON first (for pydantic-settings compatibility)
            v = v.strip()
            if v.startswith('[') and v.endswith(']'):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [int(id) for id in parsed]
                except (json.JSONDecodeError, ValueError):
                    pass

            # Fall back to comma-separated parsing
            return [int(id.strip()) for id in v.split(",") if id.strip()]
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return [int(id) for id in v]
        return v
