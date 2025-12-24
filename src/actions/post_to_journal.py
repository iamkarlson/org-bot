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
