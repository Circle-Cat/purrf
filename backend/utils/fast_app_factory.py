from fastapi import FastAPI
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.utils.auth_middleware import AuthMiddleware


class FastAppFactory:
    """
    Factory class for creating and configuring a FastAPI application.

    This class encapsulates the setup of the FastAPI app, including
    routing, dependencies, and any middleware or configuration.
    """

    def __init__(self, authentication_controller, authentication_service):
        """
        Initialize the factory.

        Args:
            authentication_controller: Controller instance responsible for authentication routes.
            authentication_service: AuthenticationService instance used by middleware to validate requests.

        TODO: Extending this method to accept configuration parameters
        or dependency overrides for testing or production environments.
        """
        self.authentication_controller = authentication_controller
        self.authentication_service = authentication_service

    def create_app(self) -> FastAPI:
        """
        Create and configure a FastAPI application instance.

        This method performs the following setup steps:
            1. Initializes the FastAPI application.
            2. Registers global exception handlers.
            3. Adds authentication middleware using AuthMiddleware.
            4. Registers the controller routes under the '/api' prefix.
            5. Adds a simple health check endpoint at '/fastapi/health'.

        Returns:
            FastAPI: A fully configured FastAPI application instance.

        Example:
            factory = FastAppFactory(auth_controller, auth_service)
            app = factory.create_app()
        """
        # Initialize the FastAPI app
        app = FastAPI()

        # Register global exception handlers
        register_exception_handlers(app)

        # Add authentication middleware
        app.add_middleware(AuthMiddleware, auth_service=self.authentication_service)

        # Include authentication routes
        app.include_router(self.authentication_controller.router, prefix="/api")

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
