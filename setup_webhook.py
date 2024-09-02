import asyncio

from defopt import run
from telegram import Bot
import os
import logging

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)

logger = logging.getLogger(__name__)


def command_webhook(bot_token: str, webhook_url: str):
    async def _inner_command_webhook():
        bot = Bot(token=bot_token)
        if not webhook_url:
            return "Please provide a webhook url"
        register_webhook = await bot.set_webhook(webhook_url)
        if register_webhook:
            webhook = await bot.get_webhook_info()
            logger.debug(webhook.to_json())
        else:
            logger.error("Failed to register webhook")

    asyncio.run(_inner_command_webhook())


if __name__ == "__main__":
    run(command_webhook)
