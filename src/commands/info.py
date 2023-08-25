import json
import logging
import os

from telegram import Bot, Message

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", None)
if BOT_TOKEN:
    bot = Bot(token=BOT_TOKEN)
else:
    logger.error("BOT_TOKEN is not set")
    bot = None


def command_info(message: Message):
    bot_info = bot.get_me()
    return json.dumps(bot_info.to_dict())
