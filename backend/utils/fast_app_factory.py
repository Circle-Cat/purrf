from fastapi import FastAPI
from backend.common.fast_api_error_handler import register_exception_handlers
from backend.utils.auth_middleware import AuthMiddleware


class FastAppFactory:
    """
    Factory class for creating and configuring a FastAPI application.

    This class encapsulates the setup of the FastAPI app, including
    routing, dependencies, and any middleware or configuration.
    """

    def __init__(
        self,
        authentication_controller,
        authentication_service,
        notification_controller,
        historical_controller,
        consumer_controller,
        frontend_controller,
    ):
        """
        Initialize the factory.

        Args:
            authentication_controller: Controller instance responsible for authentication routes.
            authentication_service: AuthenticationService instance used by middleware to validate requests.
            notification_controller: An instance of NotificationController that manages API routes for subscribe_microsoft_chat_messages and subscribe_google_chat_space.
            notification_controller: An instance of HistoricalController that manages API routes for sync historical data.
            consumer_controller: An instance of ConsumerController that manages API routes to trigger, check, or stop subscribers.
            frontend_controller: An instance of FrontendController that manages API routes to query internal activity data.
        """
        self.authentication_controller = authentication_controller
        self.authentication_service = authentication_service
        self.notification_controller = notification_controller
        self.historical_controller = historical_controller
        self.consumer_controller = consumer_controller
        self.frontend_controller = frontend_controller

    def create_app(self, is_prod: bool = False) -> FastAPI:
        """
        Create and configure a FastAPI application instance.

        This method performs the following setup steps:
            1. Initializes the FastAPI application.
                - In production mode (is_prod=True), disables Swagger UI, ReDoc,
                    and the OpenAPI schema endpoints.
                - In non-production mode, exposes:
                    * Swagger UI at '/docs'
                    * ReDoc at '/redoc'
                    * OpenAPI schema at '/openapi.json'
            2. Registers global exception handlers.
            3. Adds authentication middleware using AuthMiddleware.
            4. Registers the controller routes under the '/api' prefix.
            5. Adds a simple health check endpoint at '/fastapi/health'.

        Args:
            is_prod (bool): Whether the application is running in production mode.
                If True, API documentation and schema endpoints are disabled.
                Defaults to False.

        Returns:
            FastAPI: A fully configured FastAPI application instance.

        Example:
            factory = FastAppFactory(auth_controller, auth_service)
            app = factory.create_app()
        """
        # Initialize the FastAPI app
        app = FastAPI(
            docs_url=None if is_prod else "/docs",
            redoc_url=None if is_prod else "/redoc",
            openapi_url=None if is_prod else "/openapi.json",
        )

        # Register global exception handlers
        register_exception_handlers(app)

        # Add authentication middleware
        app.add_middleware(AuthMiddleware, auth_service=self.authentication_service)

        # Include authentication routes
        app.include_router(self.authentication_controller.router, prefix="/api")
        app.include_router(self.notification_controller.router, prefix="/api")
        app.include_router(self.historical_controller.router, prefix="/api")
        app.include_router(self.consumer_controller.router, prefix="/api")
        app.include_router(self.frontend_controller.router, prefix="/api")

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
