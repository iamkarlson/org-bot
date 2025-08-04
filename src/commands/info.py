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


async def command_info(message: Message):
    response_data = await bot.get_me()
    response = json.dumps(response_data, indent=1).replace("\\", "\\\\")
    return f"""```
{response}
```"""
