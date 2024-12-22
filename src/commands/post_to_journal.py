"""
in this task, I take the message from telegram command, and post it to my journal on github.
I will use the github api to do this.
"""

import logging
from datetime import datetime

from github import Github, Auth
from telegram import Message
from utils import get_text_from_message

logger = logging.getLogger(__name__)


class BasePostToGitJournal:
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

    def _append_text_to_file(
        self, new_text: str, commit_message: str, filename: str = None
    ):
        logger.info(
            "Appending text to file.",
            extra={
                "action": "append_text",
                "commit_message": commit_message,
                "message": new_text,
            },
        )

        contents = self.repo.get_contents(
            self.file_path, ref="main"
        )  # Assuming you're working on the 'main' branch

        # Decode the content and append new text
        decoded_content = contents.decoded_content.decode("utf-8")
        if filename:
            # [[file:pics/minecraft_sorter_scheme_b.png]]
            image_text = f"#+attr_html: :width 600px\n[[file:{filename}]]"
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
                self.repo.create_file(
                    path=filename,
                    message="Image from telegram",
                    content=file_bytes,
                    branch="main",
                )

        message_id = message.message_id
        chat_id = message.chat.id
        commit_message = f"Message {message_id} from chat {chat_id}"
        new_text = self._get_org_item(message)
        self._append_text_to_file(new_text, commit_message, filename)
        return True


class PostToTodo(BasePostToGitJournal):
    """
    This is a simple override to post TODOs to a different file
    """

    @staticmethod
    def _get_org_item(message: Message) -> str:
        """
        In this method, I'm making an message for my org-mode journal.
        It includes title "log entry" and link to the message.
        Text of the message is written in the next line.
        """
        message_id = message.message_id
        chat_id = message.chat.id
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        message_link = f"https://t.me/c/{chat_id}/{message_id}"
        # trimming TODO from the message, I may want to use different tags later on
        message_text = get_text_from_message(message)
        message_text = message_text[5:]
        return f"** TODO {message_text}\nCreated at: [{now}] from {message_link}"


class PostToGitJournal(BasePostToGitJournal):

    @staticmethod
    def _get_org_item(message: Message) -> str:
        """
        In this method, I'm making an message for my org-mode journal.
        It includes title "log entry" and link to the message.
        Text of the message is written in the next line.
        """
        message_id = message.message_id
        chat_id = message.chat.id
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        message_link = f"https://t.me/c/{chat_id}/{message_id}"
        message_text = get_text_from_message(message)
        return f"* Entry: [[{message_link}][{now}]]\n{message_text}"
