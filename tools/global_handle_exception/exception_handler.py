from flask import jsonify
import http.client
from tools.log.logger import setup_logger
import logging
from tools.global_handle_exception.constants import (
    VALUE_ERROR_LOG_MSG,
    RUNTIME_ERROR_LOG_MSG,
    UNEXPECTED_ERROR_LOG_MSG,
    ERROR_MESSAGE,
)

setup_logger()


def handle_exception(e):
    """
    Handle exceptions and return appropriate JSON error responses.

    This function processes different types of exceptions, logs them with appropriate
    error levels, and returns formatted JSON responses with corresponding HTTP status codes.

    Args:
        e (Exception): The exception object to be handled

    Returns:
        Tuple[flask.Response, int]: A tuple containing:
                    - A JSON response object (flask.Response) with an error message.
                    - An integer HTTP status code.

    Supported Exception Types:
        - ValueError: Returns 400 Bad Request
        - RuntimeError: Returns 503 Service Unavailable
        - Other exceptions: Returns 500 Internal Server Error

    Example:
        try:
            raise ValueError("Invalid input")
        except Exception as e:
            response, status_code = handle_exception(e)
        # Returns JSON response with status code 400
    """
    response = {ERROR_MESSAGE: str(e)}
    status_code: int
    if isinstance(e, ValueError):
        logging.error(VALUE_ERROR_LOG_MSG.format(error_msg=str(e)))
        status_code = http.client.BAD_REQUEST
    elif isinstance(e, RuntimeError):
        logging.error(RUNTIME_ERROR_LOG_MSG.format(error_msg=str(e)))
        status_code = http.client.SERVICE_UNAVAILABLE
    else:
        logging.error(UNEXPECTED_ERROR_LOG_MSG.format(error_msg=str(e)))
        status_code = http.client.INTERNAL_SERVER_ERROR
    return jsonify(response), status_code


def register_error_handlers(app):
    """
    Register error handlers for a Flask application.

    This function sets up the application's error handling by registering
    the handle_exception function as the handler for all Exception types.

    Args:
        app (flask.Flask): The Flask application instance to register handlers for

    Returns:
        None

    Example:
        from flask import Flask
        app = Flask(__name__)
        register_error_handlers(app)
        # All exceptions in the app will now be handled by handle_exception
    """
    app.register_error_handler(Exception, handle_exception)
