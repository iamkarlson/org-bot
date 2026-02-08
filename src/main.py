"""
GCP Cloud Functions entry point for org-bot.

This module provides the HTTP endpoint for Google Cloud Functions,
delegating all bot logic to the OrgBot class.
"""

import logging
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import functions_framework.aio
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from telegram import Update, Message

import sentry_sdk
from sentry_sdk.integrations.gcp import GcpIntegration

from .bot import OrgBot
from .config import BotSettings
from .tracing.log import GCPLogger


# Configure logging
logging.setLoggerClass(GCPLogger)
logger = logging.getLogger(__name__)

# Initialize Sentry
bot_config = BotSettings()
sentry_sdk.init(
    dsn=bot_config.sentry_dsn,
    integrations=[GcpIntegration()],
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# Create singleton OrgBot instance
org_bot = OrgBot()


# Media group handling infrastructure
@dataclass
class MediaGroupBuffer:
    """Buffer for collecting media group messages."""
    media_group_id: str
    messages: List[Message] = field(default_factory=list)
    message_ids: set[int] = field(default_factory=set)
    first_seen: float = 0.0
    last_seen: float = 0.0
    finalize_task: Optional[asyncio.Task[None]] = None
    done_event: asyncio.Event = field(default_factory=asyncio.Event)


# Module-level state (persists across function invocations within same instance)
_media_group_buffers: Dict[str, MediaGroupBuffer] = {}
_media_group_lock = asyncio.Lock()
_processing_lock = asyncio.Lock()

# Configuration
MEDIA_GROUP_TIMEOUT = 2.0  # seconds to wait after last photo
MAX_MEDIA_GROUP_WAIT = 10.0  # max total wait time
MAX_PHOTOS_PER_GROUP = 10  # safety limit


async def _collect_media_group(message: Message) -> MediaGroupBuffer:
    """Collect a media group message and ensure finalization is scheduled."""
    media_group_id = message.media_group_id
    if not media_group_id:
        raise ValueError("message.media_group_id is required")

    async with _media_group_lock:
        current_time = time.time()

        if media_group_id not in _media_group_buffers:
            _media_group_buffers[media_group_id] = MediaGroupBuffer(
                media_group_id=media_group_id,
                first_seen=current_time,
                last_seen=current_time,
            )

        buffer = _media_group_buffers[media_group_id]

        if message.message_id not in buffer.message_ids:
            buffer.messages.append(message)
            buffer.message_ids.add(message.message_id)

        buffer.last_seen = current_time

        time_since_first = current_time - buffer.first_seen
        should_force_process = (
            time_since_first >= MAX_MEDIA_GROUP_WAIT
            or len(buffer.messages) >= MAX_PHOTOS_PER_GROUP
        )

        if should_force_process:
            logger.info(
                "Media group forced complete",
                extra={
                    "media_group_id": media_group_id,
                    "message_count": len(buffer.messages),
                    "wait_time": time_since_first,
                },
            )
            # Process immediately (do not rely on background work after response).
            await _process_media_group_by_id(media_group_id)
            return buffer

        # Debounce finalization: cancel prior task and reschedule.
        if buffer.finalize_task is not None and not buffer.finalize_task.done():
            buffer.finalize_task.cancel()

        buffer.finalize_task = asyncio.create_task(
            _finalize_media_group_after_timeout(media_group_id)
        )

        return buffer


async def _finalize_media_group_after_timeout(media_group_id: str) -> None:
    try:
        await asyncio.sleep(MEDIA_GROUP_TIMEOUT)
        await _process_media_group_by_id(media_group_id)
    except asyncio.CancelledError:
        return
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.exception(
            "Error finalizing media group",
            extra={"media_group_id": media_group_id},
        )


async def _process_media_group_by_id(media_group_id: str) -> None:
    """Finalize and process a media group, then release all awaiting requests."""
    buffer: Optional[MediaGroupBuffer] = None
    try:
        async with _media_group_lock:
            buffer = _media_group_buffers.pop(media_group_id, None)

        if not buffer:
            return

        messages = sorted(buffer.messages, key=lambda m: m.message_id or 0)

        logger.info(
            "Processing media group",
            extra={
                "media_group_id": media_group_id,
                "message_count": len(messages),
                "wait_time": time.time() - buffer.first_seen,
            },
        )

        async with _processing_lock:
            await org_bot.handle_media_group(messages)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.exception(
            "Error processing media group",
            extra={"media_group_id": media_group_id},
        )
    finally:
        if buffer is not None:
            buffer.done_event.set()


async def _cleanup_stale_buffers() -> None:
    """Remove buffers older than 60 seconds."""
    async with _media_group_lock:
        current_time = time.time()
        stale_ids = [
            mid
            for mid, buf in _media_group_buffers.items()
            if current_time - buf.first_seen > 60
        ]
        for mid in stale_ids:
            logger.warning(
                "Cleaning up stale media group",
                extra={
                    "media_group_id": mid,
                    "age_seconds": current_time - _media_group_buffers[mid].first_seen,
                },
            )
            _media_group_buffers.pop(mid, None)


@functions_framework.aio.http
async def http_entrypoint(request: Request) -> Response:
    """
    HTTP webhook handler for Telegram updates.

    This function is called by Google Cloud Functions when a webhook
    is received from Telegram.

    Args:
        request: Flask request object containing the webhook data

    Returns:
        HTTP response with status code
    """
    try:
        # Health check endpoint
        if request.method == "GET":
            return JSONResponse({"statusCode": 200})

        # Process webhook
        if request.method == "POST":
            incoming_data = await request.json()
            logger.debug(f"Incoming data: {incoming_data}")

            # Parse Telegram update
            update = Update.de_json(incoming_data, org_bot._get_bot())
            message = update.message or update.edited_message

            # Process message if present
            if message:
                # Cleanup stale buffers periodically (10% of requests)
                if random.random() < 0.1:
                    await _cleanup_stale_buffers()

                # Check for media group
                if message.media_group_id:
                    logger.debug(
                        f"Media group message received: {message.media_group_id}",
                        extra={"media_group_id": message.media_group_id, "message_id": message.message_id}
                    )

                    buffer = await _collect_media_group(message)

                    # IMPORTANT (Cloud Run functions constraint): do not return until
                    # all work for this update is complete.
                    await asyncio.wait_for(
                        buffer.done_event.wait(),
                        timeout=MAX_MEDIA_GROUP_WAIT + MEDIA_GROUP_TIMEOUT + 5.0,
                    )
                else:
                    # Single message (no media group)
                    async with _processing_lock:
                        await org_bot.handle_update(message)

            return JSONResponse({"statusCode": 200})

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.exception("Error processing webhook")
        return JSONResponse({"statusCode": 200})  # Always return 200 to Telegram

    # Invalid request
    return JSONResponse({"statusCode": 422}, status_code=422)
