"""
Unit tests for the OrgBot class.

Tests cover:
- Initialization with custom configs
- Action determination logic (reply vs todo vs journal)
- MarkdownV2 escaping
- Command routing
- Unauthorized access handling
"""

import os
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock

# Set environment variables before importing src modules
os.environ.setdefault("GITHUB_TOKEN", "test_token")
os.environ.setdefault("GITHUB_REPO", "test/repo")
os.environ.setdefault("ORG_JOURNAL_FILE", "journal.org")
os.environ.setdefault("BOT_TOKEN", "test_bot_token")
os.environ.setdefault("BOT_AUTHORIZED_CHAT_IDS", "1234567890")
os.environ.setdefault("BOT_SENTRY_DSN", "")

from src.bot import OrgBot
from src.config import BotSettings, GitHubSettings, OrgSettings


@pytest.fixture
def test_bot_settings():
    """Create a test bot settings."""
    return BotSettings(
        token="test_bot_token",
        authorized_chat_ids=[1234567890],
        ignored_chat_ids=[9999],
        forward_unauthorized_to=None,
        sentry_dsn="",
    )


@pytest.fixture
def test_github_settings():
    """Create a test GitHub settings."""
    return GitHubSettings(
        token="test_token",
        repo="test/repo",
    )


@pytest.fixture
def test_org_settings():
    """Create a test Org settings."""
    return OrgSettings(
        journal_file="journal.org",
        todo_file="todo.org",
    )


@pytest.fixture
def mock_github():
    """Mock GitHub client to avoid real API calls during initialization."""
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_contents = MagicMock()
    mock_contents.decoded_content = b"# Test content"
    mock_contents.sha = "test_sha"
    mock_repo.get_contents.return_value = mock_contents
    mock_client.get_repo.return_value = mock_repo
    return mock_client


@pytest.fixture
def org_bot(test_bot_settings, test_github_settings, test_org_settings, mock_github):
    """Create an OrgBot instance with test configurations."""
    with patch("src.actions.base_post_to_org_file.Github", return_value=mock_github):
        bot = OrgBot(
            bot_settings=test_bot_settings,
            github_settings=test_github_settings,
            org_settings=test_org_settings,
        )
    return bot


class TestOrgBotInitialization:
    """Test OrgBot initialization."""

    def test_init_with_configs(
        self, test_bot_settings, test_github_settings, test_org_settings, mock_github
    ):
        """Test initialization with provided configs."""
        with patch(
            "src.actions.base_post_to_org_file.Github", return_value=mock_github
        ):
            bot = OrgBot(
                bot_settings=test_bot_settings,
                github_settings=test_github_settings,
                org_settings=test_org_settings,
            )

        assert bot.bot_settings == test_bot_settings
        assert bot.github_settings == test_github_settings
        assert bot.org_settings == test_org_settings
        assert len(bot.commands) == 3  # /start, /webhook, /info
        assert len(bot.actions) == 3  # journal, todo, reply
        assert bot.default_action_key == "journal"

    def test_init_from_env(self, mock_github):
        """Test initialization loading configs from environment."""
        with patch(
            "src.actions.base_post_to_org_file.Github", return_value=mock_github
        ):
            # Config will be loaded from environment variables set in conftest or test setup
            bot = OrgBot()

        assert bot.bot_settings is not None
        assert bot.github_settings is not None
        assert bot.org_settings is not None


class TestActionDetermination:
    """Test the _determine_action method."""

    def test_determine_action_reply(self, org_bot):
        """Test that reply messages are identified correctly."""
        message = Mock()
        message.reply_to_message = Mock()  # Has a reply
        message.text = "This is a reply"

        action_key = org_bot._determine_action(message, "This is a reply")
        assert action_key == "reply"

    def test_determine_action_todo(self, org_bot):
        """Test that TODO messages are identified correctly."""
        message = Mock()
        message.reply_to_message = None  # Not a reply

        action_key = org_bot._determine_action(message, "todo write tests")
        assert action_key == "todo"

        action_key = org_bot._determine_action(message, "TODO write tests")
        assert action_key == "todo"

        action_key = org_bot._determine_action(message, "ToDo write tests")
        assert action_key == "todo"

    def test_determine_action_journal_default(self, org_bot):
        """Test that non-reply, non-todo messages default to journal."""
        message = Mock()
        message.reply_to_message = None

        action_key = org_bot._determine_action(message, "Regular journal entry")
        assert action_key == "journal"

        action_key = org_bot._determine_action(message, "Something with todo in middle")
        assert action_key == "journal"  # Not starting with "todo "


class TestMarkdownEscaping:
    """Test the _escape_markdown_v2 static method."""

    def test_escape_basic_chars(self, org_bot):
        """Test escaping of basic special characters."""
        text = "Hello_World*Test"
        escaped = org_bot._escape_markdown_v2(text)
        assert escaped == r"Hello\_World\*Test"

    def test_escape_all_special_chars(self, org_bot):
        """Test escaping of all MarkdownV2 special characters."""
        text = "_*[]()~>#+-=|{}.!"
        escaped = org_bot._escape_markdown_v2(text)
        assert escaped == r"\_\*\[\]\(\)\~\>\#\+\-\=\|\{\}\.\!"

    def test_escape_response_message(self, org_bot):
        """Test escaping of typical response message."""
        text = "Added to journal!"
        escaped = org_bot._escape_markdown_v2(text)
        assert escaped == r"Added to journal\!"


class TestCommandRouting:
    """Test command routing logic."""

    @pytest.mark.asyncio
    async def test_handle_command_recognized(self, org_bot):
        """Test handling of recognized commands."""
        message = Mock()
        message.message_id = 123
        message.chat_id = 1234567890

        response = await org_bot._handle_command(message, "/start")
        assert response == "Hello brain!"

    @pytest.mark.asyncio
    async def test_handle_command_unrecognized(self, org_bot):
        """Test handling of unrecognized commands."""
        message = Mock()
        response = await org_bot._handle_command(message, "/unknown")
        assert response == "Unrecognized command"

    @pytest.mark.asyncio
    async def test_handle_command_with_bot_mention(self, org_bot):
        """Test command with bot username mention."""
        message = Mock()
        message.message_id = 123
        message.chat_id = 1234567890

        # Command with @botname should still work
        response = await org_bot._handle_command(message, "/start@testbot")
        assert response == "Hello brain!"


class TestActionRouting:
    """Test action routing logic."""

    @pytest.mark.asyncio
    async def test_handle_action_ignored_chat(self, org_bot):
        """Test that ignored chats return None."""
        message = Mock()
        message.chat_id = 9999  # In ignored_chat_ids (from test_bot_settings)

        response = await org_bot._handle_action(message, "Test message", None)

        assert response is None

    @pytest.mark.asyncio
    async def test_handle_action_journal(self, org_bot):
        """Test journal action execution."""
        message = Mock()
        message.chat_id = 1234567890
        message.reply_to_message = None
        message.text = "Regular journal entry"
        message.caption = None
        message.photo = None
        message.document = None

        # Mock the action function to avoid GitHub API calls
        with patch.object(
            org_bot.actions["journal"], "function", return_value=None
        ) as mock_func:
            response = await org_bot._handle_action(message, "Regular entry", None)

        assert response == "Added to journal!"
        mock_func.assert_called_once_with(message, file_paths=None)

    @pytest.mark.asyncio
    async def test_handle_action_todo(self, org_bot):
        """Test todo action execution."""
        message = Mock()
        message.chat_id = 1234567890
        message.reply_to_message = None
        message.text = "todo write tests"
        message.caption = None
        message.photo = None
        message.document = None

        with patch.object(
            org_bot.actions["todo"], "function", return_value=None
        ) as mock_func:
            response = await org_bot._handle_action(message, "todo write tests", None)

        assert response == "Added to todo list!"
        mock_func.assert_called_once_with(message, file_paths=None)

    @pytest.mark.asyncio
    async def test_handle_action_reply(self, org_bot):
        """Test reply action execution."""
        message = Mock()
        message.chat_id = 1234567890
        message.reply_to_message = Mock()
        message.text = "This is a reply"
        message.caption = None
        message.photo = None
        message.document = None

        with patch.object(
            org_bot.actions["reply"], "function", return_value=None
        ) as mock_func:
            response = await org_bot._handle_action(message, "This is a reply", None)

        assert response == "Added reply to entry!"
        mock_func.assert_called_once_with(message, file_paths=None)

    @pytest.mark.asyncio
    async def test_handle_action_with_file(self, org_bot):
        """Test action with file attachment."""
        message = Mock()
        message.chat_id = 1234567890
        message.reply_to_message = None

        with patch.object(
            org_bot.actions["journal"], "function", return_value=None
        ) as mock_func:
            response = await org_bot._handle_action(
                message, "Entry with photo", file_paths=["/tmp/test.jpg"]
            )

        assert response == "Added to journal!"
        mock_func.assert_called_once_with(message, file_paths=["/tmp/test.jpg"])

    @pytest.mark.asyncio
    async def test_handle_action_error(self, org_bot):
        """Test error handling in action execution."""
        message = Mock()
        message.chat_id = 1234567890
        message.reply_to_message = None

        # Mock action to raise an exception
        with patch.object(
            org_bot.actions["journal"], "function", side_effect=Exception("Test error")
        ):
            response = await org_bot._handle_action(message, "Test message", None)

        assert response == "Failed to add to journal."


class TestPhotoHandling:
    """Test photo saving functionality."""

    @pytest.mark.asyncio
    async def test_save_photo(self, org_bot):
        """Test photo saving to temp file."""
        message = Mock()
        photo = Mock()
        photo.file_id = "test_photo_123"
        message.photo = [photo]

        # Mock bot and file operations
        mock_file = Mock()
        mock_file.download_as_bytearray = AsyncMock(return_value=b"fake image data")

        with patch.object(org_bot, "_get_bot") as mock_get_bot:
            mock_bot = Mock()
            mock_bot.get_file = AsyncMock(return_value=mock_file)
            mock_get_bot.return_value = mock_bot

            with patch("builtins.open", create=True):
                file_path = await org_bot._save_photo(message)

        assert file_path == "/tmp/test_photo_123.jpg"
        mock_bot.get_file.assert_called_once_with("test_photo_123")


class TestResponseSending:
    """Test response sending with retry logic."""

    @pytest.mark.asyncio
    async def test_send_response_success(self, org_bot):
        """Test successful response sending."""
        message = Mock()
        message.chat_id = 1234567890
        message.message_id = 123

        with patch.object(org_bot, "_get_bot") as mock_get_bot:
            mock_bot = Mock()
            mock_bot.send_message = AsyncMock()
            mock_get_bot.return_value = mock_bot

            await org_bot._send_response(message, "Test response!")

        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 1234567890
        assert call_args.kwargs["reply_to_message_id"] == 123
        assert call_args.kwargs["parse_mode"] == "MarkdownV2"
        # Text should be escaped
        assert r"Test response\!" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_send_unauthorized_response(self, org_bot):
        """Test unauthorized response message."""
        message = Mock()
        message.chat_id = 1234567890
        message.message_id = 123

        with patch.object(org_bot, "_send_response") as mock_send:
            await org_bot._send_unauthorized_response(message)

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "not for you" in call_args[0][1]
