"""
Search service: corpus freshness, query execution, Telegram rendering.

Corpus freshness per search: one GitHub API call for HEAD SHA. Same SHA →
use the warm in-memory corpus (or the GCS copy on a cold instance).
Moved SHA → incremental update (compare API), full rebuild as fallback,
result written back to the state bucket.
"""

import logging
import time
import urllib.parse
from typing import List, Optional, Tuple

from github import Auth, Github
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from ..state_store import StateStore
from . import callbacks
from .corpus import Corpus, full_build, incremental_update
from .matcher import Hit, search
from .subtree import chunk_text, extract_subtree

logger = logging.getLogger(__name__)

PAGE_SIZE = 5
BUTTON_TITLE_LEN = 30
INLINE_RESULTS_LIMIT = 10

LONG_QUERY_HINT = "Query too long for interactive buttons — refine it or repeat /search with fewer words."


class SearchService:
    def __init__(
        self,
        github_token: str,
        repo_name: str,
        state_store: StateStore,
        branch: str = "main",
    ):
        self.repo_name = repo_name
        self.branch = branch
        self.state_store = state_store
        self._github_token = github_token
        self._repo = None
        self._warm_corpus: Optional[Corpus] = None
        self._last_freshness_check: float = 0.0

    def _get_repo(self):
        if self._repo is None:
            client = Github(auth=Auth.Token(self._github_token))
            self._repo = client.get_repo(self.repo_name)
        return self._repo

    # --- Corpus lifecycle (sync, wrap in asyncio.to_thread from handlers) ---

    def ensure_corpus(self, max_age_seconds: float = 0.0) -> Corpus:
        """
        :param max_age_seconds: reuse the warm corpus without a GitHub freshness
            check when the last check is younger than this. Inline queries fire
            per keystroke — they pass a throttle; /search passes 0 (always check).
        """
        if (
            max_age_seconds > 0
            and self._warm_corpus is not None
            and time.time() - self._last_freshness_check < max_age_seconds
        ):
            return self._warm_corpus

        repo = self._get_repo()
        head_sha = repo.get_branch(self.branch).commit.sha
        self._last_freshness_check = time.time()

        if self._warm_corpus is not None and self._warm_corpus.commit_sha == head_sha:
            return self._warm_corpus

        index_json, generation = self.state_store.read_index()
        stored = Corpus.from_json(index_json) if index_json else None

        if stored is not None and stored.commit_sha == head_sha:
            self._warm_corpus = stored
            return stored

        updated = None
        if stored is not None:
            updated = incremental_update(repo, stored, head_sha)
        if updated is None:
            updated = full_build(repo, head_sha)

        self.state_store.write_index(updated.to_json(), generation)
        self._warm_corpus = updated
        return updated

    # --- Rendering ---

    def results_response(
        self, corpus: Corpus, query: str, page: int
    ) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        hits = search(corpus, query)
        if not hits:
            return (f'No hits for "{query}".', None)

        total_pages = (len(hits) + PAGE_SIZE - 1) // PAGE_SIZE
        page = max(0, min(page, total_pages - 1))
        page_hits = hits[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

        lines = [f'{len(hits)} hit(s) for "{query}"' + (f" — page {page + 1}/{total_pages}" if total_pages > 1 else "")]
        for offset, hit in enumerate(page_hits):
            rank = page * PAGE_SIZE + offset
            partial = "" if hit.and_complete else " (partial match)"
            lines.append(f"{rank + 1}. {hit.note.title} — {hit.note.path}{partial}")
            lines.append(f"   {hit.snippet}")
        text = "\n".join(lines)

        keyboard = self._results_keyboard(page_hits, page, total_pages, query)
        if keyboard is None:
            text += f"\n\n{LONG_QUERY_HINT}"
        return text, keyboard

    def _results_keyboard(
        self, page_hits: List[Hit], page: int, total_pages: int, query: str
    ) -> Optional[InlineKeyboardMarkup]:
        rows = []
        for offset, hit in enumerate(page_hits):
            rank = page * PAGE_SIZE + offset
            data = callbacks.encode_open(rank, 0, query)
            if data is None:
                return None
            title = hit.note.title
            if len(title) > BUTTON_TITLE_LEN:
                title = title[: BUTTON_TITLE_LEN - 1] + "…"
            rows.append([InlineKeyboardButton(f"{rank + 1}. {title}", callback_data=data)])

        nav = []
        if page > 0:
            data = callbacks.encode_page(page - 1, query)
            if data is None:
                return None
            nav.append(InlineKeyboardButton("◂ prev", callback_data=data))
        if page < total_pages - 1:
            data = callbacks.encode_page(page + 1, query)
            if data is None:
                return None
            nav.append(InlineKeyboardButton("next ▸", callback_data=data))
        if nav:
            rows.append(nav)

        return InlineKeyboardMarkup(rows)

    def open_response(
        self, corpus: Corpus, query: str, rank: int, chunk: int
    ) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """Note view for a search hit. Rendered into the SAME message as the
        results (single-message navigation): chunk arrows edit in place, the
        back button re-renders the results page this hit came from."""
        hits = search(corpus, query)
        if rank >= len(hits):
            return ("That result is gone — the notes changed since the search. Run /search again.", None)

        hit = hits[rank]
        content = extract_subtree(hit.note.text, hit.best_line_no)
        chunks = chunk_text(content)
        chunk = max(0, min(chunk, len(chunks) - 1))

        header = f"{hit.note.title} — {hit.note.path}"
        if len(chunks) > 1:
            header += f" [{chunk + 1}/{len(chunks)}]"
        text = f"{header}\n\n{chunks[chunk]}"

        rows = []
        chunk_nav = []
        if chunk > 0:
            data = callbacks.encode_open(rank, chunk - 1, query)
            if data is not None:
                chunk_nav.append(InlineKeyboardButton("◂", callback_data=data))
        if chunk < len(chunks) - 1:
            data = callbacks.encode_open(rank, chunk + 1, query)
            if data is not None:
                chunk_nav.append(InlineKeyboardButton("▸ more", callback_data=data))
        if chunk_nav:
            rows.append(chunk_nav)

        bottom = []
        back = callbacks.encode_page(rank // PAGE_SIZE, query)
        if back is not None:
            bottom.append(InlineKeyboardButton("↩ results", callback_data=back))
        bottom.append(
            InlineKeyboardButton("open on GitHub", url=self._github_url(hit.note.path))
        )
        rows.append(bottom)
        return text, InlineKeyboardMarkup(rows)

    def open_by_path_response(
        self, corpus: Corpus, path: str, chunk: int
    ) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """Open a note by path (inline-mode /open flow): whole file, chunked."""
        note = corpus.notes.get(path)
        if note is None:
            return (f"No note at {path} — it may have moved. Try /search.", None)

        chunks = chunk_text(note.text)
        chunk = max(0, min(chunk, len(chunks) - 1))

        header = f"{note.title} — {note.path}"
        if len(chunks) > 1:
            header += f" [{chunk + 1}/{len(chunks)}]"
        text = f"{header}\n\n{chunks[chunk]}"

        rows = []
        chunk_nav = []
        if chunk > 0:
            data = callbacks.encode_file(chunk - 1, path)
            if data is not None:
                chunk_nav.append(InlineKeyboardButton("◂", callback_data=data))
        if chunk < len(chunks) - 1:
            data = callbacks.encode_file(chunk + 1, path)
            if data is not None:
                chunk_nav.append(InlineKeyboardButton("▸ more", callback_data=data))
            else:
                # Path too long for the payload — GitHub link carries the rest.
                text += "\n\n(continued — open on GitHub for the rest)"
        if chunk_nav:
            rows.append(chunk_nav)
        rows.append(
            [InlineKeyboardButton("open on GitHub", url=self._github_url(note.path))]
        )
        return text, InlineKeyboardMarkup(rows)

    def inline_results(self, corpus: Corpus, query: str) -> List[InlineQueryResultArticle]:
        """Type-ahead dropdown results. Selecting one sends '/open <path>' as the
        user's message — command-shaped, so it can never leak into journal capture."""
        hits = search(corpus, query)[:INLINE_RESULTS_LIMIT]
        return [
            InlineQueryResultArticle(
                id=str(rank),
                title=hit.note.title,
                description=hit.snippet,
                input_message_content=InputTextMessageContent(f"/open {hit.note.path}"),
            )
            for rank, hit in enumerate(hits)
        ]

    def _github_url(self, path: str) -> str:
        quoted = urllib.parse.quote(path)
        return f"https://github.com/{self.repo_name}/blob/{self.branch}/{quoted}"
