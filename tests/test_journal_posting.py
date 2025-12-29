"""
Unit tests for PostToGitJournal functionality.

Tests cover:
- Text message posting
- Photo message posting (with captions)
- File/document message posting (with captions)
"""

import logging
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Any, Dict

import pytest

from src.actions.post_to_journal import PostToGitJournal

logger = logging.getLogger(__name__)


class TestPostToGitJournal:
    """Test suite for PostToGitJournal class."""

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
        mock_contents.decoded_content = (
            b"* Existing journal entry\nSome existing content"
        )
        mock_contents.sha = "mock_sha_123"
        mock_contents.path = "test_journal.org"
        mock_repo.get_contents.return_value = mock_contents

        # Mock update_file and create_file
        mock_repo.update_file.return_value = {"commit": {"sha": "new_commit_sha"}}
        mock_repo.create_file.return_value = {"commit": {"sha": "file_commit_sha"}}

        logger.debug(f"Mock GitHub client configured with repo: {mock_repo}")
        return client

    @pytest.fixture
    def journal_instance(
        self, mock_github_client: MagicMock, test_config: Dict[str, Any]
    ) -> PostToGitJournal:
        """Create a PostToGitJournal instance with mocked GitHub client."""
        logger.info("Creating PostToGitJournal instance for testing")

        with patch(
            "src.actions.base_post_to_org_file.Github", return_value=mock_github_client
        ):
            instance = PostToGitJournal(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
            )

        logger.debug(f"Journal instance created with file_path: {instance.file_path}")
        return instance

    @pytest.mark.unit
    @pytest.mark.journal
    @pytest.mark.text
    def test_post_text_message_to_journal(
        self,
        journal_instance: PostToGitJournal,
        mock_telegram_message_text: Mock,
    ) -> None:
        """
        Test posting a text message to journal.

        This is the happy path test for text messages.
        """
        logger.info("=" * 80)
        logger.info("TEST: Post text message to journal")
        logger.info("=" * 80)

        message = mock_telegram_message_text

        logger.info(f"Input message ID: {message.message_id}")
        logger.info(f"Input message text: {message.text}")
        logger.info(f"Input chat ID: {message.chat.id}")

        # Execute the method
        logger.info("Executing journal_instance.run() with text message")
        result = journal_instance.run(message=message, file_path=None)

        # Verify result
        logger.info(f"Result: {result}")
        assert result is True, "Expected run() to return True for successful posting"

        # Verify GitHub interactions
        logger.info("Verifying GitHub API interactions")

        # Should have called get_contents to fetch current file
        journal_instance.repo.get_contents.assert_called_once()
        logger.debug(
            f"get_contents called with: {journal_instance.repo.get_contents.call_args}"
        )

        # Should have called update_file to append new content
        journal_instance.repo.update_file.assert_called_once()
        update_call_args = journal_instance.repo.update_file.call_args

        logger.debug(f"update_file called with args: {update_call_args}")

        # Verify the content structure
        updated_content = update_call_args[1]["content"]
        logger.info(f"Updated content length: {len(updated_content)} chars")
        logger.debug(f"Updated content:\n{updated_content}")

        # Verify the message text appears in the updated content
        assert message.text in updated_content, (
            "Message text should be in updated content"
        )

        # Verify org-mode entry format
        assert "* Entry:" in updated_content, "Should contain org-mode entry header"
        assert "https://t.me/" in updated_content, "Should contain Telegram link"

        logger.info("Text message test PASSED")

    @pytest.mark.unit
    @pytest.mark.journal
    @pytest.mark.picture
    def test_post_photo_message_to_journal(
        self,
        journal_instance: PostToGitJournal,
        mock_telegram_message_photo: Mock,
        sample_image_path: Path,
    ) -> None:
        """
        Test posting a photo message with caption to journal.

        This is the happy path test for photo messages.
        """
        logger.info("=" * 80)
        logger.info("TEST: Post photo message to journal")
        logger.info("=" * 80)

        message = mock_telegram_message_photo

        logger.info(f"Input message ID: {message.message_id}")
        logger.info(f"Input message caption: {message.caption}")
        logger.info(f"Input chat ID: {message.chat.id}")
        logger.info(f"Photo file_id: {message.photo[0].file_id}")

        # Create a temporary test image file
        temp_image_path = "/tmp/test_photo.png"
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
            logger.info("Executing journal_instance.run() with photo message")
            result = journal_instance.run(message=message, file_path=temp_image_path)

            # Verify result
            logger.info(f"Result: {result}")
            assert result is True, (
                "Expected run() to return True for successful posting"
            )

            # Verify GitHub interactions
            logger.info("Verifying GitHub API interactions")

            # Should have called create_file to upload the image
            journal_instance.repo.create_file.assert_called_once()
            create_call_args = journal_instance.repo.create_file.call_args
            logger.debug(f"create_file called with: {create_call_args}")

            # Should have called update_file to append journal entry with image reference
            journal_instance.repo.update_file.assert_called_once()
            update_call_args = journal_instance.repo.update_file.call_args
            logger.debug(f"update_file called with: {update_call_args}")

            # Verify the content structure
            updated_content = update_call_args[1]["content"]
            logger.info(f"Updated content length: {len(updated_content)} chars")
            logger.debug(f"Updated content:\n{updated_content}")

            # Verify the caption appears in the content
            assert message.caption in updated_content, (
                "Message caption should be in updated content"
            )

            # Verify org-mode image reference format
            assert "[[file:" in updated_content, "Should contain org-mode file link"
            assert "#+attr_html:" in updated_content, (
                "Should contain HTML attributes for image"
            )

            logger.info("Photo message test PASSED")

        finally:
            # Clean up temporary file
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
                logger.debug(f"Cleaned up temporary file: {temp_image_path}")

    @pytest.mark.unit
    @pytest.mark.journal
    @pytest.mark.file
    def test_post_file_message_to_journal(
        self,
        journal_instance: PostToGitJournal,
        mock_telegram_message_document: Mock,
    ) -> None:
        """
        Test posting a file/document message with caption to journal.

        This is the happy path test for file messages.
        """
        logger.info("=" * 80)
        logger.info("TEST: Post file message to journal")
        logger.info("=" * 80)

        message = mock_telegram_message_document

        logger.info(f"Input message ID: {message.message_id}")
        logger.info(f"Input message caption: {message.caption}")
        logger.info(f"Input chat ID: {message.chat.id}")
        logger.info(f"Document file_id: {message.document.file_id}")
        logger.info(f"Document filename: {message.document.file_name}")

        # Create a temporary test PDF file
        temp_pdf_path = "/tmp/test_document.pdf"
        logger.info(f"Creating temporary test PDF at: {temp_pdf_path}")

        # Minimal PDF content
        pdf_data = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n210\n%%EOF"

        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_data)

        logger.info("Temporary PDF created successfully")

        try:
            # Execute the method
            logger.info("Executing journal_instance.run() with document message")
            result = journal_instance.run(message=message, file_path=temp_pdf_path)

            # Verify result
            logger.info(f"Result: {result}")
            assert result is True, (
                "Expected run() to return True for successful posting"
            )

            # Verify GitHub interactions
            logger.info("Verifying GitHub API interactions")

            # Should have called create_file to upload the document
            journal_instance.repo.create_file.assert_called_once()
            create_call_args = journal_instance.repo.create_file.call_args
            logger.debug(f"create_file called with: {create_call_args}")

            # Verify file was uploaded to correct path
            uploaded_path = create_call_args[1]["path"]
            logger.info(f"File uploaded to path: {uploaded_path}")
            assert uploaded_path.startswith("pics/telegram/"), (
                "File should be uploaded to pics/telegram/"
            )

            # Should have called update_file to append journal entry
            journal_instance.repo.update_file.assert_called_once()
            update_call_args = journal_instance.repo.update_file.call_args
            logger.debug(f"update_file called with: {update_call_args}")

            # Verify the content structure
            updated_content = update_call_args[1]["content"]
            logger.info(f"Updated content length: {len(updated_content)} chars")
            logger.debug(f"Updated content:\n{updated_content}")

            # Verify the caption appears in the content
            assert message.caption in updated_content, (
                "Message caption should be in updated content"
            )

            # Verify org-mode file reference format
            assert "[[file:" in updated_content, "Should contain org-mode file link"

            logger.info("File message test PASSED")

        finally:
            # Clean up temporary file
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
                logger.debug(f"Cleaned up temporary file: {temp_pdf_path}")

    @pytest.mark.unit
    @pytest.mark.journal
    def test_get_org_item_format(
        self,
        journal_instance: PostToGitJournal,
        mock_telegram_message_text: Mock,
    ) -> None:
        """
        Test the _get_org_item method returns properly formatted org-mode entry.
        """
        logger.info("=" * 80)
        logger.info("TEST: Verify org-mode item formatting")
        logger.info("=" * 80)

        message = mock_telegram_message_text
        org_item = journal_instance._get_org_item(message)

        logger.info(f"Generated org item:\n{org_item}")

        # Verify format: * Entry: [[link][timestamp]]
        assert org_item.startswith("* Entry:"), "Should start with '* Entry:'"
        assert "[[https://t.me/" in org_item, "Should contain Telegram link"
        assert message.text in org_item, "Should contain message text"

        # Verify timestamp format (YYYY-MM-DD HH:MM)
        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
        assert re.search(timestamp_pattern, org_item), (
            "Should contain timestamp in correct format"
        )

        logger.info("Org-mode formatting test PASSED")
