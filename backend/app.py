from flask import Flask, Blueprint
from http import HTTPStatus
from backend.common.error_handler import register_error_handlers
from backend.common.api_response_wrapper import api_response


class App:
    """
    A factory class to assemble and configure the Flask application.
    This class encapsulates the application creation logic and its dependencies.
    """

    def __init__(
        self,
        consumer_controller,
        historical_controller,
        frontend_controller,
    ):
        """
        Initializes the factory with controller dependencies.

        Args:
            consumer_controller: An instance of ConsumerController.
            historical_controller: An instance of HistoricalController.
            frontend_controller: An instance of FrontendController.
        """
        self.consumer_controller = consumer_controller
        self.historical_controller = historical_controller
        self.frontend_controller = frontend_controller

    def create_app(self) -> Flask:
        """
        Creates and configures the Flask application instance.

        Returns:
            Flask app instance configured with required services.
        """
        # Initialize the Flask app
        app = Flask(__name__)
        register_error_handlers(app)

        # Register new blueprint for all API routes
        all_api_bp = Blueprint("all_api", __name__, url_prefix="/api")

        # Register routes using the injected controllers
        self.consumer_controller.register_routes(all_api_bp)
        self.historical_controller.register_routes(all_api_bp)
        self.frontend_controller.register_routes(all_api_bp)

        app.register_blueprint(all_api_bp)

        @app.route("/health", methods=["GET"])
        def health_check():
            """
            Health check endpoint to verify if the application is running.
            """
            return api_response(
                success=True, message="Success.", data=None, status_code=HTTPStatus.OK
            )

        return app
