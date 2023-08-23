from telegram import Message


class Task:
    """
    When bot received a message - it may call some external API, or do some other work.
    This class is the base class for all such tasks.
    """

    def __init__(self, config: dict):
        self.config = config

    def run(self, message: Message, config: dict):
        raise NotImplementedError()
