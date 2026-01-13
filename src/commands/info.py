import json
import logging
from telegram import Message
from ..base_command import BaseCommand

logger = logging.getLogger(__name__)


class InfoCommand(BaseCommand):
    async def execute(self, message: Message) -> str:
        try:
            response_data = await self.bot.get_me()
            response = json.dumps(response_data.to_dict(), indent=1).replace("\\", "\\\\")
            return f"""```
{response}
```"""
        except Exception as e:
            logger.error(f"Error getting info: {e}")
            return f"Error retrieving bot information: {str(e)}"
