import os

from telegram import Message, Bot

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot = Bot(token=BOT_TOKEN)


def command_webhook(message: Message):
    return bot.get_webhook_info().to_json()
