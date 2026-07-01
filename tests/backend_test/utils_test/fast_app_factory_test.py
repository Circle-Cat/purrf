import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, APIRouter
from backend.utils.fast_app_factory import FastAppFactory


class TestFastAppFactory(unittest.TestCase):
    def setUp(self):
        self.mock_controller = MagicMock()
        self.mock_controller.router = APIRouter()
        self.mock_profile_controller = MagicMock()
        self.mock_profile_controller.router = APIRouter()
        self.mock_service = MagicMock()

        self.factory = FastAppFactory(
            authentication_controller=self.mock_controller,
            authentication_service=self.mock_service,
            user_identity_service=MagicMock(),
            user_permissions_repository=MagicMock(),
            notification_controller=self.mock_controller,
            historical_controller=self.mock_controller,
            consumer_controller=self.mock_controller,
            internal_activity_controller=self.mock_controller,
            profile_controller=self.mock_profile_controller,
            mentorship_controller=self.mock_controller,
            mentorship_admin_controller=self.mock_controller,
            email_management_controller=self.mock_controller,
            permission_admin_controller=self.mock_controller,
            recruiting_controller=self.mock_controller,
            application_controller=self.mock_controller,
            launchdarkly_client=MagicMock(),
            database=MagicMock(),
            logger=MagicMock(),
        )

    def test_factory_initialization(self):
        """Test whether the factory class can be instantiated."""
        self.assertIsInstance(self.factory, FastAppFactory)
        self.assertEqual(self.factory.authentication_controller, self.mock_controller)
        self.assertEqual(self.factory.authentication_service, self.mock_service)
        self.assertEqual(self.factory.notification_controller, self.mock_controller)
        self.assertEqual(self.factory.historical_controller, self.mock_controller)
        self.assertEqual(self.factory.consumer_controller, self.mock_controller)
        self.assertEqual(
            self.factory.internal_activity_controller, self.mock_controller
        )
        self.assertEqual(self.factory.mentorship_controller, self.mock_controller)
        self.assertEqual(self.factory.recruiting_controller, self.mock_controller)
        self.assertEqual(self.factory.application_controller, self.mock_controller)

    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI application instance."""
        app = self.factory.create_app()
        self.assertIsInstance(app, FastAPI)

    def test_recruiting_routes_are_mounted(self):
        """The recruiting controller's router is mounted under /api."""
        recruiting = MagicMock()
        router = APIRouter()

        @router.get("/recruiting/ping")
        def _ping():
            return {}

        recruiting.router = router
        factory = FastAppFactory(
            authentication_controller=self.mock_controller,
            authentication_service=self.mock_service,
            user_identity_service=MagicMock(),
            user_permissions_repository=MagicMock(),
            notification_controller=self.mock_controller,
            historical_controller=self.mock_controller,
            consumer_controller=self.mock_controller,
            internal_activity_controller=self.mock_controller,
            profile_controller=self.mock_profile_controller,
            mentorship_controller=self.mock_controller,
            mentorship_admin_controller=self.mock_controller,
            email_management_controller=self.mock_controller,
            permission_admin_controller=self.mock_controller,
            recruiting_controller=recruiting,
            application_controller=self.mock_controller,
            launchdarkly_client=MagicMock(),
            database=MagicMock(),
            logger=MagicMock(),
        )

        app = factory.create_app()

        self.assertIn("/api/recruiting/ping", {route.path for route in app.routes})

    def test_application_routes_are_mounted(self):
        """The application controller's router is mounted under /api."""
        application = MagicMock()
        router = APIRouter()

        @router.get("/recruiting/applications/ping")
        def _ping():
            return {}

        application.router = router
        factory = FastAppFactory(
            authentication_controller=self.mock_controller,
            authentication_service=self.mock_service,
            user_identity_service=MagicMock(),
            user_permissions_repository=MagicMock(),
            notification_controller=self.mock_controller,
            historical_controller=self.mock_controller,
            consumer_controller=self.mock_controller,
            internal_activity_controller=self.mock_controller,
            profile_controller=self.mock_profile_controller,
            mentorship_controller=self.mock_controller,
            mentorship_admin_controller=self.mock_controller,
            email_management_controller=self.mock_controller,
            permission_admin_controller=self.mock_controller,
            recruiting_controller=self.mock_controller,
            application_controller=application,
            launchdarkly_client=MagicMock(),
            database=MagicMock(),
            logger=MagicMock(),
        )

        app = factory.create_app()

        self.assertIn(
            "/api/recruiting/applications/ping",
            {route.path for route in app.routes},
        )

    @patch("backend.utils.fast_app_factory.register_exception_handlers")
    def test_exception_handler_registration_called(self, mock_register):
        """
        Test that the exception handler registration function is called
        when the application is created.
        """
        self.factory.create_app()

        # register_exception_handlers should be called exactly once
        mock_register.assert_called_once()

        # It should receive a FastAPI instance
        call_args = mock_register.call_args
        self.assertIsInstance(call_args[0][0], FastAPI)

    def test_auth_middleware_added(self):
        """Test that AuthMiddleware is added to the FastAPI app."""
        app = self.factory.create_app()
        # FastAPI middleware is stored in app.user_middleware
        middleware_classes = [m.cls for m in app.user_middleware]
        from backend.utils.auth_middleware import AuthMiddleware

        self.assertIn(AuthMiddleware, middleware_classes)


class TestFastAppFactoryLifespan(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_controller = MagicMock()
        self.mock_controller.router = APIRouter()
        self.mock_profile_controller = MagicMock()
        self.mock_profile_controller.router = APIRouter()
        self.mock_service = MagicMock()
        self.mock_launchdarkly_client = MagicMock()

        self.mock_database = MagicMock()
        self.mock_database.close = AsyncMock()

        self.factory = FastAppFactory(
            authentication_controller=self.mock_controller,
            authentication_service=self.mock_service,
            user_identity_service=MagicMock(),
            user_permissions_repository=MagicMock(),
            notification_controller=self.mock_controller,
            historical_controller=self.mock_controller,
            consumer_controller=self.mock_controller,
            internal_activity_controller=self.mock_controller,
            profile_controller=self.mock_profile_controller,
            mentorship_controller=self.mock_controller,
            mentorship_admin_controller=self.mock_controller,
            email_management_controller=self.mock_controller,
            permission_admin_controller=self.mock_controller,
            recruiting_controller=self.mock_controller,
            application_controller=self.mock_controller,
            launchdarkly_client=self.mock_launchdarkly_client,
            database=self.mock_database,
            logger=MagicMock(),
        )

    async def test_lifespan_closes_database_on_shutdown(self):
        """Test that database.close is awaited during FastAPI lifespan shutdown."""
        app = self.factory.create_app()

        async with app.router.lifespan_context(app):
            pass

        self.mock_database.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
