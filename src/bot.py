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
from typing import Optional
from telegram import Bot, Message
from telegram.request import HTTPXRequest
from telegram.error import TimedOut, NetworkError

from .config import (
    BotSettings,
    GitHubSettings,
    OrgSettings,
    create_commands,
    create_actions,
)
from .auth import auth_check, ignore_check
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
    ):
        """
        Initialize the OrgBot with configurations.

        Args:
            bot_settings: Bot settings (loads from env if not provided)
            github_settings: GitHub settings (loads from env if not provided)
            org_settings: Org-mode settings (loads from env if not provided)
        """
        # Load configurations
        self.bot_settings = bot_settings or BotSettings()
        self.github_settings = github_settings or GitHubSettings()
        self.org_settings = org_settings or OrgSettings()

        # Configure HTTP client for bot
        self.request = HTTPXRequest(
            pool_timeout=30,
            connection_pool_size=10,
            read_timeout=30,
            write_timeout=30,
        )

        # Initialize commands and actions
        self.commands = create_commands(self._get_bot)
        self.actions = create_actions(self.github_settings, self.org_settings)
        self.default_action_key = "journal"

        logger.info(
            f"OrgBot initialized with {len(self.commands)} commands "
            f"and {len(self.actions)} actions"
        )

    def _get_bot(self) -> Bot:
        """Create a fresh bot instance for each request."""
        return Bot(token=self.bot_settings.token, request=self.request)

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
            return await self._handle_action(message, message_text, temp_file_path)

    async def _handle_command(self, message: Message, message_text: str) -> str:
        """
        Route message to appropriate command handler.

        Args:
            message: Telegram message
            message_text: Text content of the message

        Returns:
            Response text
        """
        # Extract command (remove bot name if present)
        command_text = message_text.split("@")[0]

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
        file_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Route message to appropriate action handler.

        Args:
            message: Telegram message
            message_text: Text content of the message
            file_path: Optional path to attached file

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
                action_config.function(message, file_path=file_path)
                return action_config.response_message
            else:
                logger.error(f"Action not found: {action_key}")
                return "Failed to process message."
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
                if "Event loop is closed" in str(e):
                    logger.info("Event loop closed, request likely completed")
                    return
                if attempt < 2:
                    logger.warning(f"Network retry {attempt + 1}/3: {type(e).__name__}")
                    await asyncio.sleep(attempt + 1)
                    continue
                logger.error(f"Failed after 3 network attempts: {type(e).__name__}")
                raise

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
