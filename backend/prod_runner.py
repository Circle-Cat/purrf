"""
ASGI entry point for the backend application.

This script performs the following steps:
1. Builds application dependencies via AppDependencyBuilder.
2. Creates the FastAPI application instance with injected dependencies and controllers
   using the fast_app_factory.
3. The resulting app instance is a native ASGI application.
4. The application can be run with any ASGI server (e.g., Uvicorn, Hypercorn).

Example usage:
    uvicorn backend.prod_runner:asgi_app --host 0.0.0.0 --port 5001
"""

from backend.utils.app_dependency_builder import AppDependencyBuilder


# Build application dependencies
builder = AppDependencyBuilder()

# Create FastAPI app with injected dependencies
asgi_app = builder.fast_app_factory.create_app(is_prod=True)
