"""
in this task, I take the message from telegram command, and post it to my journal on github.
I will use the github api to do this.
"""
import logging

from telegram import Message

logger = logging.getLogger(__name__)


class PostToGitJournal:
    def __init__(self, config: dict):
        """
        :param file_path: relative path to the file on github
        """
        # Validating config
        self.token = config["github_token"]
        if not self.token:
            logger.error("Github token is not provided.")
            raise ValueError("Github token is not provided.")
        self.file_path = config["file_path"]
        if not self.file_path:
            # warning in logs that default file path is used
            logger.warning("File path is not provided. Using default file path.")

        self.client = github.Github(self.token)

    def run(self, message: Message):
        """
        Adds a message to the journal on github. File should exists on the github.
        :param message: incoming telegram message
        :param config: config dict
        :return: status of operation
        """
        pass
