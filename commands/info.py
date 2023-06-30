import json

from telegram import Message

from main import bot


def command_info(message: Message):
    bot_info = bot.get_me()
    return json.dumps(bot_info.to_dict())
