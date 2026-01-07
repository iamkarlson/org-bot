"""Bot settings using Pydantic."""

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
        """Parse comma-separated string of IDs into list of integers."""
        if isinstance(v, str):
            return [int(id.strip()) for id in v.split(",") if id.strip()]
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return v
        return v
