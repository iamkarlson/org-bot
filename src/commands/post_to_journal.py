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
                    commit_message="Image from telegram"
                )

        message_id = message.message_id
        chat_id = message.chat.id
        commit_message = f"Message {message_id} from chat {chat_id}"
        new_text = self._get_org_item(message)
        self.org_api.append_text_to_file(
            self.file_path,
            new_text,
            commit_message,
            image_filename=filename
        )
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


class PostReplyToEntry(BasePostToGitJournal):
    """
    Handles reply messages by looking up the original message in journal/todo files
    and adding the reply as a subheader (child entry).
    """

    def __init__(self, github_token=None, repo_name=None, file_path=None, todo_file_path=None, org_api=None):
        super().__init__(github_token, repo_name, file_path, org_api=org_api)
        self.todo_file_path = todo_file_path

    def run(self, message: Message, file_path=None):
        """
        Handles a reply message by finding the original entry and adding this as a subheader.
        Falls back to regular journal entry if original message is not found.

        :param message: The reply message from Telegram
        :param file_path: Optional file path for attachments
        :return: Status of operation
        """
        # Get the original message that this is replying to
        original_message = message.reply_to_message
        if not original_message:
            # Not a reply, fall back to regular journal entry
            logger.warning("PostReplyToEntry called without reply_to_message")
            return PostToGitJournal(self.token, self.repo_name, self.file_path).run(message, file_path)

        # Build the link to the original message
        original_message_id = original_message.message_id
        original_chat_id = original_message.chat.id
        original_message_link = f"https://t.me/c/{original_chat_id}/{original_message_id}"

        logger.info(
            f"Processing reply to message {original_message_id}",
            extra={
                "original_message_id": original_message_id,
                "original_link": original_message_link
            }
        )

        # Search for the original entry in journal file first, then todo file
        entry_location = None
        search_files = [
            (self.file_path, "journal"),
            (self.todo_file_path, "todo")
        ]

        for search_file, file_type in search_files:
            if search_file:
                entry_location = self.org_api.find_original_entry(original_message_link, search_file)
                if entry_location:
                    logger.info(f"Found original entry in {file_type} file")
                    file_to_update = search_file
                    break

        if not entry_location:
            # Original message not found, add as regular journal entry
            logger.info("Original entry not found, falling back to regular journal entry")
            return PostToGitJournal(self.token, self.repo_name, self.file_path).run(message, file_path)

        line_number, org_level = entry_location

        # Find the top-level (non-reply) entry to ensure all replies are at same level
        top_line_number, top_org_level = self.org_api.find_top_level_entry(
            file_to_update, line_number, org_level
        )

        # Create the reply entry as a subheader (one level deeper than top-level)
        reply_level = top_org_level + 1
        asterisks = "*" * reply_level

        message_id = message.message_id
        chat_id = message.chat.id
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        message_link = f"https://t.me/c/{chat_id}/{message_id}"
        message_text = get_text_from_message(message)

        reply_text = f"{asterisks} Reply: [[{message_link}][{now}]]\n{message_text}"

        commit_message = f"Reply to message {original_message_id} from chat {chat_id}"

        # Insert the reply after the original entry
        # Note: We insert after the found entry (line_number) but use top_org_level
        # to determine where to insert (before next entry at same level as top-level)
        self.org_api.insert_reply_after_entry(
            file_to_update,
            top_line_number,
            top_org_level,
            reply_text,
            commit_message
        )

        return True
