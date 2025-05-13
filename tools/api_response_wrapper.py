from flask import jsonify, Response, Flask
from http import HTTPStatus
from typing import Optional, Any


def api_response(
    success: bool,
    message: str,
    data: Optional = None,
    status_code: HTTPStatus = HTTPStatus.OK,
) -> Response:
    """Generate standardized API response."""

    response_body = {"message": message, "data": data if data is not None else {}}

    response = jsonify(response_body)
    response.status_code = status_code
    return response
