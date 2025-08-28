from telegram import Message
from ..base_command import BaseCommand


class StartCommand(BaseCommand):
    async def execute(self, message: Message) -> str:
        return "Hello brain!"
