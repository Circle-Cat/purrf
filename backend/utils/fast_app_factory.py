from fastapi import FastAPI
from backend.common.fast_api_error_handler import register_exception_handlers


class FastAppFactory:
    """
    Factory class for creating and configuring a FastAPI application.

    This class encapsulates the setup of the FastAPI app, including
    routing, dependencies, and any middleware or configuration.
    """

    def __init__(self):
        """
        Initialize the factory.

        TODO: Extending this method to accept configuration parameters
        or dependency overrides for testing or production environments.
        """
        pass

    def create_app(self) -> FastAPI:
        """
        Create and configure a FastAPI application instance.

        This method sets up the application routes, dependencies, and any
        required middleware.

        Returns:
            FastAPI: A fully configured FastAPI application instance.
        """
        # Initialize the FastAPI app
        app = FastAPI()

        register_exception_handlers(app)

        @app.get("/fastapi/health")
        def health_check():
            """
            Health check endpoint.

            Returns a simple JSON response to verify that the
            application is running.

            Returns:
                dict: JSON containing the health status.
            """
            return {"Hello": "World!"}

        return app
