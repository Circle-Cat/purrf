"""purrf service"""

from flask import Flask, jsonify
from http import HTTPStatus
from google.google_api import google_bp
from tools.global_handle_exception.exception_handler import register_error_handlers

app = Flask(__name__)
register_error_handlers(app)

app.register_blueprint(google_bp)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "success"}), HTTPStatus.OK


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
