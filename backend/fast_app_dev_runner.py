"""
Production ASGI entry point for the FastAPI backend application.

This script performs the following steps:
1. Builds application dependencies via AppDependencyBuilder.
2. Creates the FastAPI application instance with all controllers/services injected.
3. Runs the application using Uvicorn ASGI server.
"""

import uvicorn
from backend.utils.app_dependency_builder import AppDependencyBuilder

# Build application dependencies
builder = AppDependencyBuilder()

# Create FastAPI app with injected dependencies
app = builder.fast_app_factory.create_app()

# Run the ASGI server (development mode)
if __name__ == "__main__":
    uvicorn.run(
        "backend.fast_app_dev_runner:app", host="0.0.0.0", port=5001, reload=True
    )
