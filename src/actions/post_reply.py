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

from ..base_post_to_org_file import BasePostToGitJournal

logger = logging.getLogger(__name__)


class PostReplyToEntry(BasePostToGitJournal):
    """
    Handles reply messages by looking up the original message in journal/todo files
    and adding the reply as a subheader (child entry).
    """

    def __init__(
        self,
        github_token=None,
        repo_name=None,
        file_path=None,
        todo_file_path=None,
        org_api=None,
    ):
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
            return PostToGitJournal(self.token, self.repo_name, self.file_path).run(
                message, file_path
            )

        # Build the link to the original message
        original_message_id = original_message.message_id
        original_chat_id = original_message.chat.id
        original_message_link = (
            f"https://t.me/c/{original_chat_id}/{original_message_id}"
        )

        logger.info(
            f"Processing reply to message {original_message_id}",
            extra={
                "original_message_id": original_message_id,
                "original_link": original_message_link,
            },
        )

        # Search for the original entry in journal file first, then todo file
        entry_location = None
        search_files = [(self.file_path, "journal"), (self.todo_file_path, "todo")]

        for search_file, file_type in search_files:
            if search_file:
                entry_location = self.org_api.find_original_entry(
                    original_message_link, search_file
                )
                if entry_location:
                    logger.info(f"Found original entry in {file_type} file")
                    file_to_update = search_file
                    break

        if not entry_location:
            # Original message not found, add as regular journal entry
            logger.info(
                "Original entry not found, falling back to regular journal entry"
            )
            return PostToGitJournal(self.token, self.repo_name, self.file_path).run(
                message, file_path
            )

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
            file_to_update, top_line_number, top_org_level, reply_text, commit_message
        )

        return True
