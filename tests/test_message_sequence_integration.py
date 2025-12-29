"""
Integration test for message sequence processing.

This test verifies the full flow of:
1. Posting a regular journal entry
2. Replying to that entry
3. Replying to the reply
4. Verifying all entries are in the file
5. Verifying responses are generated for each action
"""

import os
import logging
from unittest.mock import Mock, MagicMock, patch
from typing import Any, Dict, List

import pytest

# Set environment variables before importing src modules
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["GITHUB_REPO"] = "test/repo"
os.environ["JOURNAL_FILE"] = "journal.org"
os.environ["AUTHORIZED_CHAT_IDS"] = "1234567890"
os.environ["BOT_TOKEN"] = "test_bot_token"
os.environ.setdefault("SENTRY_DSN", "")

logger = logging.getLogger(__name__)


# Create a dummy mock repo for initialization
def _create_dummy_github_client():
    """Create a mock GitHub client that doesn't make real API calls."""
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_contents = MagicMock()
    mock_contents.decoded_content = b"# Dummy content"
    mock_contents.sha = "dummy_sha"
    mock_repo.get_contents.return_value = mock_contents
    mock_client.get_repo.return_value = mock_repo
    return mock_client


# No imports needed here - we'll import inside test functions after patching


class TestMessageSequenceIntegration:
    """Integration test suite for message sequence processing."""

    @pytest.fixture
    def mock_github_repo_with_state(self) -> MagicMock:
        """
        Create a mock GitHub repository that maintains state across operations.
        This simulates a real repository where content changes with each operation.
        """
        logger.info("Setting up stateful mock GitHub repository")

        # Initial state - empty journal
        class StatefulRepo:
            def __init__(self):
                self.content = "#+TITLE: My Journal\n"
                self.sha = "initial_sha"
                self.update_count = 0

            def get_contents(self, path, ref="main"):
                mock_contents = MagicMock()
                mock_contents.decoded_content = self.content.encode("utf-8")
                mock_contents.sha = self.sha
                mock_contents.path = path
                logger.debug(f"get_contents called, current content:\n{self.content}")
                return mock_contents

            def update_file(self, path, message, content, sha, branch):
                logger.info(f"update_file called: {message}")
                logger.debug(f"New content:\n{content}")
                self.content = content
                self.sha = f"sha_after_update_{self.update_count}"
                self.update_count += 1
                return {"commit": {"sha": self.sha}}

            def create_file(self, path, message, content, branch):
                logger.info(f"create_file called: {message}")
                return {"commit": {"sha": f"file_sha_{self.update_count}"}}

        repo = StatefulRepo()
        return repo

    @pytest.fixture
    def message_sequence(self) -> List[Dict[str, Any]]:
        """
        Define a sequence of Telegram messages to test.
        Each message is a dict with the properties needed to create a Mock.
        """
        return [
            {
                "name": "original_entry",
                "message_id": 100,
                "chat_id": 1234567890,
                "text": "This is my original journal entry",
                "reply_to_message": None,
                "expected_response": "Added to journal!",
            },
            {
                "name": "first_reply",
                "message_id": 200,
                "chat_id": 1234567890,
                "text": "This is a reply to the original entry",
                "reply_to_message_id": 100,  # Replying to message 100
                "expected_response": "Added reply to entry!",
            },
            {
                "name": "second_reply",
                "message_id": 300,
                "chat_id": 1234567890,
                "text": "This is a reply to the first reply",
                "reply_to_message_id": 200,  # Replying to message 200
                "expected_response": "Added reply to entry!",
            },
            {
                "name": "todo_entry",
                "message_id": 400,
                "chat_id": 1234567890,
                "text": "TODO Write more tests",
                "reply_to_message": None,
                "expected_response": "Added to todo list!",
            },
        ]

    def _create_mock_message(
        self, msg_data: Dict[str, Any], previous_messages: List[Mock]
    ) -> Mock:
        """
        Create a mock Telegram message from the data dict.
        If reply_to_message_id is set, link it to the corresponding previous message.
        """
        message = Mock()
        message.message_id = msg_data["message_id"]
        message.text = msg_data["text"]
        message.caption = None
        message.photo = None
        message.document = None
        message.to_json.return_value = "{}"  # Add to_json method for logger

        # Mock chat object
        chat = Mock()
        chat.id = msg_data["chat_id"]
        message.chat = chat

        # Handle reply_to_message
        if "reply_to_message_id" in msg_data:
            # Find the original message in previous_messages
            reply_to_id = msg_data["reply_to_message_id"]
            original_msg = next(
                (m for m in previous_messages if m.message_id == reply_to_id), None
            )
            if original_msg:
                message.reply_to_message = original_msg
                logger.debug(
                    f"Message {msg_data['message_id']} replies to {reply_to_id}"
                )
            else:
                logger.warning(f"Could not find message {reply_to_id} to reply to")
                message.reply_to_message = None
        else:
            message.reply_to_message = msg_data.get("reply_to_message")

        return message

    @pytest.mark.integration
    @pytest.mark.sequence
    @pytest.mark.asyncio
    async def test_message_sequence_full_flow(
        self,
        mock_github_repo_with_state: MagicMock,
        message_sequence: List[Dict[str, Any]],
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test a full sequence of messages to ensure:
        1. Each message is processed correctly
        2. Each message produces the expected response
        3. The file content is updated correctly
        4. Replies are nested properly
        """
        logger.info("=" * 80)
        logger.info("TEST: Full message sequence integration")
        logger.info("=" * 80)

        # Create mock GitHub client that returns our stateful repo
        mock_client = MagicMock()
        mock_client.get_repo.return_value = mock_github_repo_with_state

        previous_messages = []
        responses = []

        with patch(
            "src.actions.base_post_to_org_file.Github", return_value=mock_client
        ):
            # Import here to ensure patch is applied
            from src.bot import OrgBot
            from src.config import BotConfig, GitHubConfig

            # Create test configs
            bot_config = BotConfig(
                bot_token="test_bot_token",
                authorized_chat_ids=[1234567890],
                ignored_chat_ids=[],
                forward_unauthorized_to=None,
                sentry_dsn="",
            )
            github_config = GitHubConfig(
                token="test_token",
                repo_name="test/repo",
                journal_file="journal.org",
                todo_file="todo.org",
            )

            # Create OrgBot instance with test configs
            org_bot = OrgBot(bot_config=bot_config, github_config=github_config)

            # Process each message in sequence
            for i, msg_data in enumerate(message_sequence):
                logger.info(
                    f"\n--- Processing message {i + 1}/{len(message_sequence)}: {msg_data['name']} ---"
                )

                # Create mock message
                message = self._create_mock_message(msg_data, previous_messages)
                previous_messages.append(message)

                # Process the message using OrgBot's internal method
                response = await org_bot._handle_action(
                    message, message.text, file_path=None
                )

                logger.info(f"Response: {response}")
                responses.append(response)

                # Verify response
                expected_response = msg_data["expected_response"]
                assert response == expected_response, (
                    f"Message {msg_data['name']}: expected '{expected_response}', got '{response}'"
                )

                logger.info(f"✓ Response matches expected: {response}")

        # Verify final file content
        logger.info("\n--- Verifying final file content ---")
        final_content = mock_github_repo_with_state.content
        logger.info(f"Final content:\n{final_content}")

        # Verify all messages are in the file
        assert "https://t.me/c/1234567890/100" in final_content, (
            "Original entry should be in file"
        )
        assert "This is my original journal entry" in final_content, (
            "Original text should be in file"
        )

        assert "https://t.me/c/1234567890/200" in final_content, (
            "First reply should be in file"
        )
        assert "This is a reply to the original entry" in final_content, (
            "First reply text should be in file"
        )

        assert "https://t.me/c/1234567890/300" in final_content, (
            "Second reply should be in file"
        )
        assert "This is a reply to the first reply" in final_content, (
            "Second reply text should be in file"
        )

        # Verify proper nesting - all replies should be at ** level
        reply_count = final_content.count("** Reply:")
        logger.info(f"Number of ** Reply: entries: {reply_count}")
        assert reply_count == 2, (
            f"Should have 2 replies at ** level, found {reply_count}"
        )

        # Should NOT have *** level replies
        assert "*** Reply:" not in final_content, "Should not have *** level replies"

        # Verify all responses were generated
        assert len(responses) == len(message_sequence), (
            "Should have response for each message"
        )
        assert all(r is not None for r in responses), "All responses should be non-None"

        logger.info("\n✓ All messages processed correctly")
        logger.info("✓ All responses generated")
        logger.info("✓ File content updated correctly")
        logger.info("✓ Replies nested properly at same level")

    @pytest.mark.integration
    @pytest.mark.sequence
    @pytest.mark.asyncio
    async def test_reply_response_not_none(
        self,
        mock_github_repo_with_state: MagicMock,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Specific test to verify that reply messages generate a response.
        This test focuses on the issue where reply might not respond.
        """
        logger.info("=" * 80)
        logger.info("TEST: Reply response verification")
        logger.info("=" * 80)

        mock_client = MagicMock()
        mock_client.get_repo.return_value = mock_github_repo_with_state

        with patch(
            "src.actions.base_post_to_org_file.Github", return_value=mock_client
        ):
            from src.actions.post_reply import PostReplyToEntry

            reply_instance = PostReplyToEntry(
                github_token="test_token",
                repo_name="test/repo",
                file_path="journal.org",
                todo_file_path="todo.org",
            )

            # First, add an original entry
            original_message = Mock()
            original_message.message_id = 100
            original_message.text = "Original entry"
            original_message.caption = None
            original_message.photo = None
            original_message.document = None
            original_message.reply_to_message = None
            original_chat = Mock()
            original_chat.id = 1234567890
            original_message.chat = original_chat

            # Manually update the repo to have an entry
            mock_github_repo_with_state.content = """#+TITLE: My Journal
* Entry: [[https://t.me/c/1234567890/100][2025-12-17 10:00]]
Original entry"""

            # Now create a reply message
            reply_message = Mock()
            reply_message.message_id = 200
            reply_message.text = "This is a reply"
            reply_message.caption = None
            reply_message.photo = None
            reply_message.document = None
            reply_message.reply_to_message = original_message
            reply_message.to_json.return_value = "{}"  # Add to_json method
            reply_chat = Mock()
            reply_chat.id = 1234567890
            reply_message.chat = reply_chat

            # Create OrgBot instance
            from src.bot import OrgBot
            from src.config import BotConfig, GitHubConfig

            bot_config = BotConfig(
                bot_token="test_bot_token",
                authorized_chat_ids=[1234567890],
                ignored_chat_ids=[],
                forward_unauthorized_to=None,
                sentry_dsn="",
            )
            github_config = GitHubConfig(
                token="test_token",
                repo_name="test/repo",
                journal_file="journal.org",
                todo_file="todo.org",
            )

            org_bot = OrgBot(bot_config=bot_config, github_config=github_config)

            # Process the reply
            response = await org_bot._handle_action(
                reply_message, reply_message.text, file_path=None
            )

            logger.info(f"Response from reply: {response}")

            # Verify response is not None
            assert response is not None, "Reply should generate a response"
            assert response == "Added reply to entry!", (
                f"Expected 'Added reply to entry!', got '{response}'"
            )

            logger.info("✓ Reply generated correct response")
