"""purrf service"""

from flask import Flask, jsonify
from http import HTTPStatus
from google.google_api import google_bp
from tools.global_handle_exception.exception_handler import register_error_handlers
from redis_dal.redis_api import redis_api

app = Flask(__name__)
register_error_handlers(app)
# Register all submodule APIs
app.register_blueprint(google_bp)
app.register_blueprint(redis_api, url_prefix="/api")


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "success"}), HTTPStatus.OK


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
