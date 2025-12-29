from abc import ABC, abstractmethod
from typing import Callable
from telegram import Bot, Message


class BaseCommand(ABC):
    """Base class for all bot commands with dependency injection."""

    def __init__(self, get_bot: Callable[[], Bot]):
        self._get_bot = get_bot

    @property
    def bot(self) -> Bot:
        """Get a fresh bot instance for each request."""
        return self._get_bot()

    @abstractmethod
    async def execute(self, message: Message) -> str:
        """Execute the command and return response text."""
        pass
