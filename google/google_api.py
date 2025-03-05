"""google chat service"""

from flask import Flask
from tools.global_handle_exception.exception_handler import register_error_handlers

app = Flask(__name__)
register_error_handlers(app)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
