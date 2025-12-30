"""GitHub integration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    """GitHub integration settings."""

    model_config = SettingsConfigDict(
        env_prefix="GITHUB_",
        case_sensitive=False,
    )

    token: str = ""
    repo: str = ""
