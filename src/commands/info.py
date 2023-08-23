import json

from telegram import Message

import os

from telegram import Bot

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot = Bot(token=BOT_TOKEN)


def command_info(message: Message):
    bot_info = bot.get_me()
    return json.dumps(bot_info.to_dict())
