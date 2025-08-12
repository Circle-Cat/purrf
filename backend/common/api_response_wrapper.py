from flask import jsonify, Response
from http import HTTPStatus
from typing import Optional


def api_response(
    success: bool,
    message: str,
    data: Optional = None,
    status_code: HTTPStatus = HTTPStatus.OK,
) -> Response:
    """
    Generate a standardized JSON API response.

    This function creates a consistent JSON response format for API endpoints,
    including a success flag, message, optional data payload, and HTTP status code.

    Args:
        success (bool): Indicates whether the API call was successful (True) or failed (False).
        message (str): A descriptive message about the result of the API call.
        data (Optional): Optional data to include in the response body. Defaults to an empty dict if None.
        status_code (HTTPStatus, optional): HTTP status code for the response. Defaults to HTTP 200 OK.

    Returns:
        flask.Response: A Flask Response object containing the JSON-serialized
                        response body and the specified HTTP status code.

    Example:
        response = api_response(
            success=True,
            message="User created successfully.",
            data={"user_id": 123},
            status_code=HTTPStatus.CREATED
        )
    """

    response_body = {"message": message, "data": data if data is not None else {}}

    response = jsonify(response_body)
    response.status_code = status_code
    return response
