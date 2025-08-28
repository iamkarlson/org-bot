import json
from telegram import Message
from ..base_command import BaseCommand


class InfoCommand(BaseCommand):
    async def execute(self, message: Message) -> str:
        response_data = await self.bot.get_me()
        response = json.dumps(response_data, indent=1).replace("\\", "\\\\")
        return f"""```
{response}
```"""
