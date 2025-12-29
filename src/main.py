"""
GCP Cloud Functions entry point for org-bot.

This module provides the HTTP endpoint for Google Cloud Functions,
delegating all bot logic to the OrgBot class.
"""

import logging
import asyncio
import functions_framework
from flask import Request, abort
from telegram import Update

import sentry_sdk
from sentry_sdk.integrations.gcp import GcpIntegration

from .bot import OrgBot
from .config import BotConfig
from .tracing.log import GCPLogger


# Configure logging
logging.setLoggerClass(GCPLogger)
logger = logging.getLogger(__name__)

# Initialize Sentry
bot_config = BotConfig.from_env()
sentry_sdk.init(
    dsn=bot_config.sentry_dsn,
    integrations=[GcpIntegration()],
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# Create singleton OrgBot instance
org_bot = OrgBot()


@functions_framework.http
def http_entrypoint(request: Request):
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
            return {"statusCode": 200}

        # Process webhook
        if request.method == "POST":
            incoming_data = request.get_json()
            logger.debug(f"Incoming data: {incoming_data}")

            # Parse Telegram update
            update = Update.de_json(incoming_data, org_bot._get_bot())
            message = update.message or update.edited_message

            # Process message if present
            if message:
                asyncio.run(org_bot.handle_update(message))

            return {"statusCode": 200}

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.exception("Error processing webhook")
        return {"statusCode": 200}  # Always return 200 to Telegram

    # Invalid request
    abort(422)
