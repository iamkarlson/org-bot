import json

import functions_framework
from telegram import Update, Bot
from flask import Request, abort
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot = Bot(token=BOT_TOKEN)


def handle_message(message):
    """
    Command handler for telegram bot.
    """
    if message.text == "/start":
        return "Hello, World!"
    else:
        return json.dumps(message.__dict__)


@functions_framework.http
def handle(request: Request):
    """
    Incoming telegram webhook handler for a GCP Cloud Function.
    When request is received, body is parsed into standard telegram message model, and then forwarded to command handler.
    """
    # when get is called, automatically register webhook to telegram using bot token from secret
    if request.method == "GET":
        # get bot info from "https://api.telegram.org/{BOT_TOKEN}/getMe"
        bot_info = bot.get_me()
        return json.dumps(bot_info.__dict__)
    # when post is called, parse body into standard telegram message model, and then forward to command handler
    if request.method == "POST":
        update_message = Update.de_json(request.get_json(), bot)
        return handle_message(update_message)

    # Unprocessable entity
    abort(422)
