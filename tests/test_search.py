"""Unit tests for the search feature: matcher, callbacks, subtree, corpus, state store.

All fixtures are synthetic — no real notes anywhere near tests.
"""

import gzip
import json

import pytest

from src.search import callbacks
from src.search.corpus import Corpus, Note, incremental_update, parse_note
from src.search.matcher import search
from src.search.subtree import chunk_text, extract_subtree
from src.state_store import StateStore
from src.config.state_settings import StateSettings


# --- Synthetic corpus ---


def make_corpus():
    corpus = Corpus(commit_sha="abc123def")
    notes = [
        Note(
            path="area/boiler.org",
            title="Boiler maintenance",
            tags=["home"],
            text="#+title: Boiler maintenance\n#+filetags: :home:\n\n* Yearly checkup\nPressure should stay above 1.5 bar.\n* Vendor contacts\nCall the installer first.",
        ),
        Note(
            path="journal.org",
            title="journal",
            tags=[],
            text="#+title: journal\n\n* Entry: boiler pressure dropped\nChecked manometer, 1.2 bar, topped up.\n* Entry: bought coffee beans\nNice ones.",
        ),
        Note(
            path="projects/synth.org",
            title="Synthesizer build",
            tags=["music"],
            text="#+title: Synthesizer build\n#+filetags: :music:\n\n* Parts list\nOscillator chips ordered.",
        ),
    ]
    for note in notes:
        corpus.notes[note.path] = note
    return corpus


# --- Matcher ---


class TestMatcher:
    def test_title_hit_outranks_body_hit(self):
        hits = search(make_corpus(), "boiler")
        assert hits[0].note.path == "area/boiler.org"
        assert any(h.note.path == "journal.org" for h in hits)

    def test_typo_still_matches(self):
        hits = search(make_corpus(), "boilr")
        assert hits, "typo query must still find the note"
        assert hits[0].note.path == "area/boiler.org"

    def test_and_terms_both_required(self):
        hits = search(make_corpus(), "boiler pressure")
        and_hits = [h for h in hits if h.and_complete]
        assert and_hits
        for hit in and_hits:
            assert hit.note.path in ("area/boiler.org", "journal.org")

    def test_or_relaxation_marks_partial(self):
        # "boiler oscillator" never AND-matches a single note → OR relaxation kicks in.
        hits = search(make_corpus(), "boiler oscillator")
        assert hits
        partial = [h for h in hits if not h.and_complete]
        assert partial, "OR relaxation should surface partial hits"

    def test_no_hits_for_garbage(self):
        assert search(make_corpus(), "xyzzyplugh") == []

    def test_empty_query(self):
        assert search(make_corpus(), "   ") == []

    def test_snippet_is_matching_line(self):
        hits = search(make_corpus(), "manometer")
        assert hits
        assert "manometer" in hits[0].snippet.casefold()


# --- Callback encoding ---


class TestCallbacks:
    def test_page_roundtrip(self):
        data = callbacks.encode_page(2, "boiler pressure")
        decoded = callbacks.decode(data)
        assert decoded.op == callbacks.OP_PAGE
        assert decoded.page == 2
        assert decoded.query == "boiler pressure"

    def test_open_roundtrip(self):
        data = callbacks.encode_open(4, 1, "boiler")
        decoded = callbacks.decode(data)
        assert decoded.op == callbacks.OP_OPEN
        assert decoded.rank == 4
        assert decoded.chunk == 1
        assert decoded.query == "boiler"

    def test_query_with_pipe_survives(self):
        data = callbacks.encode_open(0, 0, "a|b c")
        decoded = callbacks.decode(data)
        assert decoded.query == "a|b c"

    def test_oversize_query_returns_none(self):
        assert callbacks.encode_page(0, "ы" * 40) is None

    def test_decode_garbage(self):
        assert callbacks.decode("") is None
        assert callbacks.decode("v2|p|0|x") is None
        assert callbacks.decode("v1|p|notanint|x") is None
        assert callbacks.decode("random junk") is None

    def test_file_roundtrip(self):
        data = callbacks.encode_file(2, "daily/2026-08/17 - Monday.org")
        decoded = callbacks.decode(data)
        assert decoded.op == callbacks.OP_FILE
        assert decoded.chunk == 2
        assert decoded.path == "daily/2026-08/17 - Monday.org"

    def test_file_long_path_returns_none(self):
        assert callbacks.encode_file(0, "resources/external/" + "x" * 60 + ".org") is None


# --- Subtree extraction + chunking ---


class TestSubtree:
    TEXT = "#+title: t\npreamble line\n* One\nbody one\n** One sub\nsub body\n* Two\nbody two"

    def test_match_in_subtree(self):
        lines = self.TEXT.split("\n")
        line_no = lines.index("sub body")
        subtree = extract_subtree(self.TEXT, line_no)
        assert subtree == "** One sub\nsub body"

    def test_subtree_ends_at_same_level_heading(self):
        lines = self.TEXT.split("\n")
        line_no = lines.index("body one")
        subtree = extract_subtree(self.TEXT, line_no)
        assert subtree == "* One\nbody one\n** One sub\nsub body"

    def test_preamble_match_returns_whole_file(self):
        lines = self.TEXT.split("\n")
        line_no = lines.index("preamble line")
        assert extract_subtree(self.TEXT, line_no) == self.TEXT

    def test_title_match_returns_whole_file(self):
        assert extract_subtree(self.TEXT, None) == self.TEXT

    def test_chunking_respects_size(self):
        text = "\n".join(f"line {i} " + "x" * 50 for i in range(300))
        chunks = chunk_text(text, size=1000)
        assert all(len(c) <= 1000 for c in chunks)
        assert "".join(c.replace("\n", "") for c in chunks).count("line 299") == 1


# --- Inline mode + open-by-path (service-level, no network) ---


class TestInlineAndOpen:
    def _service(self):
        from src.search.service import SearchService
        from src.config.state_settings import StateSettings

        return SearchService(
            github_token="t",
            repo_name="user/repo",
            state_store=StateStore(settings=StateSettings(bucket="")),
        )

    def test_inline_results_send_open_command(self):
        service = self._service()
        results = service.inline_results(make_corpus(), "boiler")
        assert results
        top = results[0]
        assert top.title == "Boiler maintenance"
        assert top.input_message_content.message_text == "/open area/boiler.org"

    def test_inline_results_empty_for_garbage(self):
        service = self._service()
        assert service.inline_results(make_corpus(), "xyzzyplugh") == []

    def test_open_by_path_returns_content_and_github_button(self):
        service = self._service()
        text, keyboard = service.open_by_path_response(
            make_corpus(), "area/boiler.org", chunk=0
        )
        assert "Boiler maintenance — area/boiler.org" in text
        assert "Yearly checkup" in text
        urls = [b.url for row in keyboard.inline_keyboard for b in row if b.url]
        assert urls == ["https://github.com/user/repo/blob/main/area/boiler.org"]

    def test_open_by_path_unknown_path(self):
        service = self._service()
        text, keyboard = service.open_by_path_response(make_corpus(), "nope.org", 0)
        assert keyboard is None
        assert "No note at" in text

    def test_open_response_has_back_to_results_button(self):
        service = self._service()
        corpus = make_corpus()
        text, keyboard = service.open_response(corpus, "boiler", rank=0, chunk=0)
        assert "Boiler maintenance" in text
        datas = [b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data]
        back = [d for d in datas if d.startswith("v1|p|")]
        assert back == ["v1|p|0|boiler"], "back button must return to the results page the hit came from"

    def test_open_response_chunk_navigation(self):
        service = self._service()
        corpus = Corpus(commit_sha="x")
        long_note = Note(
            path="big.org",
            title="Big note",
            tags=[],
            text="#+title: Big note\n* Heading\n" + "\n".join(f"boiler line {i} " + "x" * 80 for i in range(200)),
        )
        corpus.notes[long_note.path] = long_note
        # chunk 1 of a multi-chunk note: both directions present
        text, keyboard = service.open_response(corpus, "boiler", rank=0, chunk=1)
        labels = [b.text for row in keyboard.inline_keyboard for b in row]
        assert "◂" in labels and "▸ more" in labels and "↩ results" in labels


# --- Corpus parsing + incremental updates ---


class TestCorpus:
    def test_parse_note_title_and_tags(self):
        note = parse_note("a/b.org", "#+title: My Note\n#+filetags: :home:infra:\nbody")
        assert note.title == "My Note"
        assert note.tags == ["home", "infra"]

    def test_parse_note_fallback_title(self):
        note = parse_note("a/some_note.org", "just body, no metadata")
        assert note.title == "some_note"
        assert note.tags == []

    def test_incremental_update_applies_changes(self):
        corpus = make_corpus()

        class FakeFile:
            def __init__(self, filename, status, previous_filename=None):
                self.filename = filename
                self.status = status
                self.previous_filename = previous_filename

        class FakeContents:
            decoded_content = b"#+title: New note\nfresh body"

        class FakeRepo:
            def compare(self, base, head):
                class Comparison:
                    files = [
                        FakeFile("area/boiler.org", "removed"),
                        FakeFile("new/note.org", "added"),
                        FakeFile("pics/photo.jpg", "added"),
                    ]

                return Comparison()

            def get_contents(self, path, ref):
                assert path == "new/note.org"
                return FakeContents()

        updated = incremental_update(FakeRepo(), corpus, "newsha456")
        assert updated.commit_sha == "newsha456"
        assert "area/boiler.org" not in updated.notes
        assert updated.notes["new/note.org"].title == "New note"
        assert "pics/photo.jpg" not in updated.notes
        # Original corpus untouched
        assert "area/boiler.org" in corpus.notes


# --- State store (fake GCS client) ---


class FakeBlob:
    def __init__(self, store, path):
        self.store = store
        self.path = path
        self.generation = None

    def exists(self):
        return self.path in self.store

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        if if_generation_match == 0 and self.path in self.store:
            raise FakePreconditionFailed()
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.store[self.path] = data

    def download_as_bytes(self):
        if self.path not in self.store:
            raise FakeNotFound()
        self.generation = 1
        return self.store[self.path]


class FakeNotFound(Exception):
    code = 404


class FakePreconditionFailed(Exception):
    code = 412


class FakeBucket:
    def __init__(self, store):
        self.store = store

    def blob(self, path):
        return FakeBlob(self.store, path)


class FakeClient:
    def __init__(self):
        self.store = {}

    def bucket(self, name):
        return FakeBucket(self.store)


def make_store():
    settings = StateSettings(bucket="fake-bucket")
    return StateStore(settings=settings, client=FakeClient())


class TestStateStore:
    def test_disabled_store_noops(self):
        store = StateStore(settings=StateSettings(bucket=""))
        assert store.enabled is False
        assert store.read_index() == (None, None)
        assert store.is_processed(1) is False
        store.archive_update({"a": 1}, 1, "2026-08-19")  # must not raise
        store.mark_processed(1)  # must not raise

    def test_dedup_roundtrip(self):
        store = make_store()
        assert store.is_processed(42) is False
        store.mark_processed(42)
        assert store.is_processed(42) is True

    def test_archive_writes_raw_json(self):
        store = make_store()
        store.archive_update({"update_id": 7, "text": "hi"}, 7, "2026-08-19")
        raw = store._client.store["raw/2026-08-19/7.json"]
        assert json.loads(raw) == {"update_id": 7, "text": "hi"}

    def test_index_roundtrip(self):
        store = make_store()
        index = {"version": 1, "commit_sha": "abc", "notes": []}
        assert store.write_index(index, None) is True
        loaded, generation = store.read_index()
        assert loaded == index

    def test_index_missing(self):
        store = make_store()
        assert store.read_index() == (None, None)

    def test_index_write_race_lost_is_benign(self):
        store = make_store()
        store.write_index({"commit_sha": "a", "notes": []}, None)
        # Second write with stale "does not exist" precondition loses quietly.
        assert store.write_index({"commit_sha": "b", "notes": []}, None) is False
