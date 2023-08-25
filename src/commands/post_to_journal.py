"""
in this task, I take the message from telegram command, and post it to my journal on github.
I will use the github api to do this.
"""
import logging

from github import Github, Auth
from telegram import Message

logger = logging.getLogger(__name__)


class PostToGitJournal:
    def __init__(self, github_token=None, repo_name=None, file_path=None):
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

    def run(self, message: Message):
        """
        Adds a message to the journal on github. File should exists on the github.
        :param message: incoming telegram message
        :return: status of operation
        """
        message_id = message.message_id
        chat_id = message.chat.id
        commit_message = f"Message {message_id} from chat {chat_id}"
        new_text = self._get_text_from_message(message)
        self._append_text_to_file(new_text, commit_message)
        return True

    def _append_text_to_file(self, new_text, commit_message: str):
        contents = self.repo.get_contents(
            self.file_path, ref="main"
        )  # Assuming you're working on the 'main' branch

        # Decode the content and append new text
        decoded_content = contents.decoded_content.decode("utf-8")
        new_content = decoded_content + new_text
        # Update the file in the repository
        self.repo.update_file(
            path=contents.path,
            message=commit_message,
            content=new_content,
            sha=contents.sha,
            branch="main",
        )

    @staticmethod
    def _get_text_from_message(message: Message) -> str:
        """
        In this method, I'm making an message for my org-mode journal.
        It includes title "log entry" and link to the message.
        Text of the message is written in the next line.
        """
        message_id = message.message_id
        chat_id = message.chat.id
        message_link = f"https://t.me/c/{chat_id}/{message_id}"
        message_text = message.text
        return f"* Log entry: {message_link}\n{message_text}\n"
