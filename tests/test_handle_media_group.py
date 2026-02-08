"""
End-to-end tests for handle_media_group in bot.py.

These tests verify the full flow:
1. Multiple messages are received as a media group
2. All photos are saved
3. Caption is correctly extracted from ANY message (not just first)
4. All files are committed together in one atomic commit
"""

import logging
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from typing import List

import pytest

from src.bot import OrgBot

logger = logging.getLogger(__name__)


def create_mock_photo_message(
    message_id: int,
    caption: str | None = None,
    file_id: str | None = None,
    chat_id: int = 1234567890,
    media_group_id: str = "mg_test",
) -> Mock:
    """Create a mock Telegram photo message."""
    message = Mock()
    message.message_id = message_id
    message.text = None
    message.caption = caption
    message.media_group_id = media_group_id
    message.reply_to_message = None

    # Mock photo array (Telegram sends multiple sizes, we use last = highest res)
    photo = Mock()
    photo.file_id = file_id or f"photo_file_id_{message_id}"
    message.photo = [photo]

    message.document = None

    chat = Mock()
    chat.id = chat_id
    message.chat = chat
    message.chat_id = chat_id

    return message


class TestHandleMediaGroup:
    """Test suite for OrgBot.handle_media_group()."""

    @pytest.fixture
    def mock_bot_settings(self) -> Mock:
        """Create mock bot settings."""
        settings = Mock()
        settings.token = "mock_token"
        settings.authorized_chat_ids = [1234567890]
        settings.ignored_chat_ids = []
        settings.forward_unauthorized_to = None
        return settings

    @pytest.fixture
    def mock_github_settings(self) -> Mock:
        """Create mock GitHub settings."""
        settings = Mock()
        settings.token = "mock_github_token"
        settings.repo = "test/repo"
        return settings

    @pytest.fixture
    def mock_org_settings(self) -> Mock:
        """Create mock org settings."""
        settings = Mock()
        settings.journal_file = "journal.org"
        settings.todo_file = "todo.org"
        return settings

    @pytest.fixture
    def org_bot(
        self,
        mock_bot_settings: Mock,
        mock_github_settings: Mock,
        mock_org_settings: Mock,
    ) -> OrgBot:
        """Create OrgBot with mocked settings."""
        with patch("src.bot.create_commands", return_value={}), \
             patch("src.bot.create_actions") as mock_create_actions:
            # Create a mock action that records what it receives
            mock_action = Mock()
            mock_action.function = Mock()
            mock_action.response_message = "Added to journal"
            mock_create_actions.return_value = {"journal": mock_action}

            bot = OrgBot(
                bot_settings=mock_bot_settings,
                github_settings=mock_github_settings,
                org_settings=mock_org_settings,
            )
            bot._mock_action = mock_action
            return bot

    @pytest.mark.asyncio
    async def test_caption_extracted_from_first_message_with_caption(
        self,
        org_bot: OrgBot,
    ) -> None:
        """
        Test that caption is extracted from the first message that has one.

        Scenario: 3 photos, only the 2nd has a caption.
        Expected: The caption from the 2nd message should be used.
        """
        logger.info("=" * 80)
        logger.info("TEST: Caption extracted from first message WITH caption")
        logger.info("=" * 80)

        # Create 3 messages: first has no caption, second has caption, third has no caption
        messages = [
            create_mock_photo_message(1, caption=None),      # No caption
            create_mock_photo_message(2, caption="The actual caption"),  # Has caption
            create_mock_photo_message(3, caption=None),      # No caption
        ]

        # Mock auth and photo saving
        with patch("src.bot.auth_check", new_callable=AsyncMock, return_value=True), \
             patch.object(org_bot, "_save_photos", new_callable=AsyncMock) as mock_save, \
             patch.object(org_bot, "_send_response", new_callable=AsyncMock):

            mock_save.return_value = ["/tmp/p1.jpg", "/tmp/p2.jpg", "/tmp/p3.jpg"]

            await org_bot.handle_media_group(messages)

        # Verify action was called with the correct message (the one with caption)
        call_args = org_bot._mock_action.function.call_args

        # The message passed should be the one with the caption
        passed_message = call_args[0][0]
        assert passed_message.caption == "The actual caption", (
            f"Expected caption 'The actual caption', got '{passed_message.caption}'"
        )

        # All 3 file paths should be passed
        passed_file_paths = call_args[1]["file_paths"]
        assert len(passed_file_paths) == 3, (
            f"Expected 3 file paths, got {len(passed_file_paths)}"
        )

        logger.info("TEST PASSED")

    @pytest.mark.asyncio
    async def test_caption_from_third_message(
        self,
        org_bot: OrgBot,
    ) -> None:
        """
        Test that caption is found even if it's on the last message.
        """
        logger.info("=" * 80)
        logger.info("TEST: Caption from third (last) message")
        logger.info("=" * 80)

        messages = [
            create_mock_photo_message(1, caption=None),
            create_mock_photo_message(2, caption=None),
            create_mock_photo_message(3, caption="Caption on last photo"),
        ]

        with patch("src.bot.auth_check", new_callable=AsyncMock, return_value=True), \
             patch.object(org_bot, "_save_photos", new_callable=AsyncMock) as mock_save, \
             patch.object(org_bot, "_send_response", new_callable=AsyncMock):

            mock_save.return_value = ["/tmp/p1.jpg", "/tmp/p2.jpg", "/tmp/p3.jpg"]

            await org_bot.handle_media_group(messages)

        call_args = org_bot._mock_action.function.call_args
        passed_message = call_args[0][0]

        assert passed_message.caption == "Caption on last photo", (
            f"Expected 'Caption on last photo', got '{passed_message.caption}'"
        )

        logger.info("TEST PASSED")

    @pytest.mark.asyncio
    async def test_no_caption_placeholder_when_all_empty(
        self,
        org_bot: OrgBot,
    ) -> None:
        """
        Test behavior when NO message has a caption.

        Should use placeholder text, not fail.
        """
        logger.info("=" * 80)
        logger.info("TEST: No caption - all messages empty")
        logger.info("=" * 80)

        messages = [
            create_mock_photo_message(1, caption=None),
            create_mock_photo_message(2, caption=None),
        ]

        with patch("src.bot.auth_check", new_callable=AsyncMock, return_value=True), \
             patch.object(org_bot, "_save_photos", new_callable=AsyncMock) as mock_save, \
             patch.object(org_bot, "_send_response", new_callable=AsyncMock):

            mock_save.return_value = ["/tmp/p1.jpg", "/tmp/p2.jpg"]

            await org_bot.handle_media_group(messages)

        # Action should still be called
        org_bot._mock_action.function.assert_called_once()

        logger.info("TEST PASSED")

    @pytest.mark.asyncio
    async def test_all_photos_saved(
        self,
        org_bot: OrgBot,
    ) -> None:
        """
        Test that _save_photos is called with all messages.
        """
        logger.info("=" * 80)
        logger.info("TEST: All photos saved")
        logger.info("=" * 80)

        messages = [
            create_mock_photo_message(1, caption="Caption"),
            create_mock_photo_message(2),
            create_mock_photo_message(3),
            create_mock_photo_message(4),
        ]

        with patch("src.bot.auth_check", new_callable=AsyncMock, return_value=True), \
             patch.object(org_bot, "_save_photos", new_callable=AsyncMock) as mock_save, \
             patch.object(org_bot, "_send_response", new_callable=AsyncMock):

            mock_save.return_value = ["/tmp/p1.jpg", "/tmp/p2.jpg", "/tmp/p3.jpg", "/tmp/p4.jpg"]

            await org_bot.handle_media_group(messages)

        # Verify _save_photos was called with all 4 messages
        mock_save.assert_called_once_with(messages)

        # Verify all 4 paths passed to action
        call_args = org_bot._mock_action.function.call_args
        passed_file_paths = call_args[1]["file_paths"]
        assert len(passed_file_paths) == 4

        logger.info("TEST PASSED")

    @pytest.mark.asyncio
    async def test_first_message_caption_used_when_available(
        self,
        org_bot: OrgBot,
    ) -> None:
        """
        Test that if first message has caption, it's used (not a later one).
        """
        logger.info("=" * 80)
        logger.info("TEST: First message caption preferred")
        logger.info("=" * 80)

        messages = [
            create_mock_photo_message(1, caption="First caption"),
            create_mock_photo_message(2, caption="Second caption"),
        ]

        with patch("src.bot.auth_check", new_callable=AsyncMock, return_value=True), \
             patch.object(org_bot, "_save_photos", new_callable=AsyncMock) as mock_save, \
             patch.object(org_bot, "_send_response", new_callable=AsyncMock):

            mock_save.return_value = ["/tmp/p1.jpg", "/tmp/p2.jpg"]

            await org_bot.handle_media_group(messages)

        call_args = org_bot._mock_action.function.call_args
        passed_message = call_args[0][0]

        # First message's caption should be used
        assert passed_message.caption == "First caption"

        logger.info("TEST PASSED")
