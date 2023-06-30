from telegram import Message


def command_webhook(message: Message):
    return bot.get_webhook_info().to_json()
