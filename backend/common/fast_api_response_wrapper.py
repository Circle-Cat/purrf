from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from http import HTTPStatus


def api_response(
    message: str,
    success: bool = True,
    data: dict | None = None,
    status_code: HTTPStatus = HTTPStatus.OK,
) -> JSONResponse:
    """
    Generate a standardized JSON API response.

    This function creates a consistent JSON response format for API endpoints,
    including a success flag, message, optional data payload, and HTTP status code.
    It is designed to be framework-light and works with FastAPI/Starlette's
    `JSONResponse`.

    Args:
        message (str): A descriptive message explaining the result of the API call.
        success (bool): Whether the API call succeeded (True) or failed (False).
        data (dict | None): Optional payload to include in the response body.
                            Can be None.
        status_code (HTTPStatus): The HTTP status code for the response.
                                  Defaults to HTTPStatus.OK (200).

    Returns:
        JSONResponse: A FastAPI/Starlette JSONResponse object containing the
                      structured response body and HTTP status code.

    Example:
        return api_response(
            success=True,
            message="User created successfully.",
            data={"user_id": 123},
            status_code=HTTPStatus.CREATED,
        )
    """

    response_body = {
        "success": success,
        "message": message,
        "data": data,
    }
    serialized_body = jsonable_encoder(response_body)

    return JSONResponse(
        status_code=status_code.value,
        content=serialized_body,
    )
