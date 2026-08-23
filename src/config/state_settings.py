"""State bucket settings (search index, raw update archive, dedup markers)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class StateSettings(BaseSettings):
    """GCS state bucket settings from environment."""

    model_config = SettingsConfigDict(
        env_prefix="STATE_",
        case_sensitive=False,
    )

    bucket: str = ""
    search_index_object: str = "index/index.json.gz"
    raw_prefix: str = "raw/"
    processed_prefix: str = "processed/"

    @property
    def enabled(self) -> bool:
        """State features (search, archive, dedup) are active only when a bucket is configured."""
        return bool(self.bucket)
