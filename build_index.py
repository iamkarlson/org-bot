"""
Bootstrap the search index from a local clone of the org repo.

Builds the corpus JSON from the working tree (so the first deploy doesn't
pay a ~1000-blob GitHub API walk) and uploads it gzipped to the state
bucket. The bot keeps it fresh incrementally from there.

Usage:
    uv run python build_index.py --repo-dir ~/path/to/org-repo --bucket <state-bucket-name>
"""

import gzip
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from defopt import run

from src.search.corpus import CORPUS_VERSION, parse_note

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)

logger = logging.getLogger(__name__)


def build_index(
    *,
    repo_dir: str,
    bucket: str = "",
    output: str = "",
    index_object: str = "index/index.json.gz",
):
    """
    Build the search index from a local clone; upload it to GCS and/or write it locally.

    With --output and no --bucket, the gzipped index is only written to the local
    path — upload it separately (e.g. `gcloud storage cp <output> gs://<bucket>/<object>`),
    useful when application-default credentials belong to a different account.

    :param repo_dir: path to a local clone of the org repo (clean checkout of the branch the bot reads)
    :param bucket: state bucket name (omit to skip the upload)
    :param output: local path to also write the gzipped index to
    :param index_object: object path for the index inside the bucket
    """
    if not bucket and not output:
        raise SystemExit("Provide --bucket, --output, or both")
    repo_path = Path(repo_dir).expanduser()

    head_sha = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    tracked = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files", "*.org"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    notes = []
    for rel_path in tracked:
        text = (repo_path / rel_path).read_text(encoding="utf-8", errors="replace")
        note = parse_note(rel_path, text)
        notes.append(
            {"path": note.path, "title": note.title, "tags": note.tags, "text": note.text}
        )

    index = {
        "version": CORPUS_VERSION,
        "commit_sha": head_sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    data = gzip.compress(json.dumps(index, ensure_ascii=False).encode("utf-8"))
    logger.info(f"Built index: {len(notes)} notes at {head_sha[:9]}, {len(data)} bytes gzipped")

    if output:
        Path(output).expanduser().write_bytes(data)
        logger.info(f"Written to {output}")

    if bucket:
        from google.cloud import storage

        client = storage.Client()
        blob = client.bucket(bucket).blob(index_object)
        blob.upload_from_string(data, content_type="application/gzip")
        logger.info(f"Uploaded to gs://{bucket}/{index_object}")


if __name__ == "__main__":
    run(build_index)
