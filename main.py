import json

import functions_framework
from flask import Request, abort

class TelegramMessage:
    """
    Standard telegram message model.
    Example json:
    {
        "message_id": 1,
        "from_user": "user",
        "date": 123456789,
        "chat_id": 123456789,
        "text": "Hello, World!"
    }
    """

    def __init__(self, message_id: int, from_user: str, date: int, chat_id: int, text: str):
        self.message_id = message_id
        self.from_user = from_user
        self.date = date
        self.chat_id = chat_id
        self.text = text


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
        return "Webhook registered"
    # when post is called, parse body into standard telegram message model, and then forward to command handler
    if request.method == "POST":
        message = TelegramMessage(**request.get_json())
        return handle_message(message)

    # Unprocessable entity
    abort(422)
