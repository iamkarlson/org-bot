"""
in this task, I take the message from telegram command, and post it to my journal on github.
I will use the github api to do this.
"""

import logging

from github import Github, Auth
from telegram import Message
from ..org_api import OrgApi

logger = logging.getLogger(__name__)


class BasePostToGitJournal:
    def __init__(self, github_token=None, repo_name=None, file_path=None, org_api=None):
        # Validating config
        self.token = github_token
        if not self.token:
            logger.error("Github token is not provided.")
            raise ValueError("Github token is not provided.")
        self.repo_name = repo_name
        self.file_path = file_path
        if not self.file_path:
            # warning in logs that default file path is used
            logger.warning("File path is not provided. Using default file path.")

        self.client = Github(auth=(Auth.Token(self.token)))
        # Initialize using an access token

        # Get the specific repo and file
        self.repo = self.client.get_repo(self.repo_name)

        # Use provided org_api or create a new one
        self.org_api = org_api if org_api is not None else OrgApi(self.repo)

    def run(self, message: Message, file_path=None, file_paths=None):
        """
        Adds a message to a file on github. File should exist on github.

        Args:
            message: incoming telegram message
            file_path: (deprecated) single file path for backward compatibility
            file_paths: list of file paths for media groups

        Returns:
            status of operation
        """

        # Handle backward compatibility
        if file_path and not file_paths:
            file_paths = [file_path]

        if not file_paths:
            file_paths = []

        # Build message metadata
        message_id = message.message_id
        chat_id = message.chat.id
        commit_message = f"Message {message_id} from chat {chat_id}"
        new_text = self._get_new_org_item(message)

        # If no files, use old simple path for backward compatibility
        if not file_paths:
            logger.info(
                "Creating single-file commit (text only)",
                extra={"message_id": message_id, "chat_id": chat_id}
            )
            self.org_api.append_text_to_file(
                self.file_path,
                new_text,
                commit_message,
                image_filename=None
            )
            return True

        # Have files - use atomic commit for all files + org entry
        file_changes = []
        image_filenames = []

        # Add all photos to file_changes
        for fp in file_paths:
            with open(fp, "rb") as file:
                file_bytes = file.read()
                filename = "pics/telegram/" + fp.split("/")[-1]
                file_changes.append((filename, file_bytes))
                image_filenames.append(filename)

        # Get current org file content
        contents = self.repo.get_contents(self.file_path, ref="main")
        decoded_content = contents.decoded_content.decode("utf-8")

        # Add image links
        image_text = "\n".join([
            f"#+attr_html: :width 600px\n[[file:{fn}]]"
            for fn in image_filenames
        ])
        new_content = "\n".join([decoded_content, new_text, image_text])

        # Add org file to changes
        file_changes.append((self.file_path, new_content))

        # Create atomic commit
        logger.info(
            f"Creating atomic commit for {len(file_changes)} files",
            extra={
                "message_id": message_id,
                "chat_id": chat_id,
                "photo_count": len(image_filenames)
            }
        )
        self.org_api.create_atomic_commit(file_changes, commit_message)

        return True
