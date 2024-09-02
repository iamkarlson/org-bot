import logging
import os

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


def send_back(message: Message, text):
    """
    Sends a message back to the user. Using telegram bot's sendMessage method.
    :param message: incoming telegram message
    :param text:
    :return:
    """
    bot.send_message(
        chat_id=message.chat_id, text=text, reply_to_message_id=message.message_id
    )


def handle_message(message: Message):
    """
    Handles incoming telegram message.
    :param message: incoming telegram message
    :return:
    """
    response = process_message(message)
    if response:
        send_back(message, response)
    else:
        send_back(message, "I don't understand")


def process_message(message: Message):
    """
    Command handler for telegram bot.
    """
    # Check if the message is a command

    message_text = get_text_from_message(message)
    if message.photo:
        # we got a picture.
        # let's save it to a random file in /tmp
        # and then pass it command to insert it into the journal
        random_filename = f"/tmp/{message.photo[-1].file_id}.jpg"
        with open(random_filename, "wb") as file:
            file.write(bot.get_file(message.photo[-1].file_id).download_as_bytearray())
        logger.debug("Photo received")
        return process_non_command(message, file_path=random_filename)
    elif message_text.startswith("/"):
        command_text = message.text.split("@")[0]  # Split command and bot's name
        command = commands.get(command_text)
        if command:
            return command(
                message, file_path=random_filename if message.photo else None
            )
        else:
            return "Unrecognized command"
    else:
        return process_non_command(message)


def process_non_command(message: Message, file_path=None):
    # Your code here to process non-command messages
    logger.debug("Processing non-command message")
    logger.debug(message.to_json())

    message_text = get_text_from_message(message)
    if message_text.lower().startswith("todo "):
        action = "todo"
    else:
        action = "journal"

    try:
        if action in actions:
            actions[action]["handler"](message, file_path=file_path)
            return actions[action]["response"]
    except Exception as e:
        logger.error(e)
        return "Failed to add to journal."


authorized_chats = [
    int(authorized_chat)
    for authorized_chat in os.environ["AUTHORIZED_CHAT_IDS"].split(",")
]


def auth_check(message: Message):
    if message.chat_id in authorized_chats:
        return True
    logger.info("Unauthorized chat id")
    send_back(message, "It's not for you!")
    return False


@functions_framework.http
def handle(request: Request):
    """
    Incoming telegram webhook handler for a GCP Cloud Function.
    When request is received, body is parsed into standard telegram message model, and then forwarded to command handler.
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
                handle_message(message)
            return {"statusCode": 200}
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error("Error occurred but message wasn't processed")
            return {"statusCode": 200}

    # Unprocessable entity
    abort(422)
