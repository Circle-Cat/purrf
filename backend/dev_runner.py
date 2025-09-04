"""
Entry point for running the backend Flask application.

This script performs the following steps:
1. Builds application dependencies via AppDependencyBuilder.
2. Creates the App instance with controllers injected.
3. Instantiates the Flask app.
4. Runs the app on host 0.0.0.0 and port 5001 in debug mode.
"""

from backend.utils.app_dependency_builder import AppDependencyBuilder
from backend.app import App

builder = AppDependencyBuilder()

app_factory = App(
    notification_controller=builder.notification_controller,
    consumer_controller=builder.consumer_controller,
    historical_controller=builder.historical_controller,
    frontend_controller=builder.frontend_controller,
)

app = app_factory.create_app()
app.run(debug=True, host="0.0.0.0", port=5001)
