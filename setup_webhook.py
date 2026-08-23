import asyncio

from defopt import run
from telegram import Bot, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeDefault
import os
import logging

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand("search", "Search notes: /search <query>"),
    BotCommand("info", "Show bot info"),
    BotCommand("webhook", "Show webhook info"),
]


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


def command_menu(bot_token: str):
    """Register the bot command menu (shown by clients when typing /).

    Set in both the default and all_private_chats scopes: clients resolve the
    most specific scope, so a stale list in all_private_chats silently shadows
    anything registered in default."""

    async def _inner_command_menu():
        bot = Bot(token=bot_token)
        scopes = [BotCommandScopeDefault(), BotCommandScopeAllPrivateChats()]
        for scope in scopes:
            if await bot.set_my_commands(BOT_COMMANDS, scope=scope):
                logger.info(f"Registered {len(BOT_COMMANDS)} commands in scope {scope.type}")
            else:
                logger.error(f"Failed to register command menu in scope {scope.type}")

    asyncio.run(_inner_command_menu())


if __name__ == "__main__":
    run([command_webhook, command_menu])
