"""Tests for the Pebble Index 01 ring webhook: hotword routing, token check, bot write."""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("GITHUB_TOKEN", "test_token")
os.environ.setdefault("GITHUB_REPO", "test/repo")
os.environ.setdefault("BOT_TOKEN", "test_bot_token")
os.environ.setdefault("BOT_SENTRY_DSN", "")

from src.bot import OrgBot
from src.config import BotSettings, GitHubSettings, OrgSettings
from src.pebble import pebble_org_entry, pebble_token_ok

RECORDED_AT = 1760000000000


@pytest.mark.parametrize(
    "transcription, kind, first_line",
    [
        ("Todo, buy milk", "todo", "** TODO buy milk"),
        ("To-do: buy milk", "todo", "** TODO buy milk"),
        ("to do buy milk.", "todo", "** TODO buy milk."),
        ("Remind me to call mom tomorrow", "todo", "** TODO Remind me to call mom tomorrow"),
        ("Todo", "todo", "** TODO Todo"),
        ("Today I fixed the bike", "journal", "* Entry: ["),
        ("just a thought", "journal", "* Entry: ["),
    ],
)
def test_hotword_routing(transcription, kind, first_line):
    result_kind, org_text = pebble_org_entry(transcription, RECORDED_AT)
    assert result_kind == kind
    assert org_text.splitlines()[0].startswith(first_line)
    assert "pebble-ring" in org_text


def test_todo_has_created_at_line():
    _, org_text = pebble_org_entry("todo buy milk", RECORDED_AT)
    assert org_text.splitlines()[1].startswith("Created at: [")
    assert org_text.endswith("] from pebble-ring")


def test_journal_keeps_text_on_second_line():
    _, org_text = pebble_org_entry("just a thought", RECORDED_AT)
    assert org_text.splitlines()[1] == "just a thought"


@pytest.mark.parametrize("transcription", ["", "   ", None])
def test_empty_transcription_is_skipped(transcription):
    assert pebble_org_entry(transcription, RECORDED_AT) is None


@pytest.mark.parametrize(
    "header, expected, ok",
    [
        ("Bearer secret", "secret", True),
        ("Bearer wrong", "secret", False),
        ("secret", "secret", False),
        (None, "secret", False),
        ("Bearer ", "", False),
        (None, "", False),
    ],
)
def test_token_check(header, expected, ok):
    assert pebble_token_ok(header, expected) is ok


@pytest.fixture
def org_bot():
    mock_client = MagicMock()
    with patch("src.actions.base_post_to_org_file.Github", return_value=mock_client):
        bot = OrgBot(
            bot_settings=BotSettings(token="test_bot_token", sentry_dsn=""),
            github_settings=GitHubSettings(token="test_token", repo="test/repo"),
            org_settings=OrgSettings(journal_file="journal.org", todo_file="todo.org"),
        )
    bot.actions["todo"].function.__self__.org_api = MagicMock()
    return bot


@pytest.mark.parametrize(
    "transcription, kind, file_path",
    [
        ("remind me to water plants", "todo", "todo.org"),
        ("nice weather today", "journal", "journal.org"),
    ],
)
def test_handle_pebble_writes_to_right_file(org_bot, transcription, kind, file_path):
    assert org_bot.handle_pebble(transcription, RECORDED_AT) == kind
    org_api = org_bot.actions["todo"].function.__self__.org_api
    org_api.append_text_to_file.assert_called_once()
    assert org_api.append_text_to_file.call_args.args[0] == file_path


def test_handle_pebble_skips_empty(org_bot):
    assert org_bot.handle_pebble("", RECORDED_AT) is None
    org_bot.actions["todo"].function.__self__.org_api.append_text_to_file.assert_not_called()
