"""
ASGI entry point for the backend application.

This script performs the following steps:
1. Builds application dependencies via AppDependencyBuilder.
2. Creates the App instance with controllers injected.
3. Converts the Flask WSGI app to an ASGI app using WsgiToAsgi.
4. The resulting `asgi_app` can be run with any ASGI server (e.g., Uvicorn, Hypercorn).

Example usage:
    uvicorn backend.asgi_app:asgi_app --host 0.0.0.0 --port 5001
"""

from asgiref.wsgi import WsgiToAsgi
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
asgi_app = WsgiToAsgi(app)
