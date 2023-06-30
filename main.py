import json
from pprint import pprint

import functions_framework
from telegram import Update, Bot, Message
from flask import Request, abort
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot = Bot(token=BOT_TOKEN)

webhook_url = os.environ["WEBHOOK_URL"]


def send_back(message: Message, text):
    """
    Sends a message back to the user. Using telegram bot's sendMessage method.
    :param message: incoming telegram message
    :param text:
    :return:
    """
    bot.send_message(
        chat_id=message.chat_id,
        text=text
    )


def handle_message(message: Message):
    """
    Command handler for telegram bot.
    """
    pprint(message)
    if message.text == "/start":
        send_back(message, "Hello brain!")
    elif message.text == "/webhook":
        register_webhook = bot.set_webhook(webhook_url)
        if register_webhook:
            send_back(message, bot.get_webhook_info().to_json())
        else:
            send_back(message, "Failed to register webhook")
    elif message.text == "/info":
        bot_info = bot.get_me()
        send_back(message, json.dumps(bot_info.to_dict()))
    else:
        send_back(message, message.to_json())


@functions_framework.http
def handle(request: Request):
    """
    Incoming telegram webhook handler for a GCP Cloud Function.
    When request is received, body is parsed into standard telegram message model, and then forwarded to command handler.
    """
    # when post is called, parse body into standard telegram message model, and then forward to command handler
    if request.method == "POST":
        update_message = Update.de_json(request.get_json(), bot)
        handle_message(update_message.message)
        return {"statusCode": 200}

    # Unprocessable entity
    abort(422)
