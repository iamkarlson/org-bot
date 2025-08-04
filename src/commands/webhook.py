import json
import logging
import os

from telegram import Message, Bot

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", None)
if BOT_TOKEN:
    bot = Bot(token=BOT_TOKEN)
else:
    logger.error("BOT_TOKEN is not set in environment variables")
    bot = None


async def command_webhook(message: Message):
    if bot is None:
        logger.error("Cannot execute webhook command: BOT_TOKEN is not configured")
        return "Error: Bot token is not configured. Check logs for details."
    
    try:
        # Get webhook info
        webhook_info = await bot.get_webhook_info()
        
        # Get basic bot info
        bot_info = await bot.get_me()
        
        # Prepare response with webhook info, bot info, and chat ID
        response_data = {
            "webhook_info": webhook_info.to_dict(),
            "bot_info": {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
            },
            "chat_id": message.chat.id,
            "chat_type": message.chat.type
        }
        response = json.dumps(response_data, indent=1).replace("\\", "\\\\")
        return f"""```
{response}
```"""

    except Exception as e:
        logger.error(f"Error getting webhook/bot info: {e}")
        return f"Error retrieving bot information: {str(e)}"
