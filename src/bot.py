"""
OrgBot main application class.

This module contains the core OrgBot class that orchestrates:
- Command and action routing
- Authentication and authorization
- Message processing pipeline
- Error handling
- Response generation
"""

import logging
import asyncio
from typing import List, Optional
from telegram import Bot, CallbackQuery, InlineQuery, Message
from telegram.request import HTTPXRequest
from telegram.error import BadRequest, TimedOut, NetworkError
from github import BadCredentialsException

from .config import (
    BotSettings,
    GitHubSettings,
    OrgSettings,
    StateSettings,
    create_commands,
    create_actions,
)
from .auth import auth_check, ignore_check
from .pebble import pebble_org_entry
from .search import SearchService
from .search import callbacks as search_callbacks
from .state_store import StateStore
from .utils import get_text_from_message


logger = logging.getLogger(__name__)


class OrgBot:
    """
    Main bot application class.

    Responsibilities:
    - Initialize commands and actions from configuration
    - Route incoming messages to appropriate handlers
    - Manage authentication and authorization
    - Handle errors and provide appropriate responses
    """

    def __init__(
        self,
        bot_settings: Optional[BotSettings] = None,
        github_settings: Optional[GitHubSettings] = None,
        org_settings: Optional[OrgSettings] = None,
        state_settings: Optional[StateSettings] = None,
    ):
        """
        Initialize the OrgBot with configurations.

        Args:
            bot_settings: Bot settings (loads from env if not provided)
            github_settings: GitHub settings (loads from env if not provided)
            org_settings: Org-mode settings (loads from env if not provided)
            state_settings: State bucket settings (loads from env if not provided)
        """
        # Load configurations
        self.bot_settings = bot_settings or BotSettings()
        self.github_settings = github_settings or GitHubSettings()
        self.org_settings = org_settings or OrgSettings()
        self.state_settings = state_settings or StateSettings()

        # State store + search are optional: without a configured bucket the
        # bot runs exactly as before (capture only).
        self.state_store = StateStore(self.state_settings)
        self.search_service = None
        if self.state_store.enabled and self.github_settings.token:
            self.search_service = SearchService(
                github_token=self.github_settings.token,
                repo_name=self.github_settings.repo,
                state_store=self.state_store,
            )

        # Initialize commands and actions
        self.commands = create_commands(self._get_bot, self.search_service)
        self.actions = create_actions(self.github_settings, self.org_settings)
        self.default_action_key = "journal"

        logger.info(
            f"OrgBot initialized with {len(self.commands)} commands "
            f"and {len(self.actions)} actions "
            f"(search {'enabled' if self.search_service else 'disabled'})"
        )

    def _get_bot(self) -> Bot:
        """
        Create a fresh bot instance with a new HTTPXRequest for each request.

        This ensures the httpx client is tied to the current event loop,
        preventing "Event loop is closed" errors in serverless environments.
        """
        request = HTTPXRequest(
            pool_timeout=30,
            connection_pool_size=10,
            read_timeout=30,
            write_timeout=30,
        )
        return Bot(token=self.bot_settings.token, request=request)

    async def handle_update(self, message: Message) -> None:
        """
        Main entry point for processing a Telegram message update.

        Args:
            message: Incoming Telegram message
        """
        # Check authorization
        if not await auth_check(message, self.bot_settings, self._get_bot):
            await self._send_unauthorized_response(message)
            return

        # Process the message
        response = await self._process_message(message)

        # Send response
        if response:
            await self._send_response(message, response)

    async def handle_media_group(self, messages: List[Message]) -> None:
        """
        Handle a media group (album with multiple photos).

        Args:
            messages: List of messages from same media group
        """
        if not messages:
            logger.warning("Empty media group received")
            return

        # Use first message for auth and response
        primary_message = messages[0]

        # Check authorization
        if not await auth_check(primary_message, self.bot_settings, self._get_bot):
            await self._send_unauthorized_response(primary_message)
            return

        # Save all photos
        file_paths = await self._save_photos(messages)

        logger.info(
            f"Media group: {len(messages)} messages, {len(file_paths)} photos",
            extra={"media_group_id": primary_message.media_group_id}
        )

        # Get text from first message with actual caption/text
        # (not placeholder from get_text_from_message)
        message_text = ""
        text_message = primary_message
        for msg in messages:
            if msg.text or msg.caption:
                message_text = msg.text or msg.caption
                text_message = msg
                break

        # If no message had text/caption, use placeholder
        if not message_text:
            message_text = get_text_from_message(primary_message)

        # Process as action (media groups can't be commands)
        response = await self._handle_action(
            text_message,
            message_text,
            file_paths=file_paths
        )

        if response:
            await self._send_response(text_message, response)

    def handle_pebble(self, transcription: str, recorded_at_ms: int) -> Optional[str]:
        """
        Append a Pebble ring recording to the todo or journal file.

        Returns:
            "todo" / "journal" for the target, or None when nothing was written
        """
        entry = pebble_org_entry(transcription, recorded_at_ms)
        if entry is None:
            logger.info("Empty Pebble transcription, skipping")
            return None

        kind, org_text = entry
        file_path = (
            self.org_settings.todo_file if kind == "todo" else self.org_settings.journal_file
        )
        # The todo action already holds an OrgApi on the same repo: reuse it.
        org_api = self.actions["todo"].function.__self__.org_api
        org_api.append_text_to_file(
            file_path, org_text, f"Pebble ring recording {recorded_at_ms}"
        )
        logger.info(f"Pebble recording added to {file_path}", extra={"kind": kind})
        return kind

    async def _process_message(self, message: Message) -> Optional[str]:
        """
        Process a message and return response text.

        Args:
            message: Telegram message to process

        Returns:
            Response text or None
        """
        # Handle photos - save to temp file
        temp_file_path = None
        if message.photo:
            temp_file_path = await self._save_photo(message)

        message_text = get_text_from_message(message)

        # Route to command or action
        if message_text.startswith("/"):
            return await self._handle_command(message, message_text)
        else:
            # Pass as list for consistency with media group handling
            file_paths = [temp_file_path] if temp_file_path else None
            return await self._handle_action(message, message_text, file_paths)

    async def _handle_command(self, message: Message, message_text: str) -> str:
        """
        Route message to appropriate command handler.

        Args:
            message: Telegram message
            message_text: Text content of the message

        Returns:
            Response text
        """
        # Extract command: first token, bot name stripped ("/search@my_bot foo" -> "/search")
        command_text = message_text.split()[0].split("@")[0]

        # Find and execute command
        command = self.commands.get(command_text)
        if command:
            return await command.execute(message)
        else:
            return "Unrecognized command"

    async def _handle_action(
        self,
        message: Message,
        message_text: str,
        file_paths: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Route message to appropriate action handler.

        Args:
            message: Telegram message
            message_text: Text content of the message
            file_paths: Optional list of paths to attached files

        Returns:
            Response text or None if chat is ignored
        """
        # Check if chat should be ignored for non-command messages
        if ignore_check(message, self.bot_settings):
            logger.info(f"Ignoring message from chat {message.chat_id}")
            return None

        # Determine action based on message context
        action_key = self._determine_action(message, message_text)

        # Execute action
        try:
            action_config = self.actions.get(action_key)
            if action_config:
                # Call with file_paths (new signature)
                action_config.function(message, file_paths=file_paths)
                return action_config.response_message
            else:
                logger.error(f"Action not found: {action_key}")
                return "Failed to process message."
        except BadCredentialsException:
            logger.error("GitHub rejected the token", exc_info=True)
            return "GitHub rejected the token. Nothing saved. Fix GITHUB_TOKEN and redeploy."
        except Exception as e:
            logger.error(f"Action execution failed: {e}", exc_info=True)
            return "Failed to add to journal."

    def _determine_action(self, message: Message, message_text: str) -> str:
        """
        Determine which action to use based on message context.

        Args:
            message: Telegram message
            message_text: Text content of the message

        Returns:
            Action key (journal/todo/reply)
        """
        # Check if this is a reply to another message
        if message.reply_to_message:
            logger.info(
                f"Detected reply to message {message.reply_to_message.message_id}",
                extra={"original_message_id": message.reply_to_message.message_id},
            )
            return "reply"

        # Check if message starts with "todo"
        if message_text.lower().startswith("todo "):
            return "todo"

        # Default to journal
        return self.default_action_key

    async def handle_callback_query(self, callback_query: CallbackQuery) -> None:
        """
        Handle a button tap on a search results/content message.

        All interaction state comes from the callback payload — nothing is
        kept between invocations.
        """
        bot = self._get_bot()

        # Stop the client spinner immediately; the actual work may take a moment.
        try:
            await bot.answer_callback_query(callback_query.id)
        except BadRequest as e:
            # Stale callback (Telegram expires them after a while) — nothing to do.
            logger.info(f"answer_callback_query failed: {e}")

        message = callback_query.message
        if message is None:
            logger.warning("Callback query without message, ignoring")
            return
        chat_id = message.chat.id

        # Buttons only exist on messages the bot sent into authorized chats,
        # but check anyway — callback updates bypass the message auth path.
        if chat_id not in self.bot_settings.authorized_chat_ids:
            logger.warning(f"Callback from unauthorized chat {chat_id}, ignoring")
            return

        if self.search_service is None:
            await bot.send_message(chat_id=chat_id, text="Search is not configured.")
            return

        data = search_callbacks.decode(callback_query.data or "")
        if data is None:
            logger.info("Unrecognized callback data, ignoring")
            return

        try:
            corpus = await asyncio.to_thread(self.search_service.ensure_corpus)

            if data.op == search_callbacks.OP_PAGE:
                text, keyboard = self.search_service.results_response(
                    corpus, data.query, page=data.page
                )
            elif data.op == search_callbacks.OP_OPEN:
                text, keyboard = self.search_service.open_response(
                    corpus, data.query, rank=data.rank, chunk=data.chunk
                )
            elif data.op == search_callbacks.OP_FILE:
                text, keyboard = self.search_service.open_by_path_response(
                    corpus, data.path, chunk=data.chunk
                )
            else:
                return

            # Single-message navigation: every button tap morphs the same
            # message (results <-> note view <-> chunks) instead of stacking
            # new messages in the chat.
            await self._edit_or_send(bot, chat_id, message.message_id, text, keyboard)
        except Exception:
            logger.exception("Callback handling failed")
            await bot.send_message(chat_id=chat_id, text="Search failed.")

    @staticmethod
    async def _edit_or_send(bot, chat_id, message_id, text, keyboard) -> None:
        """Edit the navigation message in place; fall back to a new message when
        Telegram refuses the edit (>48h old message). A tap that produces
        identical content ("message is not modified") is silently ignored."""
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
            )
        except BadRequest as e:
            if "not modified" in str(e).lower():
                logger.info("edit_message_text skipped: content unchanged")
                return
            logger.info(f"edit_message_text failed ({e}), sending new message")
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)

    async def handle_inline_query(self, inline_query: InlineQuery) -> None:
        """
        Type-ahead suggestions: fires on every keystroke of "@bot <query>".

        Only the authorized user gets results — everyone else sees an empty
        dropdown (is_personal so Telegram doesn't cross-cache between users).
        """
        bot = self._get_bot()
        user_id = inline_query.from_user.id if inline_query.from_user else None

        # Private-chat ids equal user ids, so the existing authorized list works.
        if user_id not in self.bot_settings.authorized_chat_ids:
            logger.info(f"Inline query from unauthorized user {user_id}, empty answer")
            await bot.answer_inline_query(
                inline_query.id, results=[], cache_time=300, is_personal=True
            )
            return

        query = (inline_query.query or "").strip()
        if not query or self.search_service is None:
            await bot.answer_inline_query(
                inline_query.id, results=[], cache_time=5, is_personal=True
            )
            return

        try:
            # Throttled freshness: per-keystroke GitHub SHA checks are waste.
            corpus = await asyncio.to_thread(self.search_service.ensure_corpus, 60.0)
            results = self.search_service.inline_results(corpus, query)
            await bot.answer_inline_query(
                inline_query.id, results=results, cache_time=5, is_personal=True
            )
        except BadRequest as e:
            # Stale query id (user kept typing) — expected, not an error.
            logger.info(f"answer_inline_query skipped: {e}")
        except Exception:
            logger.exception("Inline query handling failed")

    async def _save_photo(self, message: Message) -> str:
        """
        Save a photo from message to temporary file.

        Args:
            message: Message containing photo

        Returns:
            Path to saved file
        """
        photo_file_id = message.photo[-1].file_id
        temp_file_path = f"/tmp/{photo_file_id}.jpg"

        with open(temp_file_path, "wb") as file:
            bot = self._get_bot()
            file_obj = await bot.get_file(photo_file_id)
            file.write(await file_obj.download_as_bytearray())

        logger.info(f"Photo saved to {temp_file_path}")
        return temp_file_path

    async def _save_photos(self, messages: List[Message]) -> List[str]:
        """
        Save multiple photos from media group messages.

        Args:
            messages: List of messages, each may contain photo

        Returns:
            List of temp file paths
        """
        file_paths = []

        for message in messages:
            if message.photo:
                # Get highest resolution photo
                photo_file_id = message.photo[-1].file_id
                temp_file_path = f"/tmp/{photo_file_id}.jpg"

                bot = self._get_bot()
                file_obj = await bot.get_file(photo_file_id)
                file_bytes = await file_obj.download_as_bytearray()

                with open(temp_file_path, "wb") as file:
                    file.write(file_bytes)

                file_paths.append(temp_file_path)
                logger.debug(f"Saved photo to {temp_file_path}")

        logger.info(f"Saved {len(file_paths)} photos from media group")
        return file_paths

    async def _send_response(self, message: Message, text: str) -> None:
        """
        Send a response message with retry logic.

        Args:
            message: Original message to reply to
            text: Response text to send
        """
        # Escape text for MarkdownV2
        escaped_text = self._escape_markdown_v2(text)

        # Retry logic for network issues
        for attempt in range(3):
            try:
                bot = self._get_bot()
                await bot.send_message(
                    chat_id=message.chat_id,
                    text=escaped_text,
                    reply_to_message_id=message.message_id,
                    parse_mode="MarkdownV2",
                )
                return
            except TimedOut:
                if attempt < 2:
                    logger.warning(f"Timeout retry {attempt + 1}/3")
                    await asyncio.sleep(attempt + 1)
                    continue
                logger.error("Failed after 3 timeout attempts")
                raise
            except NetworkError as e:
                if attempt < 2:
                    logger.warning(f"Network retry {attempt + 1}/3: {type(e).__name__}")
                    await asyncio.sleep(attempt + 1)
                    continue
                logger.error(f"Failed after 3 network attempts: {type(e).__name__}")
                raise

    async def notify_owner(self, text: str) -> None:
        """DM the first authorized chat. Used when a non-chat path (ring) fails."""
        if not self.bot_settings.authorized_chat_ids:
            logger.warning("No authorized chat id, cannot notify owner")
            return
        try:
            await self._get_bot().send_message(
                chat_id=self.bot_settings.authorized_chat_ids[0], text=text
            )
        except Exception:
            logger.exception("Owner notification failed")

    async def _send_unauthorized_response(self, message: Message) -> None:
        """Send response to unauthorized user."""
        await self._send_response(
            message,
            "It's not for you! If you have any questions ask @iamkarlson",
        )

    @staticmethod
    def _escape_markdown_v2(text: str) -> str:
        """
        Escape special characters for Telegram MarkdownV2.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        escape_chars = [
            "_",
            "*",
            "[",
            "]",
            "(",
            ")",
            "~",
            ">",
            "#",
            "+",
            "-",
            "=",
            "|",
            "{",
            "}",
            ".",
            "!",
        ]
        for char in escape_chars:
            text = text.replace(char, f"\\{char}")
        return text
