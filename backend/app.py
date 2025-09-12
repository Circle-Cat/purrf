from flask import Flask, Blueprint
from http import HTTPStatus
from backend.common.error_handler import register_error_handlers
from backend.common.api_response_wrapper import api_response
from backend.historical_data.historical_controller import history_bp
from backend.notification_management.notification_controller import notification_bp
from backend.frontend_service.frontend_controller import frontend_bp
from backend.consumers.consumer_controller import consumers_bp


class App:
    """
    A factory class to assemble and configure the Flask application.
    This class encapsulates the application creation logic and its dependencies.
    """

    def __init__(
        self,
        notification_controller,
        consumer_controller,
        historical_controller,
        frontend_controller,
    ):
        """
        Initializes the factory with controller dependencies.

        Args:
            notification_controller: An instance of NotificationController.
            consumer_controller: An instance of ConsumerController.
            historical_controller: An instance of HistoricalController.
            frontend_controller: An instance of FrontendController.
        """
        self.notification_controller = notification_controller
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

        # Register existing blueprints for various services
        # TODO: Deleted them after migration.
        app.register_blueprint(notification_bp)
        app.register_blueprint(frontend_bp)
        app.register_blueprint(consumers_bp)
        app.register_blueprint(history_bp)
        # ---

        # Register new blueprint for all API routes
        all_api_bp = Blueprint("all_api", __name__, url_prefix="/api")

        # Register routes using the injected controllers
        self.notification_controller.register_routes(all_api_bp)
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
