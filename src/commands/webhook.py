from telegram import Message

from main import bot, webhook_url


def command_webhook(message: Message):
    register_webhook = bot.set_webhook(webhook_url)
    if register_webhook:
        return bot.get_webhook_info().to_json()
    else:
        return "Failed to register webhook"
