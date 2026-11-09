"""
Pebble Index 01 ring webhook: turn a voice recording transcription into an org entry.

Routing is by hotword, same idea as the Telegram "todo " prefix:
- "todo" / "to do" / "to-do" -> TODO, hotword stripped
- "remind ..."               -> TODO, full text kept ("Remind me to call mom")
- anything else              -> journal entry
"""

import hmac
import re
from datetime import datetime

SOURCE = "pebble-ring"

# Speech-to-text writes the hotword in many ways: "Todo,", "To do:", "To-do."
HOTWORD = re.compile(r"^\s*(?:(to[\s-]?do)|(remind))\b[\s,.:;!-]*", re.IGNORECASE)


def pebble_org_entry(transcription: str, recorded_at_ms: int) -> tuple[str, str] | None:
    """
    Build the org entry for a ring recording.

    :param transcription: text from the Pebble webhook
    :param recorded_at_ms: recording time, Unix epoch in milliseconds
    :return: ("todo" | "journal", org text), or None for an empty transcription
    """
    text = (transcription or "").strip()
    if not text:
        return None

    # Server-local time, same as the Telegram entries (datetime.now()).
    when = datetime.fromtimestamp(recorded_at_ms / 1000).strftime("%Y-%m-%d %H:%M")  # noqa: DTZ006
    match = HOTWORD.match(text)

    if match and match.group(1):
        title = text[match.end():].strip() or text
        return "todo", f"** TODO {title}\nCreated at: [{when}] from {SOURCE}"
    if match:
        return "todo", f"** TODO {text}\nCreated at: [{when}] from {SOURCE}"
    return "journal", f"* Entry: [{when}] {SOURCE}\n{text}"


def pebble_token_ok(authorization: str | None, expected: str) -> bool:
    """
    Validate the "Authorization: Bearer <token>" header from the Pebble app.

    Unlike the Telegram check, an empty expected token rejects every request:
    this endpoint writes to the repo and must never be open.
    """
    if not expected or not authorization:
        return False
    return hmac.compare_digest(authorization, f"Bearer {expected}")
