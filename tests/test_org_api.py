"""
Unit tests for OrgApi functionality.

Tests cover:
- Finding original entries by message link
- Finding top-level (non-reply) entries
- Inserting replies at correct positions in org hierarchy
- Edge cases and error handling
"""

import logging
from unittest.mock import MagicMock, Mock
from typing import Any, Dict

import pytest

from src.org_api import OrgApi

logger = logging.getLogger(__name__)


class TestOrgApi:
    """Test suite for OrgApi class."""

    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        """Create a basic mock repository."""
        logger.info("Setting up mock repository")
        repo = MagicMock()
        return repo

    @pytest.fixture
    def org_api(self, mock_repo: MagicMock) -> OrgApi:
        """Create an OrgApi instance with a mock repository."""
        logger.info("Creating OrgApi instance")
        return OrgApi(mock_repo)

    @pytest.fixture
    def simple_org_content(self) -> str:
        """Return a simple org file content for testing."""
        return """#+TITLE: Test Journal
* Entry: [[https://t.me/c/1234567890/100][2025-12-17 10:00]]
This is the original message.
* Entry: [[https://t.me/c/1234567890/101][2025-12-17 10:05]]
Another entry."""

    @pytest.fixture
    def nested_org_content(self) -> str:
        """Return an org file with nested entries (replies)."""
        return """#+TITLE: Test Journal
* Entry: [[https://t.me/c/1234567890/100][2025-12-17 10:00]]
Original message content.
** Reply: [[https://t.me/c/1234567890/200][2025-12-17 11:00]]
First reply.
** Reply: [[https://t.me/c/1234567890/300][2025-12-17 12:00]]
Second reply.
* Entry: [[https://t.me/c/1234567890/101][2025-12-17 13:00]]
Different entry."""

    @pytest.fixture
    def todo_org_content(self) -> str:
        """Return a TODO org file content."""
        return """#+TITLE: Test TODOs
** TODO Review pull request [[https://t.me/c/1234567890/500][2025-12-17 09:00]]
Some details about the PR.
** TODO Another task
More details."""

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_find_original_entry_found(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
        simple_org_content: str,
    ) -> None:
        """
        Test finding an original entry that exists in the file.

        Expected behavior:
        - Return (line_number, org_level) tuple
        - Correctly identify line number (0-indexed)
        - Correctly count org-mode level (asterisks)
        """
        logger.info("=" * 80)
        logger.info("TEST: Find original entry - found")
        logger.info("=" * 80)

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = simple_org_content.encode('utf-8')
        mock_repo.get_contents.return_value = mock_contents

        # Execute
        message_link = "https://t.me/c/1234567890/100"
        result = org_api.find_original_entry(message_link, "test.org")

        # Verify
        logger.info(f"Result: {result}")
        assert result is not None, "Should find the entry"

        line_number, org_level = result
        logger.info(f"Found at line {line_number} with level {org_level}")

        assert line_number == 1, "Entry should be at line 1 (0-indexed)"
        assert org_level == 1, "Entry should have org-level 1 (*)"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_find_original_entry_not_found(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
        simple_org_content: str,
    ) -> None:
        """
        Test finding an original entry that doesn't exist.

        Expected behavior:
        - Return None when entry is not found
        """
        logger.info("=" * 80)
        logger.info("TEST: Find original entry - not found")
        logger.info("=" * 80)

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = simple_org_content.encode('utf-8')
        mock_repo.get_contents.return_value = mock_contents

        # Execute
        message_link = "https://t.me/c/9999999999/999"
        result = org_api.find_original_entry(message_link, "test.org")

        # Verify
        logger.info(f"Result: {result}")
        assert result is None, "Should return None when entry not found"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_find_original_entry_with_todo_level(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
        todo_org_content: str,
    ) -> None:
        """
        Test finding an entry with level 2 (** TODO).

        Expected behavior:
        - Correctly identify org-level 2
        """
        logger.info("=" * 80)
        logger.info("TEST: Find original entry - TODO with level 2")
        logger.info("=" * 80)

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = todo_org_content.encode('utf-8')
        mock_repo.get_contents.return_value = mock_contents

        # Execute
        message_link = "https://t.me/c/1234567890/500"
        result = org_api.find_original_entry(message_link, "test_todo.org")

        # Verify
        logger.info(f"Result: {result}")
        assert result is not None, "Should find the TODO entry"

        line_number, org_level = result
        logger.info(f"Found at line {line_number} with level {org_level}")

        assert org_level == 2, "TODO entry should have org-level 2 (**)"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_find_original_entry_exception_handling(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
    ) -> None:
        """
        Test handling exceptions when reading file fails.

        Expected behavior:
        - Return None on exception
        - Log warning
        """
        logger.info("=" * 80)
        logger.info("TEST: Find original entry - exception handling")
        logger.info("=" * 80)

        # Setup mock to raise exception
        mock_repo.get_contents.side_effect = Exception("File not found")

        # Execute
        message_link = "https://t.me/c/1234567890/100"
        result = org_api.find_original_entry(message_link, "nonexistent.org")

        # Verify
        logger.info(f"Result: {result}")
        assert result is None, "Should return None on exception"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_find_top_level_entry_non_reply(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
        simple_org_content: str,
    ) -> None:
        """
        Test finding top-level entry when current entry is not a reply.

        Expected behavior:
        - Return the same line and level (it's already top-level)
        """
        logger.info("=" * 80)
        logger.info("TEST: Find top-level entry - non-reply")
        logger.info("=" * 80)

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = simple_org_content.encode('utf-8')
        mock_repo.get_contents.return_value = mock_contents

        # Execute - line 1 is "* Entry:" (not a reply)
        result = org_api.find_top_level_entry("test.org", 1, 1)

        # Verify
        logger.info(f"Result: {result}")
        line_number, org_level = result

        assert line_number == 1, "Should return same line for non-reply entry"
        assert org_level == 1, "Should return same level for non-reply entry"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_find_top_level_entry_from_reply(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
        nested_org_content: str,
    ) -> None:
        """
        Test finding top-level entry when starting from a reply.

        Expected behavior:
        - Find the parent entry (non-reply with lower level)
        """
        logger.info("=" * 80)
        logger.info("TEST: Find top-level entry - from reply")
        logger.info("=" * 80)

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = nested_org_content.encode('utf-8')
        mock_repo.get_contents.return_value = mock_contents

        # Execute - line 3 is "** Reply:" (first reply)
        result = org_api.find_top_level_entry("test.org", 3, 2)

        # Verify
        logger.info(f"Result: {result}")
        line_number, org_level = result

        logger.info(f"Found top-level entry at line {line_number} with level {org_level}")
        assert line_number == 1, "Should find parent entry at line 1"
        assert org_level == 1, "Parent entry should have level 1"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_find_top_level_entry_from_second_reply(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
        nested_org_content: str,
    ) -> None:
        """
        Test finding top-level entry from the second reply.

        Expected behavior:
        - Should still find the original parent, not the first reply
        """
        logger.info("=" * 80)
        logger.info("TEST: Find top-level entry - from second reply")
        logger.info("=" * 80)

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = nested_org_content.encode('utf-8')
        mock_repo.get_contents.return_value = mock_contents

        # Execute - line 5 is the second "** Reply:"
        result = org_api.find_top_level_entry("test.org", 5, 2)

        # Verify
        logger.info(f"Result: {result}")
        line_number, org_level = result

        assert line_number == 1, "Should find parent entry at line 1"
        assert org_level == 1, "Parent entry should have level 1"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_insert_reply_after_entry_simple(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
        simple_org_content: str,
    ) -> None:
        """
        Test inserting a reply after a simple entry.

        Expected behavior:
        - Insert reply at correct position
        - Update file with correct content
        - Call update_file with proper parameters
        """
        logger.info("=" * 80)
        logger.info("TEST: Insert reply after entry - simple")
        logger.info("=" * 80)

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = simple_org_content.encode('utf-8')
        mock_contents.sha = "mock_sha_123"
        mock_contents.path = "test.org"
        mock_repo.get_contents.return_value = mock_contents
        mock_repo.update_file.return_value = {"commit": {"sha": "new_sha"}}

        # Execute - insert after line 1 (first entry, level 1)
        reply_text = "** Reply: [[https://t.me/c/1234567890/200][2025-12-17 11:00]]\nThis is a reply."
        org_api.insert_reply_after_entry(
            "test.org",
            1,  # line_number
            1,  # org_level
            reply_text,
            "Test commit message"
        )

        # Verify update_file was called
        logger.info("Verifying update_file was called")
        assert mock_repo.update_file.called, "Should call update_file"

        call_args = mock_repo.update_file.call_args
        logger.debug(f"update_file called with: {call_args}")

        # Verify parameters
        assert call_args[1]["path"] == "test.org"
        assert call_args[1]["message"] == "Test commit message"
        assert call_args[1]["sha"] == "mock_sha_123"
        assert call_args[1]["branch"] == "main"

        # Verify content has the reply inserted
        updated_content = call_args[1]["content"]
        logger.info(f"Updated content:\n{updated_content}")

        assert "** Reply:" in updated_content, "Should contain reply header"
        assert "This is a reply." in updated_content, "Should contain reply text"

        # Verify position - reply should come after original entry but before next entry
        lines = updated_content.split("\n")
        reply_line_idx = None
        for i, line in enumerate(lines):
            if "** Reply:" in line:
                reply_line_idx = i
                break

        assert reply_line_idx is not None, "Should find reply in content"
        logger.info(f"Reply inserted at line {reply_line_idx}")

        # Reply should be after line 1 (original entry)
        assert reply_line_idx > 1, "Reply should be after original entry"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_insert_reply_after_entry_with_content(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
    ) -> None:
        """
        Test inserting a reply after an entry that has content lines.

        Expected behavior:
        - Reply should be inserted after all content of the original entry
        - Reply should be before the next same-level entry
        """
        logger.info("=" * 80)
        logger.info("TEST: Insert reply after entry - with content")
        logger.info("=" * 80)

        # Content with multiple lines under an entry
        content_with_lines = """#+TITLE: Test Journal
* Entry: [[https://t.me/c/1234567890/100][2025-12-17 10:00]]
This is the original message.
It has multiple lines.
And even more content.
* Entry: [[https://t.me/c/1234567890/101][2025-12-17 10:05]]
Another entry."""

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = content_with_lines.encode('utf-8')
        mock_contents.sha = "mock_sha_456"
        mock_contents.path = "test.org"
        mock_repo.get_contents.return_value = mock_contents
        mock_repo.update_file.return_value = {"commit": {"sha": "new_sha"}}

        # Execute
        reply_text = "** Reply: [[https://t.me/c/1234567890/200][2025-12-17 11:00]]\nReply text."
        org_api.insert_reply_after_entry(
            "test.org",
            1,  # line_number (first entry)
            1,  # org_level
            reply_text,
            "Insert reply commit"
        )

        # Verify
        call_args = mock_repo.update_file.call_args
        updated_content = call_args[1]["content"]
        logger.info(f"Updated content:\n{updated_content}")

        lines = updated_content.split("\n")

        # Find positions
        first_entry_idx = None
        reply_idx = None
        second_entry_idx = None

        for i, line in enumerate(lines):
            if "* Entry:" in line and "100" in line:
                first_entry_idx = i
            elif "** Reply:" in line:
                reply_idx = i
            elif "* Entry:" in line and "101" in line:
                second_entry_idx = i

        logger.info(f"First entry at line {first_entry_idx}")
        logger.info(f"Reply at line {reply_idx}")
        logger.info(f"Second entry at line {second_entry_idx}")

        # Verify positions
        assert first_entry_idx is not None, "Should find first entry"
        assert reply_idx is not None, "Should find reply"
        assert second_entry_idx is not None, "Should find second entry"

        # Reply should be after first entry and all its content
        assert reply_idx > first_entry_idx, "Reply should be after first entry"
        # Reply should be before second entry
        assert reply_idx < second_entry_idx, "Reply should be before second entry"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_insert_reply_at_end_of_file(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
    ) -> None:
        """
        Test inserting a reply after the last entry in the file.

        Expected behavior:
        - Reply should be appended at the end
        """
        logger.info("=" * 80)
        logger.info("TEST: Insert reply - at end of file")
        logger.info("=" * 80)

        # Content with only one entry
        single_entry_content = """#+TITLE: Test Journal
* Entry: [[https://t.me/c/1234567890/100][2025-12-17 10:00]]
This is the only entry."""

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = single_entry_content.encode('utf-8')
        mock_contents.sha = "mock_sha_789"
        mock_contents.path = "test.org"
        mock_repo.get_contents.return_value = mock_contents
        mock_repo.update_file.return_value = {"commit": {"sha": "new_sha"}}

        # Execute
        reply_text = "** Reply: [[https://t.me/c/1234567890/200][2025-12-17 11:00]]\nReply at end."
        org_api.insert_reply_after_entry(
            "test.org",
            1,  # line_number
            1,  # org_level
            reply_text,
            "Reply at end commit"
        )

        # Verify
        call_args = mock_repo.update_file.call_args
        updated_content = call_args[1]["content"]
        logger.info(f"Updated content:\n{updated_content}")

        # Reply should be in the content
        assert "** Reply:" in updated_content, "Should contain reply"
        assert "Reply at end." in updated_content, "Should contain reply text"

        # Verify it's at the end
        lines = updated_content.split("\n")
        reply_idx = None
        for i, line in enumerate(lines):
            if "** Reply:" in line:
                reply_idx = i
                break

        assert reply_idx is not None, "Should find reply"
        # Reply should be near the end (allowing for blank lines)
        assert reply_idx >= len(lines) - 3, "Reply should be near end of file"

        logger.info("Test PASSED")

    @pytest.mark.unit
    @pytest.mark.orgapi
    def test_insert_reply_maintains_structure(
        self,
        org_api: OrgApi,
        mock_repo: MagicMock,
        nested_org_content: str,
    ) -> None:
        """
        Test that inserting a reply maintains the org structure.

        Expected behavior:
        - Existing replies should not be affected
        - New reply should be inserted in correct position
        - All org-mode levels should be preserved
        """
        logger.info("=" * 80)
        logger.info("TEST: Insert reply - maintains structure")
        logger.info("=" * 80)

        # Setup mock
        mock_contents = MagicMock()
        mock_contents.decoded_content = nested_org_content.encode('utf-8')
        mock_contents.sha = "mock_sha_structure"
        mock_contents.path = "test.org"
        mock_repo.get_contents.return_value = mock_contents
        mock_repo.update_file.return_value = {"commit": {"sha": "new_sha"}}

        # Execute - insert another reply to the first entry
        reply_text = "** Reply: [[https://t.me/c/1234567890/400][2025-12-17 14:00]]\nThird reply."
        org_api.insert_reply_after_entry(
            "test.org",
            1,  # line_number (first entry)
            1,  # org_level
            reply_text,
            "Third reply commit"
        )

        # Verify
        call_args = mock_repo.update_file.call_args
        updated_content = call_args[1]["content"]
        logger.info(f"Updated content:\n{updated_content}")

        # Count replies - should now have 3
        reply_count = updated_content.count("** Reply:")
        logger.info(f"Number of ** Reply: entries: {reply_count}")
        assert reply_count == 3, "Should have 3 replies now"

        # Verify all original content is preserved
        assert "https://t.me/c/1234567890/100" in updated_content, "Original entry preserved"
        assert "https://t.me/c/1234567890/200" in updated_content, "First reply preserved"
        assert "https://t.me/c/1234567890/300" in updated_content, "Second reply preserved"
        assert "https://t.me/c/1234567890/101" in updated_content, "Second entry preserved"

        # Verify new reply is present
        assert "https://t.me/c/1234567890/400" in updated_content, "New reply added"
        assert "Third reply." in updated_content, "New reply text added"

        logger.info("Test PASSED")
