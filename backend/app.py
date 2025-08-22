"""purrf service"""

from asgiref.wsgi import WsgiToAsgi
from flask import Flask, Blueprint
from http import HTTPStatus
from backend.common.error_handler import register_error_handlers
from backend.common.api_response_wrapper import api_response
from backend.historical_data.historical_controller import history_bp
from backend.notification_management.notification_controller import notification_bp
from backend.frontend_service.frontend_controller import frontend_bp
from backend.consumers.consumer_controller import consumers_bp


def create_app(
    notification_controller,
    consumer_controller,
    historical_controller,
    frontend_controller,
) -> Flask:
    """
    Create and configure the Flask application.

    This function initializes the Flask app, sets up error handlers,
    registers blueprints for different services (notification,
    frontend, consumers, history), and sets up required clients
    (Redis, Microsoft, Gerrit, Jira) if they are not provided.

    Args:
        notification_controller: A NotificationController instance.
        consumer_controller: A ConsumerController instance.
        historical_controller: A HistoricalController instance.
        frontend_controller: A FrontendController instance.

        ... another controller instance

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

    # Register new  blueprint
    all_api_bp = Blueprint("all_api", __name__, url_prefix="/api")

    notification_controller.register_routes(all_api_bp)
    consumer_controller.register_routes(all_api_bp)
    historical_controller.register_routes(all_api_bp)
    frontend_controller.register_routes(all_api_bp)

    app.register_blueprint(all_api_bp)

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint to verify if the application is running.

        Returns:
            API response with success status and HTTP 200 OK.
        """
        return api_response(
            success=True, message="Success.", data=None, status_code=HTTPStatus.OK
        )

    return app


if __name__ == "__main__":
    import os
    from asgiref.wsgi import WsgiToAsgi
    from backend.utils.app_dependency_builder import AppDependencyBuilder

    builder = AppDependencyBuilder()
    app = create_app(
        notification_controller=builder.notification_controller,
        consumer_controller=builder.consumer_controller,
        historical_controller=builder.historical_controller,
        frontend_controller=builder.frontend_controller,
    )

    # Used when running via uvicorn as a production server.
    if os.getenv("MOD") == "production":
        asgi_app = WsgiToAsgi(app)
    else:
        # Used when running directly using Flask development server.
        app.run(debug=True, host="0.0.0.0", port=5001)
