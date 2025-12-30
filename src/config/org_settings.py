"""Org-mode repository settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class OrgSettings(BaseSettings):
    """Org-mode repository settings."""

    model_config = SettingsConfigDict(
        env_prefix="ORG_",
        case_sensitive=False,
    )

    journal_file: str = "journal.md"
    todo_file: str = "todo.org"
