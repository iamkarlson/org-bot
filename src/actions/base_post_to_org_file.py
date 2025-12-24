"""
in this task, I take the message from telegram command, and post it to my journal on github.
I will use the github api to do this.
"""

import logging
import re
from datetime import datetime

from github import Github, Auth
from telegram import Message
from ..utils import get_text_from_message
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

    def run(self, message: Message, file_path=None):
        """
        Adds a message to a file on github. File should exists on the github.
        :param message: incoming telegram message
        :return: status of operation
        """

        filename = None
        if file_path:
            # we got a file. Now it has to be uploaded to the repo as bytes
            with open(file_path, "rb") as file:
                file_bytes = file.read()
                filename = "pics/telegram/" + file_path.split("/")[-1]
                self.org_api.create_file(
                    file_path=filename,
                    content=file_bytes,
                    commit_message="Image from telegram",
                )

        message_id = message.message_id
        chat_id = message.chat.id
        commit_message = f"Message {message_id} from chat {chat_id}"
        new_text = self._get_org_item(message)
        self.org_api.append_text_to_file(
            self.file_path, new_text, commit_message, image_filename=filename
        )
        return True
