from telegram import Message


def get_text_from_message(message: Message):
    """
    This method is used to get the message from the text of the message.
    We have not only text messages, but also other types of messages.
    """
    if message.text:
        return message.text
    elif message.caption:
        return message.caption
    else:
        return "%% No text %%"
