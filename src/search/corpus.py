"""
Corpus snapshot of the org repo: what the search runs against.

The corpus is a JSON document (path, title, tags, full text per note)
stamped with the repo HEAD SHA it was built from. It lives gzipped in the
state bucket and is refreshed incrementally: when HEAD moves, only the
org files changed between the old and new SHA are re-fetched (GitHub
compare API), so the work is proportional to changes, not repo size.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CORPUS_VERSION = 1

# The compare API caps the file list; past that the diff is not trustworthy.
COMPARE_FILES_LIMIT = 300

_TITLE_RE = re.compile(r"^#\+title:\s*(.+)\s*$", re.IGNORECASE | re.MULTILINE)
_FILETAGS_RE = re.compile(r"^#\+filetags:\s*(.+)\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass
class Note:
    path: str
    title: str
    tags: List[str]
    text: str


@dataclass
class Corpus:
    commit_sha: str
    notes: Dict[str, Note] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "version": CORPUS_VERSION,
            "commit_sha": self.commit_sha,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "notes": [
                {"path": n.path, "title": n.title, "tags": n.tags, "text": n.text}
                for n in self.notes.values()
            ],
        }

    @classmethod
    def from_json(cls, data: dict) -> "Corpus":
        corpus = cls(commit_sha=data["commit_sha"])
        for item in data.get("notes", []):
            note = Note(
                path=item["path"],
                title=item["title"],
                tags=item.get("tags", []),
                text=item.get("text", ""),
            )
            corpus.notes[note.path] = note
        return corpus


def parse_note(path: str, text: str) -> Note:
    """Build a Note from raw org file content."""
    title_match = _TITLE_RE.search(text)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = path.rsplit("/", 1)[-1].removesuffix(".org")

    tags: List[str] = []
    tags_match = _FILETAGS_RE.search(text)
    if tags_match:
        tags = [t for t in tags_match.group(1).strip().split(":") if t]

    return Note(path=path, title=title, tags=tags, text=text)


def full_build(repo, head_sha: str) -> Corpus:
    """Build the corpus from scratch via a recursive tree walk.

    Expensive (one blob fetch per org file) — used only when there is no
    prior corpus or the incremental path can't be trusted."""
    corpus = Corpus(commit_sha=head_sha)
    tree = repo.get_git_tree(head_sha, recursive=True)
    org_elements = [el for el in tree.tree if el.type == "blob" and el.path.endswith(".org")]
    logger.info(f"Full corpus rebuild: {len(org_elements)} org files at {head_sha[:9]}")
    for el in org_elements:
        blob = repo.get_git_blob(el.sha)
        import base64

        text = base64.b64decode(blob.content).decode("utf-8", errors="replace")
        corpus.notes[el.path] = parse_note(el.path, text)
    return corpus


def incremental_update(repo, corpus: Corpus, head_sha: str) -> Optional[Corpus]:
    """Patch an existing corpus from old SHA to head_sha via the compare API.

    :return: updated Corpus, or None when the diff can't be applied
             (force push, too many files) and a full rebuild is needed.
    """
    try:
        comparison = repo.compare(corpus.commit_sha, head_sha)
    except Exception as e:
        logger.warning(f"Compare {corpus.commit_sha[:9]}..{head_sha[:9]} failed: {e}")
        return None

    files = list(comparison.files)
    if len(files) >= COMPARE_FILES_LIMIT:
        logger.warning(f"Compare returned {len(files)} files, falling back to full rebuild")
        return None

    updated = Corpus(commit_sha=head_sha, notes=dict(corpus.notes))
    changed = 0
    for f in files:
        if f.status == "removed":
            if f.filename.endswith(".org"):
                updated.notes.pop(f.filename, None)
                changed += 1
            continue
        if f.status == "renamed" and f.previous_filename:
            updated.notes.pop(f.previous_filename, None)
        if not f.filename.endswith(".org"):
            continue
        contents = repo.get_contents(f.filename, ref=head_sha)
        text = contents.decoded_content.decode("utf-8", errors="replace")
        updated.notes[f.filename] = parse_note(f.filename, text)
        changed += 1

    logger.info(
        f"Corpus updated {corpus.commit_sha[:9]}..{head_sha[:9]}: {changed} org file(s) changed"
    )
    return updated
