"""
Unit tests for PostReplyToEntry functionality.

Tests cover:
- Reply to journal entry (finds original, nests reply)
- Reply to TODO entry (finds original, nests reply)
- Reply when original message not found (falls back to journal)
- Reply without reply_to_message (falls back to journal)
- Correct org-mode level nesting
- Correct insertion position in the file
"""

import logging
from unittest.mock import Mock, MagicMock, patch
from typing import Any, Dict

import pytest

from src.actions.post_reply import PostReplyToEntry
from src.actions.post_to_journal import PostToGitJournal

logger = logging.getLogger(__name__)


class TestPostReplyToEntry:
    """Test suite for PostReplyToEntry class."""

    @pytest.fixture
    def mock_github_client_with_journal_entry(self) -> MagicMock:
        """
        Create a mock GitHub client with a journal file containing an entry.

        The mock journal contains:
        - A header
        - An entry at line 2 with level 1 (*)
        - Some content under the entry
        - Another entry after it
        """
        logger.info("Setting up mock GitHub client with journal entry")

        client = MagicMock()
        mock_repo = MagicMock()
        client.get_repo.return_value = mock_repo

        # Create a journal file with an existing entry that can be replied to
        journal_content = """#+TITLE: My Journal
* Entry: [[https://t.me/c/1234567890/100][2025-12-17 10:00]]
This is the original message that we will reply to.
* Entry: [[https://t.me/c/1234567890/101][2025-12-17 10:05]]
This is another entry."""

        mock_contents = MagicMock()
        mock_contents.decoded_content = journal_content.encode("utf-8")
        mock_contents.sha = "mock_sha_journal"
        mock_contents.path = "test_journal.org"

        # Mock the get_contents to return our mock content
        mock_repo.get_contents.return_value = mock_contents

        # Mock update_file
        mock_repo.update_file.return_value = {"commit": {"sha": "new_commit_sha"}}

        logger.debug("Mock GitHub client configured with journal entry")
        return client

    @pytest.fixture
    def mock_github_client_with_todo_entry(self) -> MagicMock:
        """
        Create a mock GitHub client with a TODO file containing an entry.
        """
        logger.info("Setting up mock GitHub client with TODO entry")

        client = MagicMock()
        mock_repo = MagicMock()
        client.get_repo.return_value = mock_repo

        # Create files - both journal and todo
        journal_content = """#+TITLE: My Journal
* Entry: [[https://t.me/c/1234567890/101][2025-12-17 10:05]]
This is another entry."""

        todo_content = """#+TITLE: My TODOs
** TODO Review the pull request [[https://t.me/c/1234567890/100][2025-12-17 09:00]]
Some additional details about the pull request
** TODO Another task"""

        # We need to handle multiple get_contents calls
        def get_contents_side_effect(path, ref=None):
            mock_contents = MagicMock()
            if "journal" in path:
                mock_contents.decoded_content = journal_content.encode("utf-8")
                mock_contents.path = "test_journal.org"
            else:  # todo file
                mock_contents.decoded_content = todo_content.encode("utf-8")
                mock_contents.path = "test_todo.org"
            mock_contents.sha = f"mock_sha_{path}"
            return mock_contents

        mock_repo.get_contents.side_effect = get_contents_side_effect
        mock_repo.update_file.return_value = {"commit": {"sha": "new_commit_sha"}}

        logger.debug("Mock GitHub client configured with TODO entry")
        return client

    @pytest.fixture
    def mock_github_client_no_entry(self) -> MagicMock:
        """
        Create a mock GitHub client where the original message is NOT found.
        """
        logger.info("Setting up mock GitHub client without target entry")

        client = MagicMock()
        mock_repo = MagicMock()
        client.get_repo.return_value = mock_repo

        # Files without the message we're looking for
        journal_content = """#+TITLE: My Journal
* Entry: [[https://t.me/c/1234567890/999][2025-12-17 08:00]]
Some other message."""

        todo_content = """#+TITLE: My TODOs
** TODO Some task"""

        def get_contents_side_effect(path, ref=None):
            mock_contents = MagicMock()
            if "journal" in path:
                mock_contents.decoded_content = journal_content.encode("utf-8")
                mock_contents.path = "test_journal.org"
            else:  # todo file
                mock_contents.decoded_content = todo_content.encode("utf-8")
                mock_contents.path = "test_todo.org"
            mock_contents.sha = f"mock_sha_{path}"
            return mock_contents

        mock_repo.get_contents.side_effect = get_contents_side_effect
        mock_repo.update_file.return_value = {"commit": {"sha": "new_commit_sha"}}

        logger.debug("Mock GitHub client configured without target entry")
        return client

    @pytest.fixture
    def mock_reply_message(self) -> Mock:
        """
        Create a mock Telegram reply message.

        This message is replying to message ID 100 from chat 1234567890.
        """
        logger.debug("Creating mock reply message")

        # Create the original message that this is replying to
        original_message = Mock()
        original_message.message_id = 100
        original_chat = Mock()
        original_chat.id = 1234567890
        original_message.chat = original_chat

        # Create the reply message
        message = Mock()
        message.message_id = 200
        message.text = "This is my reply to the original message"
        message.caption = None
        message.photo = None
        message.document = None
        message.reply_to_message = original_message

        # Mock chat object for the reply
        chat = Mock()
        chat.id = 1234567890
        message.chat = chat

        logger.debug(f"Mock reply message created - ID: {message.message_id}")
        logger.debug(f"Replying to message ID: {original_message.message_id}")

        return message

    @pytest.fixture
    def mock_non_reply_message(self) -> Mock:
        """Create a mock message that is NOT a reply."""
        logger.debug("Creating mock non-reply message")

        message = Mock()
        message.message_id = 300
        message.text = "This is not a reply"
        message.caption = None
        message.photo = None
        message.document = None
        message.reply_to_message = None  # No reply

        chat = Mock()
        chat.id = 1234567890
        message.chat = chat

        return message

    @pytest.mark.unit
    @pytest.mark.reply
    def test_reply_to_journal_entry(
        self,
        mock_github_client_with_journal_entry: MagicMock,
        mock_reply_message: Mock,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test replying to a message found in the journal file.

        Expected behavior:
        - Find the original entry in journal
        - Insert reply as a nested subheader (** level)
        - Insert at correct position (after original entry content)
        """
        logger.info("=" * 80)
        logger.info("TEST: Reply to journal entry")
        logger.info("=" * 80)

        with patch(
            "src.actions.base_post_to_org_file.Github",
            return_value=mock_github_client_with_journal_entry,
        ):
            reply_instance = PostReplyToEntry(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
                todo_file_path=test_config["todo_file"],
            )

        message = mock_reply_message

        logger.info(f"Reply message ID: {message.message_id}")
        logger.info(f"Original message ID: {message.reply_to_message.message_id}")

        # Execute the method
        logger.info("Executing reply_instance.run() with reply message")
        result = reply_instance.run(message=message, file_path=None)

        # Verify result
        logger.info(f"Result: {result}")
        assert (
            result is True
        ), "Expected run() to return True for successful reply posting"

        # Verify GitHub interactions
        logger.info("Verifying GitHub API interactions")

        # Should have called get_contents to search for original entry
        assert (
            reply_instance.repo.get_contents.called
        ), "Should call get_contents to search"

        # Should have called update_file to insert the reply
        reply_instance.repo.update_file.assert_called_once()
        update_call_args = reply_instance.repo.update_file.call_args

        logger.debug(f"update_file called with args: {update_call_args}")

        # Verify the content structure
        updated_content = update_call_args[1]["content"]
        logger.info(f"Updated content length: {len(updated_content)} chars")
        logger.debug(f"Updated content:\n{updated_content}")

        # Verify the reply text appears
        assert (
            message.text in updated_content
        ), "Reply text should be in updated content"

        # Verify it's a nested entry (** Reply:)
        assert (
            "** Reply:" in updated_content
        ), "Should contain nested reply header (** level)"

        # Verify it contains the reply message link
        assert (
            "https://t.me/c/1234567890/200" in updated_content
        ), "Should contain reply message link"

        # Verify the commit message
        commit_message = update_call_args[1]["message"]
        logger.info(f"Commit message: {commit_message}")
        assert (
            "Reply to message 100" in commit_message
        ), "Commit should reference original message"

        logger.info("Reply to journal entry test PASSED")

    @pytest.mark.unit
    @pytest.mark.reply
    def test_reply_to_todo_entry(
        self,
        mock_github_client_with_todo_entry: MagicMock,
        mock_reply_message: Mock,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test replying to a message found in the TODO file.

        Expected behavior:
        - Search journal first (not found)
        - Find the original entry in todo file
        - Insert reply as nested subheader (*** level, since TODO is **)
        """
        logger.info("=" * 80)
        logger.info("TEST: Reply to TODO entry")
        logger.info("=" * 80)

        # Patch Github at a persistent level to handle fallback scenarios
        with patch(
            "src.actions.base_post_to_org_file.Github",
            return_value=mock_github_client_with_todo_entry,
        ) as mock_github:
            reply_instance = PostReplyToEntry(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
                todo_file_path=test_config["todo_file"],
            )

            message = mock_reply_message

            logger.info(f"Reply message ID: {message.message_id}")
            logger.info(f"Original message ID: {message.reply_to_message.message_id}")

            # Execute the method
            logger.info("Executing reply_instance.run() with reply to TODO")
            result = reply_instance.run(message=message, file_path=None)

            # Verify result
            logger.info(f"Result: {result}")
            assert (
                result is True
            ), "Expected run() to return True for successful reply posting"

            # Verify update was called
            assert reply_instance.repo.update_file.called, "Should update file"
            update_call_args = reply_instance.repo.update_file.call_args

            # Verify the content
            updated_content = update_call_args[1]["content"]
            logger.debug(f"Updated content:\n{updated_content}")

            # Verify the reply is nested correctly (*** level for TODO which is **)
            assert (
                "*** Reply:" in updated_content
            ), "Should contain nested reply header (*** level)"

            # Verify reply text
            assert (
                message.text in updated_content
            ), "Reply text should be in updated content"

            logger.info("Reply to TODO entry test PASSED")

    @pytest.mark.unit
    @pytest.mark.reply
    def test_reply_original_not_found_fallback(
        self,
        mock_github_client_no_entry: MagicMock,
        mock_reply_message: Mock,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test replying when original message is NOT found.

        Expected behavior:
        - Search journal (not found)
        - Search todo (not found)
        - Fall back to creating regular journal entry
        """
        logger.info("=" * 80)
        logger.info("TEST: Reply with original message not found (fallback)")
        logger.info("=" * 80)

        with patch(
            "src.actions.base_post_to_org_file.Github",
            return_value=mock_github_client_no_entry,
        ):
            reply_instance = PostReplyToEntry(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
                todo_file_path=test_config["todo_file"],
            )

            message = mock_reply_message

            # Execute the method
            logger.info("Executing reply_instance.run() when original not found")
            result = reply_instance.run(message=message, file_path=None)

            # Verify result
            logger.info(f"Result: {result}")
            assert result is True, "Expected run() to return True (fallback to journal)"

            # Verify it called update_file (for the fallback journal entry)
            assert (
                reply_instance.repo.update_file.called
            ), "Should update file with fallback entry"
            update_call_args = reply_instance.repo.update_file.call_args

            updated_content = update_call_args[1]["content"]
            logger.debug(f"Updated content:\n{updated_content}")

            # Verify it's a regular journal entry, not a nested reply
            assert (
                "* Entry:" in updated_content
            ), "Should create regular journal entry (fallback)"

            # Should NOT have the nested Reply format
            assert "** Reply:" not in updated_content, "Should not be a nested reply"

            logger.info("Fallback to journal test PASSED")

    @pytest.mark.unit
    @pytest.mark.reply
    def test_reply_without_reply_to_message(
        self,
        mock_github_client_no_entry: MagicMock,
        mock_non_reply_message: Mock,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test when PostReplyToEntry is called with a non-reply message.

        Expected behavior:
        - Detect no reply_to_message
        - Fall back to creating regular journal entry
        """
        logger.info("=" * 80)
        logger.info("TEST: PostReplyToEntry without reply_to_message")
        logger.info("=" * 80)

        with patch(
            "src.actions.base_post_to_org_file.Github",
            return_value=mock_github_client_no_entry,
        ):
            reply_instance = PostReplyToEntry(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
                todo_file_path=test_config["todo_file"],
            )

            message = mock_non_reply_message

            # Execute the method
            logger.info("Executing reply_instance.run() without reply_to_message")
            result = reply_instance.run(message=message, file_path=None)

            # Verify result
            assert result is True, "Expected run() to return True (fallback)"

            # Verify it created a regular journal entry
            assert reply_instance.repo.update_file.called, "Should update file"
            update_call_args = reply_instance.repo.update_file.call_args

            updated_content = update_call_args[1]["content"]
            logger.debug(f"Updated content:\n{updated_content}")

            # Should be a regular journal entry
            assert "* Entry:" in updated_content, "Should create regular journal entry"

            logger.info("Non-reply message test PASSED")

    @pytest.mark.unit
    @pytest.mark.reply
    def test_reply_to_reply_stays_at_same_level(
        self,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test replying to a reply message.

        Expected behavior:
        - Find the reply message
        - Find the top-level (non-reply) entry
        - Create new reply at same level as first reply (not deeper)

        Structure:
        * Entry: [[link1][time1]]
        Original content
        ** Reply: [[link2][time2]]
        First reply

        After replying to link2, should become:
        * Entry: [[link1][time1]]
        Original content
        ** Reply: [[link2][time2]]
        First reply
        ** Reply: [[link3][time3]]  <-- Same level as first reply, not ***
        Second reply
        """
        logger.info("=" * 80)
        logger.info("TEST: Reply to reply stays at same level")
        logger.info("=" * 80)

        # Create a journal with an entry and a reply to it
        journal_content = """#+TITLE: My Journal
* Entry: [[https://t.me/c/1234567890/100][2025-12-17 10:00]]
This is the original message.
** Reply: [[https://t.me/c/1234567890/200][2025-12-17 11:00]]
This is a reply to the original message.
* Entry: [[https://t.me/c/1234567890/999][2025-12-17 12:00]]
Another entry."""

        client = MagicMock()
        mock_repo = MagicMock()
        client.get_repo.return_value = mock_repo

        mock_contents = MagicMock()
        mock_contents.decoded_content = journal_content.encode("utf-8")
        mock_contents.sha = "mock_sha_reply"
        mock_contents.path = "test_journal.org"

        mock_repo.get_contents.return_value = mock_contents
        mock_repo.update_file.return_value = {"commit": {"sha": "new_commit_sha"}}

        # Create a message that replies to the reply (link2)
        original_message = Mock()
        original_message.message_id = 200  # Replying to the reply
        original_chat = Mock()
        original_chat.id = 1234567890
        original_message.chat = original_chat

        message = Mock()
        message.message_id = 300
        message.text = "This is a reply to the reply"
        message.caption = None
        message.photo = None
        message.document = None
        message.reply_to_message = original_message

        chat = Mock()
        chat.id = 1234567890
        message.chat = chat

        with patch("src.actions.base_post_to_org_file.Github", return_value=client):
            reply_instance = PostReplyToEntry(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
                todo_file_path=test_config["todo_file"],
            )

            logger.info(
                f"Replying to message {original_message.message_id} (which is itself a reply)"
            )
            result = reply_instance.run(message=message, file_path=None)

            # Verify result
            logger.info(f"Result: {result}")
            assert result is True, "Expected run() to return True"

            # Verify update was called
            assert mock_repo.update_file.called, "Should update file"
            update_call_args = mock_repo.update_file.call_args

            updated_content = update_call_args[1]["content"]
            logger.debug(f"Updated content:\n{updated_content}")

            # Count the number of ** Reply: entries - should have 2 now
            reply_count = updated_content.count("** Reply:")
            logger.info(f"Number of ** Reply: entries: {reply_count}")
            assert reply_count == 2, "Should have 2 replies at ** level"

            # Should NOT have *** Reply: (no deeper nesting)
            assert (
                "*** Reply:" not in updated_content
            ), "Should NOT have *** level replies"

            # Verify both replies are present
            assert (
                "https://t.me/c/1234567890/200" in updated_content
            ), "First reply link should be present"
            assert (
                "https://t.me/c/1234567890/300" in updated_content
            ), "Second reply link should be present"

            logger.info("Reply to reply test PASSED - all replies stay at same level")

    @pytest.mark.unit
    @pytest.mark.reply
    def test_find_top_level_entry_method(
        self,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test the find_top_level_entry method from org_api directly.

        Verifies:
        - Returns same entry if it's not a reply
        - Finds parent entry if current entry is a reply
        """
        logger.info("=" * 80)
        logger.info("TEST: find_top_level_entry method")
        logger.info("=" * 80)

        # Create a journal with nested structure
        journal_content = """#+TITLE: My Journal
* Entry: [[https://t.me/c/1234567890/100][2025-12-17 10:00]]
Original content
** Reply: [[https://t.me/c/1234567890/200][2025-12-17 11:00]]
First reply
* Another Entry: [[https://t.me/c/1234567890/300][2025-12-17 12:00]]
Different content"""

        client = MagicMock()
        mock_repo = MagicMock()
        client.get_repo.return_value = mock_repo

        mock_contents = MagicMock()
        mock_contents.decoded_content = journal_content.encode("utf-8")
        mock_contents.sha = "mock_sha"
        mock_contents.path = "test_journal.org"

        mock_repo.get_contents.return_value = mock_contents

        with patch("src.actions.base_post_to_org_file.Github", return_value=client):
            reply_instance = PostReplyToEntry(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
                todo_file_path=test_config["todo_file"],
            )

            # Test 1: Non-reply entry should return itself
            logger.info("Test 1: Non-reply entry")
            line_num, level = reply_instance.org_api.find_top_level_entry(
                test_config["journal_file"], 1, 1  # Line 1 is "* Entry:" (the original)
            )
            logger.info(f"Result: line {line_num}, level {level}")
            assert line_num == 1, "Should return same line for non-reply entry"
            assert level == 1, "Should return same level for non-reply entry"

            # Test 2: Reply entry should find its parent
            logger.info("Test 2: Reply entry")
            line_num, level = reply_instance.org_api.find_top_level_entry(
                test_config["journal_file"], 3, 2  # Line 3 is "** Reply:"
            )
            logger.info(f"Result: line {line_num}, level {level}")
            assert line_num == 1, "Should return parent entry line"
            assert level == 1, "Should return parent entry level"

            logger.info("find_top_level_entry method test PASSED")

    @pytest.mark.unit
    @pytest.mark.reply
    def test_find_original_entry_method(
        self,
        mock_github_client_with_journal_entry: MagicMock,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test the find_original_entry method from org_api directly.

        Verifies:
        - Correctly identifies line number
        - Correctly identifies org-mode level
        - Returns None when not found
        """
        logger.info("=" * 80)
        logger.info("TEST: find_original_entry method")
        logger.info("=" * 80)

        with patch(
            "src.actions.base_post_to_org_file.Github",
            return_value=mock_github_client_with_journal_entry,
        ):
            reply_instance = PostReplyToEntry(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
                todo_file_path=test_config["todo_file"],
            )

        # Test finding an entry that exists
        original_link = "https://t.me/c/1234567890/100"
        result = reply_instance.org_api.find_original_entry(
            original_link, test_config["journal_file"]
        )

        logger.info(f"Find result: {result}")
        assert result is not None, "Should find the entry"

        line_number, org_level = result
        logger.info(f"Found at line {line_number} with level {org_level}")

        assert line_number == 1, "Entry should be at line 1 (0-indexed)"
        assert org_level == 1, "Entry should have org-level 1 (*)"

        # Test finding an entry that doesn't exist
        nonexistent_link = "https://t.me/c/9999999999/999"
        result_not_found = reply_instance.org_api.find_original_entry(
            nonexistent_link, test_config["journal_file"]
        )

        logger.info(f"Find result for nonexistent: {result_not_found}")
        assert result_not_found is None, "Should return None when entry not found"

        logger.info("find_original_entry method test PASSED")

    @pytest.mark.unit
    @pytest.mark.reply
    def test_insert_position_calculation(
        self,
        mock_github_client_with_journal_entry: MagicMock,
        mock_reply_message: Mock,
        test_config: Dict[str, Any],
    ) -> None:
        """
        Test that replies are inserted at the correct position.

        The reply should be inserted:
        - After the original entry header
        - After any content under the original entry
        - Before the next entry of same or higher level
        """
        logger.info("=" * 80)
        logger.info("TEST: Reply insertion position")
        logger.info("=" * 80)

        with patch(
            "src.actions.base_post_to_org_file.Github",
            return_value=mock_github_client_with_journal_entry,
        ):
            reply_instance = PostReplyToEntry(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
                todo_file_path=test_config["todo_file"],
            )

        message = mock_reply_message

        # Execute
        result = reply_instance.run(message=message, file_path=None)
        assert result is True

        # Get the updated content
        update_call_args = reply_instance.repo.update_file.call_args
        updated_content = update_call_args[1]["content"]

        lines = updated_content.split("\n")
        logger.info(f"Updated content has {len(lines)} lines")

        # Find where the reply was inserted
        reply_line_index = None
        for i, line in enumerate(lines):
            if "** Reply:" in line:
                reply_line_index = i
                break

        assert reply_line_index is not None, "Should find the reply in the content"
        logger.info(f"Reply inserted at line {reply_line_index}")

        # Verify it comes after the original entry
        original_entry_index = None
        for i, line in enumerate(lines):
            if "* Entry:" in line and "https://t.me/c/1234567890/100" in line:
                original_entry_index = i
                break

        assert original_entry_index is not None, "Should find original entry"
        logger.info(f"Original entry at line {original_entry_index}")

        assert (
            reply_line_index > original_entry_index
        ), "Reply should come after original entry"

        # Verify it comes before the next top-level entry
        next_entry_index = None
        for i, line in enumerate(lines):
            if (
                i > original_entry_index
                and "* Entry:" in line
                and "https://t.me/c/1234567890/101" in line
            ):
                next_entry_index = i
                break

        if next_entry_index:
            logger.info(f"Next entry at line {next_entry_index}")
            assert (
                reply_line_index < next_entry_index
            ), "Reply should come before next entry"

        logger.info("Insertion position test PASSED")
