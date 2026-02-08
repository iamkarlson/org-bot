"""
OrgApi - A class for manipulating org-mode files.

This class provides methods for:
- Finding entries in org files by message links
- Finding top-level (non-reply) entries
- Inserting replies at the correct position in the org hierarchy
"""

import base64
import logging
import re
from typing import List, Optional, Tuple, Union

from github import InputGitTreeElement

logger = logging.getLogger(__name__)


class OrgApi:
    """API for manipulating org-mode files in a GitHub repository."""

    def __init__(self, repo):
        """
        Initialize OrgApi with a GitHub repository object.

        :param repo: GitHub repository object with get_contents and update_file methods
        """
        self.repo = repo

    def create_atomic_commit(
        self,
        file_changes: List[Tuple[str, Union[str, bytes]]],
        commit_message: str,
    ) -> str:
        """
        Create a single commit with multiple file changes.

        Uses the GitHub Git Tree API to create an atomic commit containing
        multiple file changes (both text and binary). This is useful for
        committing multiple photos + org file update in one transaction.

        Args:
            file_changes: List of (file_path, content) tuples.
                         Content can be str (for text files) or bytes (for binary files).
            commit_message: Git commit message

        Returns:
            Commit SHA string

        Example:
            file_changes = [
                ("pics/telegram/photo1.jpg", photo1_bytes),
                ("pics/telegram/photo2.jpg", photo2_bytes),
                ("journal.org", updated_org_content_str)
            ]
            sha = org_api.create_atomic_commit(file_changes, "Message 123 from chat 456")
        """
        repo = self.repo
        branch = repo.get_branch("main")

        logger.info(
            f"Creating atomic commit with {len(file_changes)} file(s)",
            extra={
                "action": "atomic_commit",
                "file_count": len(file_changes),
                "commit_message": commit_message,
            },
        )

        # Create blobs and tree elements for each file
        tree_elements = []
        for file_path, content in file_changes:
            # Convert content to proper format for blob creation
            if isinstance(content, bytes):
                # For binary content, encode as base64
                blob_content = base64.b64encode(content).decode("ascii")
                blob = repo.create_git_blob(blob_content, "base64")
            else:
                # For text content, use as-is
                blob = repo.create_git_blob(content, "utf-8")

            # Create tree element
            tree_element = InputGitTreeElement(
                path=file_path,
                mode="100644",  # Regular file
                type="blob",
                sha=blob.sha,
            )
            tree_elements.append(tree_element)

        # Create tree with base
        base_tree = repo.get_git_tree(sha=branch.commit.sha)
        new_tree = repo.create_git_tree(tree=tree_elements, base_tree=base_tree)

        # Create commit
        parent = repo.get_git_commit(branch.commit.sha)
        commit = repo.create_git_commit(
            message=commit_message, tree=new_tree, parents=[parent]
        )

        # Update branch ref
        ref = repo.get_git_ref("heads/main")
        ref.edit(sha=commit.sha)

        logger.info(
            f"Atomic commit created: {commit.sha}",
            extra={"commit_sha": commit.sha, "files": [fc[0] for fc in file_changes]},
        )

        return commit.sha

    def find_original_entry(
        self, original_message_link: str, file_path: str
    ) -> Optional[Tuple[int, int]]:
        """
        Searches for the original message in the specified file.
        Returns (line_number, org_level) if found, None otherwise.

        :param original_message_link: The Telegram message link to search for
        :param file_path: The file to search in (journal.org or todo.org)
        :return: Tuple of (line_number, org_level) or None
        """
        try:
            contents = self.repo.get_contents(file_path, ref="main")
            decoded_content = contents.decoded_content.decode("utf-8")
            lines = decoded_content.split("\n")

            for i, line in enumerate(lines):
                if original_message_link in line:
                    # Determine the org-mode level (count asterisks at the start)
                    match = re.match(r"^(\*+)\s", line)
                    if match:
                        org_level = len(match.group(1))
                        logger.info(
                            f"Found original entry at line {i} with level {org_level} in {file_path}"
                        )
                        return (i, org_level)

            logger.info(f"Original message not found in {file_path}")
            return None

        except Exception as e:
            logger.warning(f"Could not search {file_path}: {e}")
            return None

    def find_top_level_entry(
        self, file_path: str, start_line: int, current_level: int
    ) -> Tuple[int, int]:
        """
        Find the top-level (non-reply) entry by searching backwards from the current position.
        This ensures all replies are at the same level, regardless of whether replying to
        an original entry or to another reply.

        :param file_path: The file to search in
        :param start_line: Line number to start searching from
        :param current_level: Current org-mode level
        :return: Tuple of (line_number, org_level) for the top-level entry
        """
        contents = self.repo.get_contents(file_path, ref="main")
        decoded_content = contents.decoded_content.decode("utf-8")
        lines = decoded_content.split("\n")

        # Check if current entry is itself a reply
        if "Reply:" not in lines[start_line]:
            # Not a reply, this is the top-level entry
            return (start_line, current_level)

        # Search backwards for the first non-reply entry with lower level
        for i in range(start_line - 1, -1, -1):
            match = re.match(r"^(\*+)\s", lines[i])
            if match:
                line_level = len(match.group(1))
                # Found an entry with lower level
                if line_level < current_level:
                    # Check if it's not a reply
                    if "Reply:" not in lines[i]:
                        logger.info(
                            f"Found top-level entry at line {i} with level {line_level} in {file_path}"
                        )
                        return (i, line_level)

        # If we didn't find a parent, the current entry is top-level
        return (start_line, current_level)

    def insert_reply_after_entry(
        self,
        file_path: str,
        line_number: int,
        org_level: int,
        reply_text: str,
        commit_message: str,
    ):
        """
        Inserts a reply as a subheader after the original entry.

        :param file_path: The file to modify
        :param line_number: Line number where original entry was found
        :param org_level: Org-mode level of the original entry
        :param reply_text: The formatted reply text
        :param commit_message: Git commit message
        """
        contents = self.repo.get_contents(file_path, ref="main")
        decoded_content = contents.decoded_content.decode("utf-8")
        lines = decoded_content.split("\n")

        # Find the end of the original entry (next entry of same or higher level, or end of file)
        insert_position = line_number + 1

        # Look for the next line that starts with asterisks of equal or lesser count
        for i in range(line_number + 1, len(lines)):
            match = re.match(r"^(\*+)\s", lines[i])
            if match and len(match.group(1)) <= org_level:
                insert_position = i
                break
            insert_position = i + 1

        # Insert the reply at the calculated position
        lines.insert(insert_position, reply_text)

        new_content = "\n".join(lines)

        # Update the file in the repository
        self.repo.update_file(
            path=contents.path,
            message=commit_message,
            content=new_content,
            sha=contents.sha,
            branch="main",
        )

        logger.info(
            f"Inserted reply at line {insert_position} in {file_path}",
            extra={
                "action": "insert_reply",
                "file": file_path,
                "line": insert_position,
                "org_level": org_level + 1,
            },
        )

    def create_file(self, file_path: str, content: bytes, commit_message: str):
        """
        Creates a new file in the repository.

        :param file_path: The path where the file should be created
        :param content: The file content as bytes
        :param commit_message: Git commit message
        """
        logger.info(
            f"Creating file: {file_path}",
            extra={
                "action": "create_file",
                "file_path": file_path,
                "commit_message": commit_message,
            },
        )

        self.repo.create_file(
            path=file_path,
            message=commit_message,
            content=content,
            branch="main",
        )

    def append_text_to_file(
        self,
        file_path: str,
        new_text: str,
        commit_message: str,
        image_filename: Optional[str] = None,
    ):
        """
        Appends text to an org file in the repository.

        :param file_path: The file to append to
        :param new_text: The text to append
        :param commit_message: Git commit message
        :param image_filename: Optional image filename to include as org-mode link
        """
        logger.info(
            "Appending text to file.",
            extra={
                "action": "append_text",
                "commit_message": commit_message,
                "new_text": new_text,
            },
        )

        contents = self.repo.get_contents(file_path, ref="main")

        # Decode the content and append new text
        decoded_content = contents.decoded_content.decode("utf-8")
        if image_filename:
            # [[file:pics/minecraft_sorter_scheme_b.png]]
            image_text = f"#+attr_html: :width 600px\n[[file:{image_filename}]]"
            new_content = "\n".join([decoded_content, new_text, image_text])
        else:
            new_content = "\n".join([decoded_content, new_text])

        # Update the file in the repository
        self.repo.update_file(
            path=contents.path,
            message=commit_message,
            content=new_content,
            sha=contents.sha,
            branch="main",
        )
