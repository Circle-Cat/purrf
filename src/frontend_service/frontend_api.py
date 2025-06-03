from flask import Blueprint
from http import HTTPStatus
from src.frontend_service.ldap_loader import get_all_ldaps_and_displaynames
from src.common.constants import MicrosoftAccountStatus
from src.common.api_response_wrapper import api_response

frontend_bp = Blueprint("frontend", __name__, url_prefix="/api")


@frontend_bp.route("/microsoft/<status>/ldaps", methods=["GET"])
async def all_ldaps_and_names(status):
    """API endpoint to get Microsoft 365 user LDAP information from Redis."""
    response = get_all_ldaps_and_displaynames(
        MicrosoftAccountStatus.validate_status(status)
    )

    return api_response(
        success=True,
        message="Saved successfully.",
        data=response,
        status_code=HTTPStatus.OK,
    )
