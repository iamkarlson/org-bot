import json
import logging
from telegram import Message
from ..base_command import BaseCommand

logger = logging.getLogger(__name__)


class WebhookCommand(BaseCommand):
    async def execute(self, message: Message) -> str:
        try:
            # Get webhook info
            webhook_info = await self.bot.get_webhook_info()
            
            # Get basic bot info
            bot_info = await self.bot.get_me()
            
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
            return f"""Webhook data
    
    ```
    
{response}

```"""

        except Exception as e:
            logger.error(f"Error getting webhook/bot info: {e}")
            return f"Error retrieving bot information: {str(e)}"
