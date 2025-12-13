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
                "new_text": new_text,
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


class PostReplyToEntry(BasePostToGitJournal):
    """
    Handles reply messages by looking up the original message in journal/todo files
    and adding the reply as a subheader (child entry).
    """

    def __init__(self, github_token=None, repo_name=None, file_path=None, todo_file_path=None):
        super().__init__(github_token, repo_name, file_path)
        self.todo_file_path = todo_file_path

    def _find_original_entry(self, original_message_link: str, file_path: str) -> tuple[int, int] | None:
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
                    match = re.match(r'^(\*+)\s', line)
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

    def _insert_reply_after_entry(
        self,
        file_path: str,
        line_number: int,
        org_level: int,
        reply_text: str,
        commit_message: str
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
            match = re.match(r'^(\*+)\s', lines[i])
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
                "org_level": org_level + 1
            }
        )

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
                entry_location = self._find_original_entry(original_message_link, search_file)
                if entry_location:
                    logger.info(f"Found original entry in {file_type} file")
                    file_to_update = search_file
                    break

        if not entry_location:
            # Original message not found, add as regular journal entry
            logger.info("Original entry not found, falling back to regular journal entry")
            return PostToGitJournal(self.token, self.repo_name, self.file_path).run(message, file_path)

        line_number, org_level = entry_location

        # Create the reply entry as a subheader (one level deeper)
        reply_level = org_level + 1
        asterisks = "*" * reply_level

        message_id = message.message_id
        chat_id = message.chat.id
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        message_link = f"https://t.me/c/{chat_id}/{message_id}"
        message_text = get_text_from_message(message)

        reply_text = f"{asterisks} Reply: [[{message_link}][{now}]]\n{message_text}"

        commit_message = f"Reply to message {original_message_id} from chat {chat_id}"

        # Insert the reply after the original entry
        self._insert_reply_after_entry(
            file_to_update,
            line_number,
            org_level,
            reply_text,
            commit_message
        )

        return True
