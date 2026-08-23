"""
Fuzzy matching over the corpus via rapidfuzz.

Candidates are lines, not whole files: each note contributes its title,
its tag string, and its body lines. Matching targets phone-style typos
(transpositions, fat fingers, partial words) with an edit-distance scorer.
Query terms are AND-ed; when AND yields fewer than AND_RELAX_THRESHOLD
hits the query relaxes to OR, with OR-only hits ranked below AND-complete
ones and marked as partial.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

from .corpus import Corpus, Note

logger = logging.getLogger(__name__)

# Additive location bonuses, not multipliers: a bonus prefers titles/tags over
# body at comparable match quality, while a multiplier would let a weak title
# match (70*3) crush a perfect body match (100*1).
BONUS_TITLE = 15.0
BONUS_TAGS = 10.0
BONUS_BODY = 0.0

SCORE_CUTOFF = 70.0
AND_RELAX_THRESHOLD = 3
MAX_HITS = 50


@dataclass
class Hit:
    note: Note
    score: float
    and_complete: bool
    snippet: str
    # Line number of the best-matching body line within the note text,
    # or None when the best match was the title or tags.
    best_line_no: Optional[int]


class _Candidates:
    """Flat candidate arrays for one corpus, cached by commit SHA."""

    def __init__(self, corpus: Corpus):
        self.lines: List[str] = []
        self.note_paths: List[str] = []
        self.weights: List[float] = []
        self.line_nos: List[Optional[int]] = []

        for note in corpus.notes.values():
            self._add(note.path, note.title, BONUS_TITLE, None)
            if note.tags:
                self._add(note.path, " ".join(note.tags), BONUS_TAGS, None)
            for i, line in enumerate(note.text.split("\n")):
                stripped = line.strip()
                if stripped:
                    self._add(note.path, stripped, BONUS_BODY, i)

    def _add(self, path: str, text: str, bonus: float, line_no: Optional[int]) -> None:
        self.lines.append(text.casefold())
        self.note_paths.append(path)
        self.weights.append(bonus)
        self.line_nos.append(line_no)


_candidates_cache: Tuple[Optional[str], Optional[_Candidates]] = (None, None)


def _get_candidates(corpus: Corpus) -> _Candidates:
    global _candidates_cache
    cached_sha, cached = _candidates_cache
    if cached_sha == corpus.commit_sha and cached is not None:
        return cached
    candidates = _Candidates(corpus)
    _candidates_cache = (corpus.commit_sha, candidates)
    return candidates


def search(corpus: Corpus, query: str) -> List[Hit]:
    """Rank notes against the query. Returns hits sorted best-first."""
    terms = [t for t in query.casefold().split() if t]
    if not terms:
        return []

    candidates = _get_candidates(corpus)

    # note path -> term index -> (weighted score, raw score, line_no)
    note_term_best: Dict[str, Dict[int, Tuple[float, float, Optional[int]]]] = {}

    for term_idx, term in enumerate(terms):
        # partial_ratio, not WRatio: terms are single words matched against
        # whole lines, and WRatio's length-ratio scaling caps short-term vs
        # long-line scores at 60 — below any usable cutoff. partial_ratio
        # scores the best window, independent of line length.
        matches = process.extract(
            term,
            candidates.lines,
            scorer=fuzz.partial_ratio,
            score_cutoff=SCORE_CUTOFF,
            limit=None,
        )
        for _, raw_score, cand_idx in matches:
            path = candidates.note_paths[cand_idx]
            weighted = raw_score + candidates.weights[cand_idx]
            per_term = note_term_best.setdefault(path, {})
            prev = per_term.get(term_idx)
            if prev is None or weighted > prev[0]:
                per_term[term_idx] = (
                    weighted,
                    raw_score,
                    candidates.line_nos[cand_idx],
                )

    and_hits: List[Hit] = []
    or_hits: List[Hit] = []
    for path, per_term in note_term_best.items():
        note = corpus.notes[path]
        score = sum(weighted for weighted, _, _ in per_term.values())
        and_complete = len(per_term) == len(terms)
        best_weighted, _, best_line_no = max(per_term.values(), key=lambda v: v[0])
        snippet = _snippet(note, best_line_no)
        hit = Hit(
            note=note,
            score=score,
            and_complete=and_complete,
            snippet=snippet,
            best_line_no=best_line_no,
        )
        (and_hits if and_complete else or_hits).append(hit)

    and_hits.sort(key=lambda h: (-h.score, h.note.path))

    if len(and_hits) >= AND_RELAX_THRESHOLD:
        return and_hits[:MAX_HITS]

    # Relaxed mode: too few AND-complete hits, let OR-only hits trail.
    or_hits.sort(key=lambda h: (-h.score, h.note.path))
    return (and_hits + or_hits)[:MAX_HITS]


def _snippet(note: Note, line_no: Optional[int], max_len: int = 120) -> str:
    if line_no is None:
        text = note.title
    else:
        lines = note.text.split("\n")
        text = lines[line_no].strip() if line_no < len(lines) else note.title
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text
