from pprint import pprint

import defopt

from telegram import Bot

with open("bot_token.txt") as file:
    BOT_TOKEN = file.readline()
    bot = Bot(token=BOT_TOKEN)


def command_webhook(webhook_url: str):
    if not webhook_url:
        return "Please provide a webhook url"
    register_webhook = bot.set_webhook(webhook_url)
    if register_webhook:
        pprint(bot.get_webhook_info().to_json())
    else:
        print("Failed to register webhook")


# using defopt package to parse command line arguments
if __name__ == "__main__":
    defopt.run(command_webhook)
