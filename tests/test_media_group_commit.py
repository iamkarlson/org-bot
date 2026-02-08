"""
Tests for media group handling - verifying all media files are committed
together with text in a single atomic commit.

These tests ensure that when Telegram sends multiple photos as a media group,
all photos + the org file update happen in ONE commit (no partial commits).
"""

import os
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Any, Dict, List

import pytest

from src.actions.post_to_journal import PostToGitJournal

logger = logging.getLogger(__name__)


def create_mock_photo_message(
    message_id: int,
    caption: str | None = None,
    file_id: str | None = None,
    chat_id: int = 1234567890,
    media_group_id: str | None = None,
) -> Mock:
    """Create a mock Telegram photo message."""
    message = Mock()
    message.message_id = message_id
    message.text = None
    message.caption = caption

    photo = Mock()
    photo.file_id = file_id or f"photo_file_id_{message_id}"
    photo.file_size = 1024 * 50
    photo.width = 800
    photo.height = 600
    message.photo = [photo]

    message.document = None
    message.media_group_id = media_group_id

    chat = Mock()
    chat.id = chat_id
    message.chat = chat

    return message


class TestMediaGroupCommit:
    """Test suite for media group atomic commits."""

    @pytest.fixture
    def mock_github_client(self) -> MagicMock:
        """Create a mock GitHub client with all necessary methods."""
        client = MagicMock()
        mock_repo = MagicMock()
        client.get_repo.return_value = mock_repo

        # Mock file contents
        mock_contents = MagicMock()
        mock_contents.decoded_content = b"* Existing journal entry\nSome content"
        mock_contents.sha = "mock_sha"
        mock_contents.path = "test_journal.org"
        mock_repo.get_contents.return_value = mock_contents

        # Mock Git Tree API for atomic commits
        mock_branch = MagicMock()
        mock_branch.commit.sha = "base_commit_sha"
        mock_repo.get_branch.return_value = mock_branch

        mock_blob = MagicMock()
        mock_blob.sha = "blob_sha"
        mock_repo.create_git_blob.return_value = mock_blob

        mock_base_tree = MagicMock()
        mock_base_tree.sha = "base_tree_sha"
        mock_repo.get_git_tree.return_value = mock_base_tree

        mock_new_tree = MagicMock()
        mock_new_tree.sha = "new_tree_sha"
        mock_repo.create_git_tree.return_value = mock_new_tree

        mock_parent_commit = MagicMock()
        mock_repo.get_git_commit.return_value = mock_parent_commit

        mock_commit = MagicMock()
        mock_commit.sha = "atomic_commit_sha"
        mock_repo.create_git_commit.return_value = mock_commit

        mock_ref = MagicMock()
        mock_repo.get_git_ref.return_value = mock_ref

        return client

    @pytest.fixture
    def journal_instance(
        self, mock_github_client: MagicMock, test_config: Dict[str, Any]
    ) -> PostToGitJournal:
        """Create a PostToGitJournal instance with mocked GitHub client."""
        with patch(
            "src.actions.base_post_to_org_file.Github", return_value=mock_github_client
        ):
            instance = PostToGitJournal(
                github_token=test_config["github_token"],
                repo_name=test_config["github_repo"],
                file_path=test_config["journal_file"],
            )
        return instance

    def _create_temp_images(self, count: int) -> List[str]:
        """Create temporary image files for testing."""
        # Minimal valid PNG data
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        paths = []
        for i in range(count):
            path = f"/tmp/test_media_group_photo_{i}.png"
            with open(path, "wb") as f:
                f.write(png_data)
            paths.append(path)
        return paths

    def _cleanup_temp_images(self, paths: List[str]) -> None:
        """Clean up temporary image files."""
        for path in paths:
            if os.path.exists(path):
                os.remove(path)

    @pytest.mark.unit
    @pytest.mark.journal
    @pytest.mark.picture
    def test_multiple_photos_committed_together(
        self,
        journal_instance: PostToGitJournal,
    ) -> None:
        """
        Test that multiple photos are committed in a single atomic commit.

        This verifies the core requirement: when a media group with N photos
        is posted, all N photos + the org file update happen in ONE commit.
        """
        logger.info("=" * 80)
        logger.info("TEST: Multiple photos committed together")
        logger.info("=" * 80)

        # Create 3 temporary test images
        temp_paths = self._create_temp_images(3)

        # Create mock message with caption
        message = create_mock_photo_message(
            message_id=100,
            caption="Caption for the media group",
            media_group_id="mg_12345",
        )

        try:
            with patch.object(
                journal_instance.org_api,
                "create_atomic_commit",
                wraps=journal_instance.org_api.create_atomic_commit,
            ) as mock_atomic_commit:
                result = journal_instance.run(message=message, file_paths=temp_paths)

            assert result is True

            # Verify atomic commit was called exactly once
            mock_atomic_commit.assert_called_once()

            file_changes, commit_message = mock_atomic_commit.call_args.args

            # Verify all 3 photos + 1 org file = 4 files in the commit
            assert len(file_changes) == 4, (
                f"Expected 4 files (3 photos + 1 org), got {len(file_changes)}"
            )

            # Extract paths from file_changes
            paths = [path for path, _ in file_changes]

            # Verify all photos are in pics/telegram/
            photo_paths = [p for p in paths if p.startswith("pics/telegram/")]
            assert len(photo_paths) == 3, (
                f"Expected 3 photo paths, got {len(photo_paths)}"
            )

            # Verify org file is included
            assert journal_instance.file_path in paths

            logger.info(f"Commit includes {len(file_changes)} files")
            logger.info(f"Photo paths: {photo_paths}")
            logger.info("TEST PASSED: All photos committed together")

        finally:
            self._cleanup_temp_images(temp_paths)

    @pytest.mark.unit
    @pytest.mark.journal
    @pytest.mark.picture
    def test_all_image_links_in_org_content(
        self,
        journal_instance: PostToGitJournal,
    ) -> None:
        """
        Test that all image links are added to the org file content.

        Each photo should have its own [[file:...]] link in the org file.
        """
        logger.info("=" * 80)
        logger.info("TEST: All image links in org content")
        logger.info("=" * 80)

        temp_paths = self._create_temp_images(3)
        message = create_mock_photo_message(
            message_id=101,
            caption="Testing image links",
            media_group_id="mg_links",
        )

        try:
            with patch.object(
                journal_instance.org_api,
                "create_atomic_commit",
                wraps=journal_instance.org_api.create_atomic_commit,
            ) as mock_atomic_commit:
                journal_instance.run(message=message, file_paths=temp_paths)

            file_changes, _ = mock_atomic_commit.call_args.args

            # Get the org file content
            org_content = next(
                content
                for path, content in file_changes
                if path == journal_instance.file_path
            )

            # Verify each image has a [[file:]] link
            for temp_path in temp_paths:
                filename = temp_path.split("/")[-1]
                expected_link = f"[[file:pics/telegram/{filename}]]"
                assert expected_link in org_content, (
                    f"Missing link for {filename}"
                )

            # Verify #+attr_html for each image
            attr_count = org_content.count("#+attr_html:")
            assert attr_count == 3, (
                f"Expected 3 #+attr_html lines, got {attr_count}"
            )

            logger.info("All 3 image links found in org content")
            logger.info("TEST PASSED")

        finally:
            self._cleanup_temp_images(temp_paths)

    @pytest.mark.unit
    @pytest.mark.journal
    @pytest.mark.picture
    def test_caption_included_with_media_group(
        self,
        journal_instance: PostToGitJournal,
    ) -> None:
        """
        Test that the caption text is included in the org entry.
        """
        logger.info("=" * 80)
        logger.info("TEST: Caption included with media group")
        logger.info("=" * 80)

        temp_paths = self._create_temp_images(2)
        caption_text = "This is the caption for my photo album"
        message = create_mock_photo_message(
            message_id=102,
            caption=caption_text,
            media_group_id="mg_caption",
        )

        try:
            with patch.object(
                journal_instance.org_api,
                "create_atomic_commit",
                wraps=journal_instance.org_api.create_atomic_commit,
            ) as mock_atomic_commit:
                journal_instance.run(message=message, file_paths=temp_paths)

            file_changes, _ = mock_atomic_commit.call_args.args

            org_content = next(
                content
                for path, content in file_changes
                if path == journal_instance.file_path
            )

            assert caption_text in org_content, "Caption not found in org content"
            logger.info("Caption found in org content")
            logger.info("TEST PASSED")

        finally:
            self._cleanup_temp_images(temp_paths)

    @pytest.mark.unit
    @pytest.mark.journal
    @pytest.mark.picture
    def test_single_commit_for_large_media_group(
        self,
        journal_instance: PostToGitJournal,
    ) -> None:
        """
        Test that even a large media group (10 photos) results in a single commit.

        This is the maximum Telegram allows per album.
        """
        logger.info("=" * 80)
        logger.info("TEST: Single commit for large media group (10 photos)")
        logger.info("=" * 80)

        temp_paths = self._create_temp_images(10)
        message = create_mock_photo_message(
            message_id=103,
            caption="Large album with 10 photos",
            media_group_id="mg_large",
        )

        try:
            with patch.object(
                journal_instance.org_api,
                "create_atomic_commit",
                wraps=journal_instance.org_api.create_atomic_commit,
            ) as mock_atomic_commit:
                result = journal_instance.run(message=message, file_paths=temp_paths)

            assert result is True

            # Must be exactly one atomic commit call
            assert mock_atomic_commit.call_count == 1, (
                f"Expected 1 commit, got {mock_atomic_commit.call_count}"
            )

            file_changes, _ = mock_atomic_commit.call_args.args

            # 10 photos + 1 org file = 11 files
            assert len(file_changes) == 11, (
                f"Expected 11 files, got {len(file_changes)}"
            )

            logger.info(f"Single commit with {len(file_changes)} files")
            logger.info("TEST PASSED")

        finally:
            self._cleanup_temp_images(temp_paths)

    @pytest.mark.unit
    @pytest.mark.journal
    @pytest.mark.picture
    def test_binary_content_for_photos(
        self,
        journal_instance: PostToGitJournal,
    ) -> None:
        """
        Test that photo content is passed as binary (bytes), not string.

        Photos should be base64 encoded when creating blobs.
        """
        logger.info("=" * 80)
        logger.info("TEST: Binary content for photos")
        logger.info("=" * 80)

        temp_paths = self._create_temp_images(2)
        message = create_mock_photo_message(
            message_id=104,
            caption="Binary test",
            media_group_id="mg_binary",
        )

        try:
            with patch.object(
                journal_instance.org_api,
                "create_atomic_commit",
                wraps=journal_instance.org_api.create_atomic_commit,
            ) as mock_atomic_commit:
                journal_instance.run(message=message, file_paths=temp_paths)

            file_changes, _ = mock_atomic_commit.call_args.args

            for path, content in file_changes:
                if path.startswith("pics/telegram/"):
                    assert isinstance(content, bytes), (
                        f"Photo content should be bytes, got {type(content)}"
                    )
                elif path.endswith(".org"):
                    assert isinstance(content, str), (
                        f"Org content should be str, got {type(content)}"
                    )

            logger.info("Photo content is bytes, org content is str")
            logger.info("TEST PASSED")

        finally:
            self._cleanup_temp_images(temp_paths)

    @pytest.mark.unit
    @pytest.mark.journal
    def test_no_photos_uses_simple_update(
        self,
        journal_instance: PostToGitJournal,
        mock_telegram_message_text: Mock,
    ) -> None:
        """
        Test that text-only messages don't use atomic commit (optimization).

        Text-only messages should use the simpler update_file path.
        """
        logger.info("=" * 80)
        logger.info("TEST: No photos uses simple update")
        logger.info("=" * 80)

        with patch.object(
            journal_instance.org_api,
            "create_atomic_commit",
        ) as mock_atomic_commit, patch.object(
            journal_instance.org_api,
            "append_text_to_file",
        ) as mock_append:
            result = journal_instance.run(
                message=mock_telegram_message_text,
                file_paths=None,
            )

        assert result is True

        # Atomic commit should NOT be called for text-only messages
        mock_atomic_commit.assert_not_called()

        # Instead, append_text_to_file should be used
        mock_append.assert_called_once()

        logger.info("Text-only message used simple update path")
        logger.info("TEST PASSED")
