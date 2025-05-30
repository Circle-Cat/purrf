from flask import Blueprint
from http import HTTPStatus
from src.historical_data.microsoft_ldap_fetcher import sync_microsoft_members_to_redis
from src.common.api_response_wrapper import api_response

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
