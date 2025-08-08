import logging
import os

import asyncio
import functions_framework
from flask import Request, abort
from telegram import Bot, Update, Message

import sentry_sdk
from sentry_sdk.integrations.gcp import GcpIntegration

from .config import commands, actions
from .tracing.log import GCPLogger
from .utils import get_text_from_message


BOT_TOKEN = os.environ["BOT_TOKEN"]
bot = Bot(token=BOT_TOKEN)

# Set the new logger class
logging.setLoggerClass(GCPLogger)

logger = logging.getLogger(__name__)

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=[GcpIntegration()],
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

# Chain of calls when bot receives a message from Telegram:
# 1. http_entrypoint() - receives webhook POST request from Telegram
# 2. handle_message() - processes the incoming message and sends response
# 3. process_message() - determines if message is command or non-command
# 4. For commands: looks up command in commands dict and executes it
# 5. For non-commands: calls process_non_command() to handle journal/todo entries
# 6. send_back() - sends the response back to user via Telegram API


async def send_back(message: Message, text):
    """
    Sends a message back to the user. Using telegram bot's sendMessage method.
    :param message: incoming telegram message
    :param text:
    :return:
    """

    # escape text for MarkdownV2 formatting
    # There's a bunch of characters that need escaping in MarkdownV2
    markdownv2_escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in markdownv2_escape_chars:
        text = text.replace(char, f'\\{char}')
    
    
    await bot.send_message(
        chat_id=message.chat_id, 
        text=text,
        reply_to_message_id=message.message_id,
        parse_mode="MarkdownV2"  # Use MarkdownV2 for better formatting
    )


async def handle_message(message: Message):
    """
    Handles incoming telegram message.
    :param message: incoming telegram message
    :return:
    """
    response = await process_message(message)
    if response:
        await send_back(message, response)
    else:
        await send_back(message, "I don't understand")


async def process_message(message: Message):
    """
    Command handler for telegram bot.
    """
    # Generate temp file path upfront
    temp_file_path = None
    if message.photo:
        # we got a picture.
        # let's save it to a random file in /tmp
        # and then pass it command to insert it into the journal
        temp_file_path = f"/tmp/{message.photo[-1].file_id}.jpg"
        with open(temp_file_path, "wb") as file:
            file.write(bot.get_file(message.photo[-1].file_id).download_as_bytearray())
        logger.info("Photo received")

    message_text = get_text_from_message(message)
    
    if message_text.startswith("/"):
        # Commands are always processed, even from ignored chats
        command_text = message.text.split("@")[0]  # Split command and bot's name
        command = commands.get(command_text)
        if command:
            return await command(message)
        else:
            return "Unrecognized command"
    else:
        # For non-command messages, check if chat should be ignored
        if ignore_check(message):
            return None  # Don't respond to ignored chats for regular messages
        else:
            return process_non_command(message, file_path=temp_file_path)


def process_non_command(message: Message, file_path=None):
    # Your code here to process non-command messages
    logger.info("Processing non-command message")
    logger.debug(message.to_json())

    message_text = get_text_from_message(message)
    if message_text.lower().startswith("todo "):
        keyword = "todo"
    else:
        keyword = "journal"

    try:
        if action_config := actions.get(keyword):
            action_config["function"](message, file_path=file_path)
            return action_config["response"]
    except Exception as e:
        logger.error(e)
        return "Failed to add to journal."


authorized_chats = [
    int(authorized_chat)
    for authorized_chat in os.environ["AUTHORIZED_CHAT_IDS"].split(",")
]

ignored_chats = [
    int(ignored_chat)
    for ignored_chat in os.environ.get("IGNORED_CHAT_IDS", "").split(",")
    if ignored_chat
]


def auth_check(message: Message):
    logger.debug(f"All authorized chats: {authorized_chats}")
    if message.chat_id in authorized_chats:
        return True
    logger.error("Unauthorized chat id")
    sentry_sdk.capture_message(
        f"Unauthorized chat id: {message.chat_id}",
        level="error"
    )
    # Note: send_back is async but we can't await here in sync function
    # This should be handled at the calling level
    return False


def ignore_check(message: Message):
    """
    Check if message comes from an ignored chat.
    :param message: incoming telegram message
    :return: True if chat should be ignored, False otherwise
    """
    logger.debug(f"All ignored chats: {ignored_chats}")
    if message.chat_id in ignored_chats:
        logger.info(f"Message from ignored chat: {message.chat_id}")
        return True
    return False



@functions_framework.http
def http_entrypoint(request: Request):
    """
    Incoming telegram webhook handler for a GCP Cloud Function.
    """
    if request.method == "GET":
        return {"statusCode": 200}

    if request.method == "POST":
        try:
            incoming_data = request.get_json()
            logger.debug(f"incoming data: {incoming_data}")
            update_message = Update.de_json(incoming_data, bot)
            message = update_message.message or update_message.edited_message
            
            if auth_check(message):
                # Run async function in sync context
                asyncio.run(handle_message(message))
            else:
                # Handle unauthorized case
                asyncio.run(send_back(message, "It's not for you!"))
            return {"statusCode": 200}
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.exception("Error occurred but message wasn't processed")
            return {"statusCode": 200}

    # Unprocessable entity
    abort(422)