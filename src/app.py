"""purrf service"""

from flask import Flask, jsonify
from http import HTTPStatus
from src.common.error_handler import register_error_handlers
from src.common.api_response_wrapper import api_response
from src.historical_data.historical_api import history_bp

app = Flask(__name__)
register_error_handlers(app)
app.register_blueprint(history_bp)


@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.

    This endpoint is used to verify that the application is running and responsive.
    It returns a standardized success response with HTTP 200 OK status.

    Returns:
        flask.Response: A Flask JSON response indicating the service is healthy.
    """
    return api_response(
        success=True, message="Success.", data=None, status_code=HTTPStatus.OK
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
