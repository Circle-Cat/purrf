from flask import Blueprint, request
from http import HTTPStatus
from src.historical_data.microsoft_ldap_fetcher import sync_microsoft_members_to_redis
from src.historical_data.gerrit_history_fetcher import fetch_and_store_changes
from src.historical_data.google_chat_history_fetcher import fetch_history_messages
from src.common.api_response_wrapper import api_response
from src.historical_data.microsoft_chat_history_fetcher import (
    sync_microsoft_chat_messages_by_chat_id,
)


history_bp = Blueprint("history", __name__, url_prefix="/api")


@history_bp.route("/microsoft/backfill/ldaps", methods=["POST"])
async def backfill_microsoft_ldaps():
    """API endpoint to backfill Microsoft 365 user LDAP information into Redis."""

    response = await sync_microsoft_members_to_redis()

    return api_response(
        success=True,
        message="Saved successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )


@history_bp.route("/gerrit/backfill", methods=["POST"])
async def backfill_gerrit_changes():
    """API endpoint to backfill Gerrit changes into Redis."""

    body = request.get_json(silent=True) or {}
    statuses = body.get("statuses")

    fetch_and_store_changes(statuses=statuses)

    return api_response(
        success=True,
        message="Saved successfully.",
        data="",
        status_code=HTTPStatus.OK,
    )


@history_bp.route("/microsoft/fetch/history/messages/<chatId>", methods=["POST"])
async def backfill_microsoft_chat_messages(chatId):
    """API endpoint to backfill Microsoft Teams Chat messages into Redis."""
    response = await sync_microsoft_chat_messages_by_chat_id(chatId)

    return api_response(
        success=True,
        message="Saved successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )


@history_bp.route("/google/chat/spaces/messages", methods=["POST"])
def history_messages():
    """API endpoint to trigger the fetching of messages for all SPACE type chat spaces and store them in Redis asynchronously."""

    response = fetch_history_messages()
    return api_response(
        success=True,
        message="Saved successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )
