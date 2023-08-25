import logging
import os

from telegram import Message, Bot

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", None)
if BOT_TOKEN:
    bot = Bot(token=BOT_TOKEN)
else:
    logger.error("BOT_TOKEN is not set")
    bot = None


def command_webhook(message: Message):
    return bot.get_webhook_info().to_json()
