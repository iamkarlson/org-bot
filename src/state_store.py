"""
GCS-backed state store.

Holds the three kinds of persistent state the bot owns:
- the search index (one gzipped JSON object),
- the raw update archive (every incoming Telegram update, verbatim, before processing),
- processed-update markers (dedup for Telegram webhook redeliveries).

All operations are synchronous; callers in async context should wrap them
in asyncio.to_thread. Every method is safe to call when the store is
disabled (no bucket configured) — reads return None/False, writes no-op.
"""

import gzip
import json
import logging
from typing import Optional, Tuple

from .config.state_settings import StateSettings

logger = logging.getLogger(__name__)


class StateStore:
    def __init__(self, settings: Optional[StateSettings] = None, client=None):
        """
        :param settings: state settings (loads from env if not provided)
        :param client: optional pre-built google.cloud.storage.Client (for tests)
        """
        self.settings = settings or StateSettings()
        self._client = client
        self._bucket = None

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    def _get_bucket(self):
        if self._bucket is None:
            if self._client is None:
                # Imported lazily so environments without the dependency or
                # credentials (tests, bots running without a state bucket)
                # never touch it.
                from google.cloud import storage

                self._client = storage.Client()
            self._bucket = self._client.bucket(self.settings.bucket)
        return self._bucket

    # --- Search index ---

    def read_index(self) -> Tuple[Optional[dict], Optional[int]]:
        """
        Read the search index object.

        :return: (index dict, blob generation) or (None, None) if absent
        """
        if not self.enabled:
            return None, None
        blob = self._get_bucket().blob(self.settings.search_index_object)
        try:
            data = blob.download_as_bytes()
        except Exception as e:
            if _is_not_found(e):
                logger.info("Search index object not found in bucket")
                return None, None
            raise
        index = json.loads(gzip.decompress(data).decode("utf-8"))
        return index, blob.generation

    def write_index(self, index: dict, generation: Optional[int]) -> bool:
        """
        Write the search index with a generation precondition.

        :param generation: generation read alongside the previous index,
                           or None/0 for "object must not exist yet"
        :return: True on success, False when a concurrent writer won the race
        """
        if not self.enabled:
            return False
        blob = self._get_bucket().blob(self.settings.search_index_object)
        data = gzip.compress(json.dumps(index, ensure_ascii=False).encode("utf-8"))
        try:
            blob.upload_from_string(
                data,
                content_type="application/gzip",
                if_generation_match=generation or 0,
            )
            return True
        except Exception as e:
            if _is_precondition_failed(e):
                # Concurrent invocation wrote an equivalent index first; benign.
                logger.info("Index write lost race to concurrent writer, skipping")
                return False
            raise

    # --- Raw update archive + dedup markers ---

    def archive_update(self, update_data: dict, update_id: int, date_str: str) -> None:
        """Persist a raw Telegram update before any processing. Overwrite-safe."""
        if not self.enabled:
            return
        path = f"{self.settings.raw_prefix}{date_str}/{update_id}.json"
        blob = self._get_bucket().blob(path)
        blob.upload_from_string(
            json.dumps(update_data, ensure_ascii=False),
            content_type="application/json",
        )

    def is_processed(self, update_id: int) -> bool:
        """True when this update was already fully processed (webhook redelivery)."""
        if not self.enabled:
            return False
        blob = self._get_bucket().blob(f"{self.settings.processed_prefix}{update_id}")
        return blob.exists()

    def mark_processed(self, update_id: int) -> None:
        """Record successful processing. Written after the action completes:
        a crash in between means a redelivery gets reprocessed — a rare
        duplicate is preferred over silent loss."""
        if not self.enabled:
            return
        blob = self._get_bucket().blob(f"{self.settings.processed_prefix}{update_id}")
        blob.upload_from_string(b"", content_type="application/octet-stream")


def _is_not_found(e: Exception) -> bool:
    return type(e).__name__ == "NotFound" or getattr(e, "code", None) == 404


def _is_precondition_failed(e: Exception) -> bool:
    return type(e).__name__ == "PreconditionFailed" or getattr(e, "code", None) == 412
