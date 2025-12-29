import logging
import os
from telegram import Message
import sentry_sdk


logger = logging.getLogger(__name__)


authorized_chats = [
    int(authorized_chat)
    for authorized_chat in os.environ["AUTHORIZED_CHAT_IDS"].split(",")
]

ignored_chats = [
    int(ignored_chat)
    for ignored_chat in os.environ.get("IGNORED_CHAT_IDS", "").split(",")
    if ignored_chat
]

# Optional: Forward unauthorized messages to this chat ID
forward_unauthorized_to = os.environ.get("FORWARD_UNAUTHORIZED_TO")
if forward_unauthorized_to:
    forward_unauthorized_to = int(forward_unauthorized_to)


async def auth_check(message: Message, bot_getter=None):
    """
    Check if message comes from an authorized chat.
    Logs comprehensive information about unauthorized access attempts.

    :param message: incoming telegram message
    :return: True if authorized, False otherwise
    """
    logger.debug(f"All authorized chats: {authorized_chats}")
    if message.chat_id in authorized_chats:
        return True

    # Capture comprehensive unauthorized access information
    chat = message.chat
    user = message.from_user

    chat_info = {
        "chat_id": chat.id,
        "chat_type": chat.type,
        "title": getattr(chat, "title", None),
        "username": getattr(chat, "username", None),
        "first_name": getattr(chat, "first_name", None),
        "last_name": getattr(chat, "last_name", None),
        "description": getattr(chat, "description", None),
        "invite_link": getattr(chat, "invite_link", None),
        "pinned_message_id": getattr(chat.pinned_message, "message_id", None)
        if hasattr(chat, "pinned_message") and chat.pinned_message
        else None,
        "permissions": {
            "can_send_messages": getattr(chat.permissions, "can_send_messages", None),
            "can_send_media_messages": getattr(
                chat.permissions, "can_send_media_messages", None
            ),
            "can_send_polls": getattr(chat.permissions, "can_send_polls", None),
            "can_send_other_messages": getattr(
                chat.permissions, "can_send_other_messages", None
            ),
            "can_add_web_page_previews": getattr(
                chat.permissions, "can_add_web_page_previews", None
            ),
            "can_change_info": getattr(chat.permissions, "can_change_info", None),
            "can_invite_users": getattr(chat.permissions, "can_invite_users", None),
            "can_pin_messages": getattr(chat.permissions, "can_pin_messages", None),
        }
        if hasattr(chat, "permissions") and chat.permissions
        else None,
        "member_count": getattr(chat, "member_count", None),
        "is_forum": getattr(chat, "is_forum", None),
    }

    user_info = {
        "user_id": user.id if user else None,
        "username": user.username if user else None,
        "first_name": user.first_name if user else None,
        "last_name": user.last_name if user else None,
        "is_bot": user.is_bot if user else None,
        "is_premium": getattr(user, "is_premium", None) if user else None,
        "language_code": getattr(user, "language_code", None) if user else None,
    }

    # Log comprehensive unauthorized access warning
    warning_msg = f"UNAUTHORIZED ACCESS ATTEMPT - Chat: {chat_info} | User: {user_info} | Message ID: {message.message_id} | Date: {message.date}"
    logger.warning(warning_msg)

    # Send to Sentry with additional context
    with sentry_sdk.push_scope() as scope:
        scope.set_extra("chat_info", chat_info)
        scope.set_extra("user_info", user_info)
        scope.set_extra("message_id", message.message_id)
        scope.set_extra("message_date", str(message.date))
        scope.set_extra("message_text", message.text[:100] if message.text else None)
        sentry_sdk.capture_message(
            f"Unauthorized chat access attempt from chat_id: {message.chat_id}",
            level="warning",
        )

    # Forward unauthorized message if configured
    if forward_unauthorized_to and bot_getter:
        try:
            bot = bot_getter()

            # Create summary message with context
            summary_text = "🚨 UNAUTHORIZED ACCESS\n\n"
            summary_text += f"Chat: {chat_info.get('title') or chat_info.get('first_name') or 'Unknown'} ({chat_info['chat_type']})\n"
            summary_text += f"Chat ID: {chat_info['chat_id']}\n"
            if user_info.get("username"):
                summary_text += f"User: @{user_info['username']}\n"
            if user_info.get("first_name"):
                summary_text += f"Name: {user_info['first_name']} {user_info.get('last_name', '')}\n"
            summary_text += f"User ID: {user_info['user_id']}\n"
            summary_text += f"Date: {message.date}\n"

            # Send summary first
            await bot.send_message(chat_id=forward_unauthorized_to, text=summary_text)

            # Then forward the original message
            await bot.forward_message(
                chat_id=forward_unauthorized_to,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
            )

            logger.info(f"Forwarded unauthorized message to {forward_unauthorized_to}")

        except Exception as e:
            logger.error(f"Failed to forward unauthorized message: {e}")

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
