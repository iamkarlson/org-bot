import asyncio
import logging
from typing import TYPE_CHECKING, Callable, Optional

from telegram import Bot, Message

from ..base_command import BaseCommand

if TYPE_CHECKING:
    # Runtime import would be circular: config -> commands -> search -> state_store -> config
    from ..search.service import SearchService

logger = logging.getLogger(__name__)

USAGE = "Usage: /open <note path>"
NOT_CONFIGURED = "Search is not configured (no state bucket)."


class OpenCommand(BaseCommand):
    """Open a note by path. This is what an inline-mode suggestion sends when
    selected — command-shaped so it routes here instead of journal capture.
    Deliberately absent from the command menu; it works when typed manually."""

    def __init__(self, get_bot: Callable[[], Bot], search_service: "Optional[SearchService]"):
        super().__init__(get_bot)
        self.search_service = search_service

    async def execute(self, message: Message) -> str:
        if self.search_service is None:
            return NOT_CONFIGURED

        text = message.text or ""
        parts = text.split(maxsplit=1)
        path = parts[1].strip() if len(parts) > 1 else ""
        if not path:
            return USAGE

        try:
            corpus = await asyncio.to_thread(self.search_service.ensure_corpus)
            response_text, keyboard = self.search_service.open_by_path_response(
                corpus, path, chunk=0
            )
        except Exception:
            logger.exception("Open note failed")
            return "Failed to open note."

        await self.bot.send_message(
            chat_id=message.chat_id,
            text=response_text,
            reply_to_message_id=message.message_id,
            reply_markup=keyboard,
        )
        return ""
