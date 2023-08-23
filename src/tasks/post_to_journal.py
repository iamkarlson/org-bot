"""
in this task, I take the message from telegram command, and post it to my journal on github.
I will use the github api to do this.
"""
from telegram import Message

from src.tasks import Task


class PostToGitJournal(Task):
    def __init__(self, config: dict):
        """
        :param file_path: relative path to the file on github
        """
        super().__init__(config)

        self.file_path = config["file_path"]

    def run(self, message: Message):
        """
        Adds a message to the journal on github. File should exists on the github.
        :param message: incoming telegram message
        :param config: config dict
        :return: status of operation
        """
        pass
