import os
from pprint import pprint

import functions_framework
from flask import Request, abort
from telegram import Bot, Update, Message

from commands import commands
from src.config import default_action

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot = Bot(token=BOT_TOKEN)


def send_back(message: Message, text):
    """
    Sends a message back to the user. Using telegram bot's sendMessage method.
    :param message: incoming telegram message
    :param text:
    :return:
    """
    bot.send_message(chat_id=message.chat_id, text=text)


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
    pprint(message)

    # Check if the message is a command
    if message.text.startswith("/"):
        command_text = message.text.split("@")[0]  # Split command and bot's name
        command = commands.get(command_text)
        if command:
            return command(message)
        else:
            return "Unrecognized command"
    else:
        return process_non_command(message)


def process_non_command(message: Message):
    # Your code here to process non-command messages
    default_action(message)
    return "Added to journal!"


@functions_framework.http
def handle(request: Request):
    """
    Incoming telegram webhook handler for a GCP Cloud Function.
    When request is received, body is parsed into standard telegram message model, and then forwarded to command handler.
    """
    if request.method == "GET":
        return {"statusCode": 200}
    # when post is called, parse body into standard telegram message model, and then forward to command handler
    if request.method == "POST":
        update_message = Update.de_json(request.get_json(), bot)
        handle_message(update_message.message)
        return {"statusCode": 200}

    # Unprocessable entity
    abort(422)
