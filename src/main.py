import logging
import os
import asyncio
import functions_framework
from flask import Request, abort
from telegram import Bot, Update, Message
from telegram.request import HTTPXRequest
from telegram.error import TimedOut, NetworkError

import sentry_sdk
from sentry_sdk.integrations.gcp import GcpIntegration

from .config import init_commands, actions
from .tracing.log import GCPLogger
from .utils import get_text_from_message
from .auth import auth_check, ignore_check


BOT_TOKEN = os.environ["BOT_TOKEN"]

# Configure HTTP client with larger pool and longer timeout to prevent pool exhaustion
request = HTTPXRequest(
    pool_timeout=30,  # Wait up to 30 seconds for connection
    connection_pool_size=10,  # Allow up to 10 concurrent connections
    read_timeout=30,  # Timeout for reading response
    write_timeout=30,  # Timeout for writing request
)


def get_bot() -> Bot:
    """Safe bot getter that creates a fresh instance for each request."""
    return Bot(token=BOT_TOKEN, request=request)


# Set the new logger class
logging.setLoggerClass(GCPLogger)

logger = logging.getLogger(__name__)

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


async def send_back(message: Message, text: str):
    markdownv2_escape_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        # "`", # Perhaps this shouldn't be escaped
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
    for char in markdownv2_escape_chars:
        text = text.replace(char, f"\\{char}")

    for attempt in range(3):
        try:
            bot = get_bot()
            await bot.send_message(
                chat_id=message.chat_id,
                text=text,
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
            bot = get_bot()
            file_obj = await bot.get_file(message.photo[-1].file_id)
            file.write(await file_obj.download_as_bytearray())
        logger.info("Photo received")

    message_text = get_text_from_message(message)
    commands = init_commands(get_bot)  # Initialize commands with bot getter

    if message_text.startswith("/"):
        # Commands are always processed, even from ignored chats
        command_text = (message.text or "").split("@")[
            0
        ]  # Split command and bot's name
        command = commands.get(command_text)
        if command:
            return await command.execute(message)
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


async def handle_telegram_update(message: Message):
    """
    Async handler for telegram updates.
    """
    if auth_check(message):
        await handle_message(message)
    else:
        await send_back(
            message, "It's not for you! If you have any questions ask @iamkarlson"
        )


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
            update_message = Update.de_json(incoming_data, get_bot())
            message = update_message.message or update_message.edited_message

            if message:
                # Run async function with proper lifecycle management
                asyncio.run(handle_telegram_update(message))
            return {"statusCode": 200}
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.exception("Error occurred but message wasn't processed")
            return {"statusCode": 200}

    # Unprocessable entity
    abort(422)
