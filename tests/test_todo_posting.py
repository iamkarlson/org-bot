"""
Unit tests for PostToTodo functionality.

Tests cover:
- Text message posting (with TODO prefix)
- Photo message posting (with captions and TODO prefix)
- File/document message posting (with captions and TODO prefix)
"""

import logging
import os
from unittest.mock import Mock, MagicMock, patch
from typing import Any, Dict

import pytest

from src.actions.post_to_todo import PostToTodo

logger = logging.getLogger(__name__)


class TestPostToTodo:
    """Test suite for PostToTodo class."""

    @pytest.fixture
    def mock_github_client(self) -> MagicMock:
        """Create a mock GitHub client with all necessary methods."""
        logger.info("Setting up mock GitHub client")

        # Create mock client
        client = MagicMock()

        # Mock repository
        mock_repo = MagicMock()
        client.get_repo.return_value = mock_repo

        # Mock file contents
        mock_contents = MagicMock()
        mock_contents.decoded_content = b"* Existing TODO items\n** TODO First task"
        mock_contents.sha = "mock_sha_456"
        mock_contents.path = "test_todo.org"
        mock_repo.get_contents.return_value = mock_contents

        # Mock update_file and create_file
        mock_repo.update_file.return_value = {"commit": {"sha": "new_commit_sha"}}
        mock_repo.create_file.return_value = {"commit": {"sha": "file_commit_sha"}}

        # Mock Git Tree API for atomic commits
        mock_branch = MagicMock()
        mock_branch.commit.sha = "base_commit_sha"
        mock_repo.get_branch.return_value = mock_branch

        mock_blob = MagicMock()
        mock_blob.sha = "blob_sha_456"
        mock_repo.create_git_blob.return_value = mock_blob

        mock_base_tree = MagicMock()
        mock_base_tree.sha = "base_tree_sha"
        mock_repo.get_git_tree.return_value = mock_base_tree

        mock_new_tree = MagicMock()
        mock_new_tree.sha = "new_tree_sha"
        mock_repo.create_git_tree.return_value = mock_new_tree

        mock_parent_commit = MagicMock()
        mock_parent_commit.sha = "parent_commit_sha"
        mock_repo.get_git_commit.return_value = mock_parent_commit

        mock_commit = MagicMock()
        mock_commit.sha = "atomic_commit_sha"
        mock_repo.create_git_commit.return_value = mock_commit

        mock_ref = MagicMock()
        mock_repo.get_git_ref.return_value = mock_ref

        logger.debug(f"Mock GitHub client configured with repo: {mock_repo}")
        return client

    @pytest.fixture
    def todo_instance(
        self, mock_github_client: MagicMock, test_config: Dict[str, Any]
    ) -> PostToTodo:
        """Create a PostToTodo instance with mocked GitHub client."""
        logger.info("Creating PostToTodo instance for testing")

        with patch(
            "src.actions.base_post_to_org_file.Github", return_value=mock_github_client
        ):
            instance = PostToTodo(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["todo_file"],
            )

        logger.debug(f"TODO instance created with file_path: {instance.file_path}")
        return instance

    @pytest.fixture
    def mock_todo_message_text(self) -> Mock:
        """Create a mock Telegram text message with TODO prefix."""
        logger.debug("Creating mock TODO text message")

        message = Mock()
        message.message_id = 54321
        message.text = "TODO Review the pull request and merge it"
        message.caption = None
        message.photo = None
        message.document = None

        # Mock chat object
        chat = Mock()
        chat.id = 9876543210
        message.chat = chat

        logger.debug(
            f"Mock TODO message created - ID: {message.message_id}, Chat ID: {chat.id}"
        )
        logger.debug(f"Message text: {message.text}")

        return message

    @pytest.fixture
    def mock_todo_message_photo(self) -> Mock:
        """Create a mock Telegram photo message with TODO in caption."""
        logger.debug("Creating mock TODO photo message")

        message = Mock()
        message.message_id = 54322
        message.text = None
        message.caption = "TODO Check this screenshot for bugs"

        # Mock photo array
        photo = Mock()
        photo.file_id = "mock_todo_photo_file_id_789"
        photo.file_size = 1024 * 75
        photo.width = 1024
        photo.height = 768
        message.photo = [photo]

        message.document = None

        # Mock chat object
        chat = Mock()
        chat.id = 9876543210
        message.chat = chat

        logger.debug(f"Mock TODO photo message created - ID: {message.message_id}")
        logger.debug(f"Message caption: {message.caption}")

        return message

    @pytest.fixture
    def mock_todo_message_document(self) -> Mock:
        """Create a mock Telegram document message with TODO in caption."""
        logger.debug("Creating mock TODO document message")

        message = Mock()
        message.message_id = 54323
        message.text = None
        message.caption = "TODO Process this invoice document"
        message.photo = None

        # Mock document object
        document = Mock()
        document.file_id = "mock_todo_document_file_id_999"
        document.file_name = "invoice.pdf"
        document.file_size = 1024 * 200
        document.mime_type = "application/pdf"
        message.document = document

        # Mock chat object
        chat = Mock()
        chat.id = 9876543210
        message.chat = chat

        logger.debug(f"Mock TODO document message created - ID: {message.message_id}")
        logger.debug(f"Document filename: {document.file_name}")

        return message

    @pytest.mark.unit
    @pytest.mark.todo
    @pytest.mark.text
    def test_post_text_message_to_todo(
        self,
        todo_instance: PostToTodo,
        mock_todo_message_text: Mock,
    ) -> None:
        """
        Test posting a text message with TODO to todo list.

        This is the happy path test for TODO text messages.
        """
        logger.info("=" * 80)
        logger.info("TEST: Post TODO text message to todo list")
        logger.info("=" * 80)

        message = mock_todo_message_text

        logger.info(f"Input message ID: {message.message_id}")
        logger.info(f"Input message text: {message.text}")
        logger.info(f"Input chat ID: {message.chat.id}")

        # Execute the method
        logger.info("Executing todo_instance.run() with TODO text message")
        result = todo_instance.run(message=message, file_path=None)

        # Verify result
        logger.info(f"Result: {result}")
        assert result is True, "Expected run() to return True for successful posting"

        # Verify GitHub interactions
        logger.info("Verifying GitHub API interactions")

        # Should have called get_contents to fetch current file
        todo_instance.repo.get_contents.assert_called_once()
        logger.debug(
            f"get_contents called with: {todo_instance.repo.get_contents.call_args}"
        )

        # Should have called update_file to append new TODO
        todo_instance.repo.update_file.assert_called_once()
        update_call_args = todo_instance.repo.update_file.call_args

        logger.debug(f"update_file called with args: {update_call_args}")

        # Verify the content structure
        updated_content = update_call_args[1]["content"]
        logger.info(f"Updated content length: {len(updated_content)} chars")
        logger.debug(f"Updated content:\n{updated_content}")

        # Verify TODO format - the method strips "TODO " prefix and adds it back
        assert "** TODO" in updated_content, "Should contain org-mode TODO header"
        assert "Review the pull request and merge it" in updated_content, (
            "Should contain TODO text without prefix"
        )
        assert "Created at:" in updated_content, "Should contain creation timestamp"
        assert "https://t.me/" in updated_content, "Should contain Telegram link"

        logger.info("TODO text message test PASSED")

    @pytest.mark.unit
    @pytest.mark.todo
    @pytest.mark.picture
    def test_post_photo_message_to_todo(
        self,
        todo_instance: PostToTodo,
        mock_todo_message_photo: Mock,
    ) -> None:
        """
        Test posting a photo message with TODO caption to todo list.

        This is the happy path test for TODO photo messages.
        """
        logger.info("=" * 80)
        logger.info("TEST: Post TODO photo message to todo list")
        logger.info("=" * 80)

        message = mock_todo_message_photo

        logger.info(f"Input message ID: {message.message_id}")
        logger.info(f"Input message caption: {message.caption}")
        logger.info(f"Input chat ID: {message.chat.id}")
        logger.info(f"Photo file_id: {message.photo[0].file_id}")

        # Create a temporary test image file
        temp_image_path = "/tmp/test_todo_photo.png"
        logger.info(f"Creating temporary test image at: {temp_image_path}")

        # Create a small PNG file (1x1 pixel)
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        with open(temp_image_path, "wb") as f:
            f.write(png_data)

        logger.info("Temporary image created successfully")

        try:
            # Execute the method
            logger.info("Executing todo_instance.run() with TODO photo message")
            with patch.object(
                todo_instance.org_api,
                "create_atomic_commit",
                wraps=todo_instance.org_api.create_atomic_commit,
            ) as atomic_commit:
                result = todo_instance.run(message=message, file_path=temp_image_path)

            # Verify result
            logger.info(f"Result: {result}")
            assert result is True, (
                "Expected run() to return True for successful posting"
            )

            # Verify GitHub interactions
            logger.info("Verifying GitHub API interactions")

            atomic_commit.assert_called_once()
            file_changes, _commit_message = atomic_commit.call_args.args

            assert len(file_changes) == 2, "Expected photo + todo file update in one commit"
            paths = {path for path, _ in file_changes}
            assert any(p.startswith("pics/telegram/") for p in paths)
            assert todo_instance.file_path in paths

            updated_content = next(
                content for path, content in file_changes if path == todo_instance.file_path
            )
            logger.info(f"Updated content length: {len(updated_content)} chars")
            logger.debug(f"Updated content:\n{updated_content}")

            # Verify TODO format with image
            assert "** TODO" in updated_content, "Should contain org-mode TODO header"
            assert "Check this screenshot for bugs" in updated_content, (
                "Should contain TODO text"
            )
            assert "[[file:" in updated_content, "Should contain org-mode file link"
            assert "#+attr_html:" in updated_content, (
                "Should contain HTML attributes for image"
            )

            logger.info("TODO photo message test PASSED")

        finally:
            # Clean up temporary file
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
                logger.debug(f"Cleaned up temporary file: {temp_image_path}")

    @pytest.mark.unit
    @pytest.mark.todo
    @pytest.mark.file
    def test_post_file_message_to_todo(
        self,
        todo_instance: PostToTodo,
        mock_todo_message_document: Mock,
    ) -> None:
        """
        Test posting a file/document message with TODO caption to todo list.

        This is the happy path test for TODO file messages.
        """
        logger.info("=" * 80)
        logger.info("TEST: Post TODO file message to todo list")
        logger.info("=" * 80)

        message = mock_todo_message_document

        logger.info(f"Input message ID: {message.message_id}")
        logger.info(f"Input message caption: {message.caption}")
        logger.info(f"Input chat ID: {message.chat.id}")
        logger.info(f"Document file_id: {message.document.file_id}")
        logger.info(f"Document filename: {message.document.file_name}")

        # Create a temporary test PDF file
        temp_pdf_path = "/tmp/test_todo_document.pdf"
        logger.info(f"Creating temporary test PDF at: {temp_pdf_path}")

        # Minimal PDF content
        pdf_data = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n210\n%%EOF"

        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_data)

        logger.info("Temporary PDF created successfully")

        try:
            # Execute the method
            logger.info("Executing todo_instance.run() with TODO document message")
            with patch.object(
                todo_instance.org_api,
                "create_atomic_commit",
                wraps=todo_instance.org_api.create_atomic_commit,
            ) as atomic_commit:
                result = todo_instance.run(message=message, file_path=temp_pdf_path)

            # Verify result
            logger.info(f"Result: {result}")
            assert result is True, (
                "Expected run() to return True for successful posting"
            )

            # Verify GitHub interactions
            logger.info("Verifying GitHub API interactions")

            atomic_commit.assert_called_once()
            file_changes, _commit_message = atomic_commit.call_args.args

            assert len(file_changes) == 2, "Expected file + todo file update in one commit"
            paths = {path for path, _ in file_changes}
            uploaded_paths = [p for p in paths if p.startswith("pics/telegram/")]
            assert uploaded_paths, "Expected uploaded file under pics/telegram/"
            assert todo_instance.file_path in paths

            updated_content = next(
                content for path, content in file_changes if path == todo_instance.file_path
            )
            logger.info(f"Updated content length: {len(updated_content)} chars")
            logger.debug(f"Updated content:\n{updated_content}")

            # Verify TODO format with file
            assert "** TODO" in updated_content, "Should contain org-mode TODO header"
            assert "Process this invoice document" in updated_content, (
                "Should contain TODO text"
            )
            assert "[[file:" in updated_content, "Should contain org-mode file link"

            logger.info("TODO file message test PASSED")

        finally:
            # Clean up temporary file
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
                logger.debug(f"Cleaned up temporary file: {temp_pdf_path}")

    @pytest.mark.unit
    @pytest.mark.todo
    def test_get_new_org_item_format_todo(
        self,
        todo_instance: PostToTodo,
        mock_todo_message_text: Mock,
    ) -> None:
        """
        Test the _get_new_org_item method returns properly formatted TODO entry.
        """
        logger.info("=" * 80)
        logger.info("TEST: Verify TODO org-mode item formatting")
        logger.info("=" * 80)

        message = mock_todo_message_text
        org_item = todo_instance._get_new_org_item(message)

        logger.info(f"Generated TODO org item:\n{org_item}")

        # Verify format: ** TODO [task text]
        assert org_item.startswith("** TODO"), "Should start with '** TODO'"
        assert "Created at:" in org_item, "Should contain 'Created at:' timestamp"
        assert "https://t.me/" in org_item, "Should contain Telegram link"

        # The TODO prefix should be stripped from the original message
        assert "Review the pull request and merge it" in org_item, (
            "Should contain task text without TODO prefix"
        )

        # Verify timestamp format (YYYY-MM-DD HH:MM)
        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
        assert re.search(timestamp_pattern, org_item), (
            "Should contain timestamp in correct format"
        )

        logger.info("TODO org-mode formatting test PASSED")
