"""Tests for atomic commit functionality."""
import pytest
from unittest.mock import Mock, MagicMock
from src.org_api import OrgApi


def test_create_atomic_commit_multiple_files():
    """Test creating a single commit with multiple files."""
    # Mock GitHub repo
    mock_repo = MagicMock()

    # Mock branch
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_commit_sha"
    mock_repo.get_branch.return_value = mock_branch

    # Mock blob creation
    mock_blob = MagicMock()
    mock_blob.sha = "blob_sha"
    mock_repo.create_git_blob.return_value = mock_blob

    # Mock tree creation
    mock_base_tree = MagicMock()
    mock_base_tree.sha = "base_tree_sha"
    mock_repo.get_git_tree.return_value = mock_base_tree

    mock_new_tree = MagicMock()
    mock_new_tree.sha = "new_tree_sha"
    mock_repo.create_git_tree.return_value = mock_new_tree

    # Mock commit creation
    mock_parent_commit = MagicMock()
    mock_parent_commit.sha = "parent_sha"
    mock_repo.get_git_commit.return_value = mock_parent_commit

    mock_commit = MagicMock()
    mock_commit.sha = "new_commit_sha"
    mock_repo.create_git_commit.return_value = mock_commit

    # Mock ref update
    mock_ref = MagicMock()
    mock_repo.get_git_ref.return_value = mock_ref

    # Create OrgApi and test
    org_api = OrgApi(mock_repo)

    file_changes = [
        ("pics/telegram/photo1.jpg", b"fake_image_1_data"),
        ("pics/telegram/photo2.jpg", b"fake_image_2_data"),
        ("journal.org", "* New entry\n** Subentry\n")
    ]

    commit_sha = org_api.create_atomic_commit(
        file_changes,
        "Message 123 from chat 456"
    )

    # Assertions
    assert commit_sha == "new_commit_sha"
    assert mock_repo.create_git_blob.call_count == 3
    assert mock_repo.create_git_tree.called
    assert mock_repo.create_git_commit.called
    assert mock_ref.edit.called

    # Verify commit message
    mock_repo.create_git_commit.assert_called_once()
    call_args = mock_repo.create_git_commit.call_args
    assert call_args[1]["message"] == "Message 123 from chat 456"


def test_create_atomic_commit_text_only():
    """Test atomic commit with text files only."""
    # Mock GitHub repo
    mock_repo = MagicMock()

    # Setup mocks
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_blob = MagicMock()
    mock_blob.sha = "text_blob_sha"
    mock_repo.create_git_blob.return_value = mock_blob

    mock_base_tree = MagicMock()
    mock_repo.get_git_tree.return_value = mock_base_tree

    mock_new_tree = MagicMock()
    mock_new_tree.sha = "tree_sha"
    mock_repo.create_git_tree.return_value = mock_new_tree

    mock_parent = MagicMock()
    mock_repo.get_git_commit.return_value = mock_parent

    mock_commit = MagicMock()
    mock_commit.sha = "text_commit_sha"
    mock_repo.create_git_commit.return_value = mock_commit

    mock_ref = MagicMock()
    mock_repo.get_git_ref.return_value = mock_ref

    # Create OrgApi
    org_api = OrgApi(mock_repo)

    file_changes = [
        ("journal.org", "* Entry 1\n"),
        ("todo.org", "** TODO Task\n")
    ]

    commit_sha = org_api.create_atomic_commit(
        file_changes,
        "Update org files"
    )

    assert commit_sha == "text_commit_sha"
    assert mock_repo.create_git_blob.call_count == 2


def test_create_atomic_commit_binary_only():
    """Test atomic commit with binary files only."""
    # Mock GitHub repo
    mock_repo = MagicMock()

    # Setup mocks
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_blob = MagicMock()
    mock_blob.sha = "binary_blob_sha"
    mock_repo.create_git_blob.return_value = mock_blob

    mock_base_tree = MagicMock()
    mock_repo.get_git_tree.return_value = mock_base_tree

    mock_new_tree = MagicMock()
    mock_new_tree.sha = "tree_sha"
    mock_repo.create_git_tree.return_value = mock_new_tree

    mock_parent = MagicMock()
    mock_repo.get_git_commit.return_value = mock_parent

    mock_commit = MagicMock()
    mock_commit.sha = "binary_commit_sha"
    mock_repo.create_git_commit.return_value = mock_commit

    mock_ref = MagicMock()
    mock_repo.get_git_ref.return_value = mock_ref

    # Create OrgApi
    org_api = OrgApi(mock_repo)

    file_changes = [
        ("pics/photo1.jpg", b"\x89PNG\r\n\x1a\n...fake_png_data"),
        ("pics/photo2.jpg", b"\xff\xd8\xff...fake_jpeg_data")
    ]

    commit_sha = org_api.create_atomic_commit(
        file_changes,
        "Add photos"
    )

    assert commit_sha == "binary_commit_sha"
    assert mock_repo.create_git_blob.call_count == 2

    # Verify binary content was base64 encoded
    for call in mock_repo.create_git_blob.call_args_list:
        encoding = call[0][1]
        assert encoding == "base64"


def test_create_atomic_commit_mixed_content():
    """Test atomic commit with both text and binary files."""
    # Mock GitHub repo
    mock_repo = MagicMock()

    # Setup mocks
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_blob = MagicMock()
    mock_blob.sha = "blob_sha"
    mock_repo.create_git_blob.return_value = mock_blob

    mock_base_tree = MagicMock()
    mock_repo.get_git_tree.return_value = mock_base_tree

    mock_new_tree = MagicMock()
    mock_new_tree.sha = "tree_sha"
    mock_repo.create_git_tree.return_value = mock_new_tree

    mock_parent = MagicMock()
    mock_repo.get_git_commit.return_value = mock_parent

    mock_commit = MagicMock()
    mock_commit.sha = "mixed_commit_sha"
    mock_repo.create_git_commit.return_value = mock_commit

    mock_ref = MagicMock()
    mock_repo.get_git_ref.return_value = mock_ref

    # Create OrgApi
    org_api = OrgApi(mock_repo)

    file_changes = [
        ("pics/photo.jpg", b"binary_data"),
        ("journal.org", "text content")
    ]

    commit_sha = org_api.create_atomic_commit(
        file_changes,
        "Mixed commit"
    )

    assert commit_sha == "mixed_commit_sha"
    assert mock_repo.create_git_blob.call_count == 2

    # Verify first call was base64 (binary), second was utf-8 (text)
    calls = mock_repo.create_git_blob.call_args_list
    assert calls[0][0][1] == "base64"
    assert calls[1][0][1] == "utf-8"


def test_create_atomic_commit_single_file():
    """Test atomic commit with a single file (edge case)."""
    # Mock GitHub repo
    mock_repo = MagicMock()

    # Setup mocks
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_blob = MagicMock()
    mock_blob.sha = "blob_sha"
    mock_repo.create_git_blob.return_value = mock_blob

    mock_base_tree = MagicMock()
    mock_repo.get_git_tree.return_value = mock_base_tree

    mock_new_tree = MagicMock()
    mock_new_tree.sha = "tree_sha"
    mock_repo.create_git_tree.return_value = mock_new_tree

    mock_parent = MagicMock()
    mock_repo.get_git_commit.return_value = mock_parent

    mock_commit = MagicMock()
    mock_commit.sha = "single_commit_sha"
    mock_repo.create_git_commit.return_value = mock_commit

    mock_ref = MagicMock()
    mock_repo.get_git_ref.return_value = mock_ref

    # Create OrgApi
    org_api = OrgApi(mock_repo)

    file_changes = [
        ("journal.org", "* Single entry\n")
    ]

    commit_sha = org_api.create_atomic_commit(
        file_changes,
        "Single file commit"
    )

    assert commit_sha == "single_commit_sha"
    assert mock_repo.create_git_blob.call_count == 1


def test_create_atomic_commit_verifies_tree_elements():
    """Test that tree elements are created correctly."""
    # Mock GitHub repo
    mock_repo = MagicMock()

    # Setup mocks
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_blob = MagicMock()
    mock_blob.sha = "blob_sha_123"
    mock_repo.create_git_blob.return_value = mock_blob

    mock_base_tree = MagicMock()
    mock_repo.get_git_tree.return_value = mock_base_tree

    mock_new_tree = MagicMock()
    mock_new_tree.sha = "tree_sha"
    mock_repo.create_git_tree.return_value = mock_new_tree

    mock_parent = MagicMock()
    mock_repo.get_git_commit.return_value = mock_parent

    mock_commit = MagicMock()
    mock_commit.sha = "commit_sha"
    mock_repo.create_git_commit.return_value = mock_commit

    mock_ref = MagicMock()
    mock_repo.get_git_ref.return_value = mock_ref

    # Create OrgApi
    org_api = OrgApi(mock_repo)

    file_changes = [
        ("test/file.txt", "content")
    ]

    org_api.create_atomic_commit(file_changes, "Test commit")

    # Verify create_git_tree was called with proper arguments
    assert mock_repo.create_git_tree.called
    call_args = mock_repo.create_git_tree.call_args

    # Check that tree_elements were passed
    tree_elements = call_args[1]["tree"]
    assert len(tree_elements) == 1

    # Check that base_tree was passed
    base_tree = call_args[1]["base_tree"]
    assert base_tree == mock_base_tree


def test_create_atomic_commit_updates_ref():
    """Test that the branch ref is updated correctly."""
    # Mock GitHub repo
    mock_repo = MagicMock()

    # Setup mocks
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_sha"
    mock_repo.get_branch.return_value = mock_branch

    mock_blob = MagicMock()
    mock_blob.sha = "blob_sha"
    mock_repo.create_git_blob.return_value = mock_blob

    mock_base_tree = MagicMock()
    mock_repo.get_git_tree.return_value = mock_base_tree

    mock_new_tree = MagicMock()
    mock_new_tree.sha = "tree_sha"
    mock_repo.create_git_tree.return_value = mock_new_tree

    mock_parent = MagicMock()
    mock_repo.get_git_commit.return_value = mock_parent

    mock_commit = MagicMock()
    mock_commit.sha = "final_commit_sha"
    mock_repo.create_git_commit.return_value = mock_commit

    mock_ref = MagicMock()
    mock_repo.get_git_ref.return_value = mock_ref

    # Create OrgApi
    org_api = OrgApi(mock_repo)

    file_changes = [("test.txt", "test")]

    org_api.create_atomic_commit(file_changes, "Test")

    # Verify ref was fetched and edited
    mock_repo.get_git_ref.assert_called_once_with("heads/main")
    mock_ref.edit.assert_called_once_with(sha="final_commit_sha")
