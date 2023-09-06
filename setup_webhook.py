import os
import logging
import defopt

from telegram import Bot

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot = Bot(token=BOT_TOKEN)

logger = logging.getLogger(__name__)


def command_webhook(webhook_url: str):
    if not webhook_url:
        return "Please provide a webhook url"
    register_webhook = bot.set_webhook(webhook_url)
    if register_webhook:
        logger.debug(bot.get_webhook_info().to_json())
    else:
        print("Failed to register webhook")


# using defopt package to parse command line arguments
if __name__ == "__main__":
    defopt.run(command_webhook)
