import asyncio
import logging
from typing import TYPE_CHECKING, Callable, Optional

from telegram import Bot, Message

from ..base_command import BaseCommand

if TYPE_CHECKING:
    # Runtime import would be circular: config -> commands -> search -> state_store -> config
    from ..search.service import SearchService

logger = logging.getLogger(__name__)

USAGE = "Usage: /search <query>"
NOT_CONFIGURED = "Search is not configured (no state bucket)."


class SearchCommand(BaseCommand):
    """Search notes in the org repo. Sends its own responses (plain text +
    inline buttons), so execute() returns an empty string."""

    def __init__(self, get_bot: Callable[[], Bot], search_service: "Optional[SearchService]"):
        super().__init__(get_bot)
        self.search_service = search_service

    async def execute(self, message: Message) -> str:
        if self.search_service is None:
            return NOT_CONFIGURED

        text = message.text or ""
        parts = text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            return USAGE

        try:
            # Corpus refresh does sync network I/O (GitHub, GCS) — keep it
            # off the event loop.
            corpus = await asyncio.to_thread(self.search_service.ensure_corpus)
            response_text, keyboard = self.search_service.results_response(
                corpus, query, page=0
            )
        except Exception:
            # Privacy: never log the query text itself.
            logger.exception("Search failed", extra={"query_length": len(query)})
            return "Search failed."

        logger.info(
            "Search executed",
            extra={"query_length": len(query), "corpus_size": len(corpus.notes)},
        )

        await self.bot.send_message(
            chat_id=message.chat_id,
            text=response_text,
            reply_to_message_id=message.message_id,
            reply_markup=keyboard,
        )
        return ""
