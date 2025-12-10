from http import HTTPStatus
from backend.common.fast_api_response_wrapper import api_response
from backend.common.logger import get_logger
from fastapi import Request, FastAPI
from fastapi.exceptions import RequestValidationError

logger = get_logger()


async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler used to convert Python exceptions into a unified API response.
    It also performs structured logging while preventing sensitive information from leaking
    to the client.
    """

    # Determine the HTTP status code based on the type of exception.
    match exc:
        case ValueError() | RequestValidationError():
            status = HTTPStatus.BAD_REQUEST
        case RuntimeError():
            status = HTTPStatus.SERVICE_UNAVAILABLE
        case _:
            status = HTTPStatus.INTERNAL_SERVER_ERROR

    # Extract information from the request path.
    parts = request.url.path.strip("/").split("/")
    platform = parts[1] if len(parts) > 1 else "unknown"
    is_server_error = status >= 500

    # The design separates the "log message" from the "user-facing message".
    # The log message always contains the full raw error details.
    log_msg = str(exc)

    # The user-facing message hides sensitive details for server errors,
    # simplifies validation errors, and otherwise displays the original message.
    if is_server_error:
        user_message = "Internal Server Error. Please contact support."
    elif isinstance(exc, RequestValidationError):
        first_error = exc.errors()[0]
        user_message = (
            f"Validation Error: {first_error.get('loc', [])[-1]} - "
            f"{first_error.get('msg')}"
        )
    else:
        user_message = str(exc)

    # Log the error. Full stack traces are logged only for server-side errors.
    log_method = logger.error if is_server_error else logger.warning
    log_method(
        "[%s] %s on platform [%s]: %s",
        "Server Error" if is_server_error else "Client Error",
        type(exc).__name__,
        platform,
        log_msg,
        exc_info=is_server_error,
    )

    # Return a unified JSON API response to the client.
    return api_response(
        success=False,
        message=user_message,
        status_code=status,
    )


def register_exception_handlers(app: FastAPI):
    """
    Registers the global exception handlers on the provided FastAPI application.
    This ensures unexpected exceptions are consistently processed and returned
    in the standard API response format.
    """
    for exc_cls in (Exception, RequestValidationError):
        app.add_exception_handler(exc_cls, global_exception_handler)
