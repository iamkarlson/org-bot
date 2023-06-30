from telegram import Message

import os

from telegram import Bot

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot = Bot(token=BOT_TOKEN)

webhook_url = os.environ["WEBHOOK_URL"]


def command_webhook(message: Message):
    register_webhook = bot.set_webhook(webhook_url)
    if register_webhook:
        return bot.get_webhook_info().to_json()
    else:
        return "Failed to register webhook"
