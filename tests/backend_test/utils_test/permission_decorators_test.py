import unittest
from unittest.mock import MagicMock, patch
from http import HTTPStatus
from starlette.requests import Request
from backend.utils.permission_decorators import authenticate
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel


class ItemUpdatePayload(BaseModel):
    name: str
    description: str | None = None


class TestAuthenticateDecorator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch api_response
        patcher = patch("backend.utils.permission_decorators.api_response")
        self.mock_api_response = patcher.start()
        self.addCleanup(patcher.stop)

        # Make api_response return a mock response with status_code
        def fake_api_response(*args, **kwargs):
            resp = MagicMock()
            resp.status_code = kwargs.get("status_code")
            return resp

        self.mock_api_response.side_effect = fake_api_response
        self.mock_request = MagicMock(spec=Request)
        self.mock_request.state = MagicMock()

        self.mock_user = MagicMock()
        self.mock_user.sub = "user_123"
        self.mock_user.roles = ["admin", "editor"]
        self.mock_user.primary_email = "test@example.com"

    async def test_no_user_in_state_returns_401(self):
        """Requirement: return 401 if no user is found in request state."""
        self.mock_request.state.user = None

        @authenticate()
        async def dummy_func():
            return "success"

        response = await dummy_func(request=self.mock_request)

        # Verify that api_response returns a 401 status code
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    async def test_insufficient_permissions_returns_403(self):
        """Requirement: return 403 when user roles do not match required roles."""
        self.mock_request.state.user = self.mock_user

        @authenticate(roles=["super_admin"])  # User has admin, not super_admin
        async def dummy_func():
            return "success"

        response = await dummy_func(request=self.mock_request)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    async def test_sufficient_permissions_calls_func(self):
        """Requirement: successfully call the function when roles match."""
        self.mock_request.state.user = self.mock_user

        @authenticate(roles=["admin"])
        async def dummy_func():
            return "called"

        response = await dummy_func(request=self.mock_request)
        self.assertEqual(response, "called")

    async def test_inject_current_user(self):
        """Requirement: automatically inject the current_user parameter."""
        self.mock_request.state.user = self.mock_user

        @authenticate()
        async def dummy_func(current_user):
            return current_user

        response = await dummy_func(request=self.mock_request)
        # Verify the injected object is the mocked user
        self.assertEqual(response, self.mock_user)
        self.assertEqual(response.sub, "user_123")

    async def test_inject_user_sub(self):
        """Requirement: automatically inject the user_sub parameter."""
        self.mock_request.state.user = self.mock_user

        @authenticate()
        async def dummy_func(user_sub: str):
            return user_sub

        response = await dummy_func(request=self.mock_request)
        self.assertEqual(response, "user_123")

    async def test_mixed_params_filtering_request(self):
        """
        Requirement: the business function should not receive the request parameter,
        but should still receive other business parameters.
        """
        self.mock_request.state.user = self.mock_user

        @authenticate(roles=["admin"])
        async def dummy_func(payload: dict, user_sub: str):
            return {"payload": payload, "sub": user_sub}

        test_payload = {"key": "value"}
        # Simulate FastAPI call: pass in request and business parameters
        response = await dummy_func(request=self.mock_request, payload=test_payload)

        self.assertEqual(response["payload"], test_payload)
        self.assertEqual(response["sub"], "user_123")

    async def test_no_roles_specified_only_checks_login(self):
        """Requirement: when no roles are specified, only check that the user exists."""
        self.mock_request.state.user = self.mock_user

        @authenticate()  # Login check only
        async def dummy_func():
            return "ok"

        response = await dummy_func(request=self.mock_request)
        self.assertEqual(response, "ok")

    async def test_manual_decoration_of_bound_method(self):
        """
        Scenario: endpoint = authenticate(roles=["admin"])(self.cleanup_system)

        Verify:
        1. The decorator can correctly handle bound methods of a class.
        2. The `self` parameter is preserved.
        3. Parameters such as user_sub are correctly injected into the method.
        """

        # Define an internal mock Controller class
        class MockController:
            def __init__(self):
                self.was_called = False
                self.captured_sub = None

            async def cleanup_system(self, payload: dict, user_sub: str):
                self.was_called = True
                self.captured_sub = user_sub
                return {"result": "ok", "data": payload}

        controller = MockController()

        # Simulate middleware injecting a user with admin role
        self.mock_request.state.user = self.mock_user

        # Manually decorate (simulating behavior in add_api_route)
        # Here controller.cleanup_system is a bound method and already carries `self`
        decorated_endpoint = authenticate(roles=["admin"])(controller.cleanup_system)

        # Simulate FastAPI calling the endpoint
        test_payload = {"action": "delete_logs"}
        response = await decorated_endpoint(
            request=self.mock_request, payload=test_payload
        )

        # Assertions
        # Verify the original method was executed
        self.assertTrue(controller.was_called)
        # Verify injection worked
        self.assertEqual(controller.captured_sub, "user_123")
        # Verify business return value
        self.assertEqual(response["result"], "ok")
        self.assertEqual(response["data"], test_payload)

    async def test_manual_decoration_forbidden_scenario(self):
        """Scenario: insufficient permissions when manually decorating a method."""

        class MockController:
            async def secure_action(self):
                return "should not be called"

        controller = MockController()

        # Simulate a low-privilege user without admin role
        low_privilege_user = MagicMock()
        low_privilege_user.roles = ["guest"]
        self.mock_request.state.user = low_privilege_user

        # Manual decoration
        decorated_endpoint = authenticate(roles=["admin"])(controller.secure_action)

        # Execute
        response = await decorated_endpoint(request=self.mock_request)

        # Assert: should return 403 api_response and not call the original method
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestFastAPIParamsIntegration(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()

        # Mock authentication middleware
        @self.app.middleware("http")
        async def mock_auth_middleware(request: Request, call_next):
            role = request.headers.get("x-test-role", "admin")
            user = type(
                "User",
                (),
                {
                    "sub": "user_12345",
                    "roles": [role],
                },
            )
            request.state.user = user
            return await call_next(request)

        class ComplexController:
            def __init__(self):
                self.router = APIRouter()

                # 1. Test path parameters
                self.router.add_api_route(
                    "/items/{item_id}",
                    endpoint=authenticate()(self.get_item),
                    methods=["GET"],
                )

                # 2. Test query parameters
                self.router.add_api_route(
                    "/search",
                    endpoint=authenticate()(self.search_items),
                    methods=["GET"],
                )

                # 3. Mixed scenario: path + query + body + injected params
                self.router.add_api_route(
                    "/update/{item_id}",
                    endpoint=authenticate(roles=["admin"])(self.update_item),
                    methods=["PUT"],
                )

            async def get_item(self, item_id: str):
                return {"item_id": item_id}

            async def search_items(self, category: str, limit: int = 10):
                return {"category": category, "limit": limit}

            async def update_item(
                self,
                item_id: str,
                payload: ItemUpdatePayload,
                user_sub: str,
                priority: int = 1,
            ):
                return {
                    "item_id": item_id,
                    "updated_by": user_sub,
                    "new_name": payload.name,
                    "priority": priority,
                }

        self.controller = ComplexController()
        self.app.include_router(self.controller.router)
        self.client = TestClient(self.app)

    def test_path_parameter_works(self):
        """Verify that the path parameter /{item_id} is passed correctly."""
        item_id = "abc-789"
        item_id = "abc-789"
        response = self.client.get(f"/items/{item_id}")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["item_id"], item_id)

    def test_query_parameter_works(self):
        """Verify that query parameters ?category=xxx&limit=yyy are parsed correctly."""
        response = self.client.get("/search?category=electronics&limit=50")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["category"], "electronics")
        self.assertEqual(data["limit"], 50)

    def test_complex_mixed_params(self):
        """
        Verify the mixed scenario of path + body + query + injected params.

        URL: /update/item_456?priority=9
        Body: {"name": "new_phone"}
        Injected: user_sub (from decorator)
        """
        item_id = "item_456"
        payload = {"name": "new_phone", "description": "some desc"}
        priority = 9

        response = self.client.put(
            f"/update/{item_id}?priority={priority}",
            json=payload,
            headers={"x-test-role": "admin"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()

        # Verify path parameter
        self.assertEqual(data["item_id"], item_id)
        # Verify injected parameter
        self.assertEqual(data["updated_by"], "user_12345")
        # Verify body parameter
        self.assertEqual(data["new_name"], "new_phone")
        # Verify query parameter
        self.assertEqual(data["priority"], priority)

    def test_invalid_query_param_type_still_triggers_fastapi_error(self):
        """
        Verify that the decorator does not break FastAPI's native validation.

        If `limit` is passed as a string instead of an integer,
        FastAPI should still return a 422 error.
        """
        response = self.client.get("/search?category=books&limit=not_an_int")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_openapi_schema_completeness(self):
        """
        Verify that the OpenAPI schema preserves path and query parameters,
        while excluding injected parameters.。
        """
        schema = self.app.openapi()
        params = schema["paths"]["/update/{item_id}"]["put"]["parameters"]

        param_names = [p["name"] for p in params]

        self.assertIn(
            "item_id",
            param_names,
            "Path parameter 'item_id' should be present in schema",
        )
        self.assertIn(
            "priority",
            param_names,
            "Query parameter 'priority' should be present in schema",
        )
        self.assertNotIn(
            "user_sub",
            param_names,
            "Injected parameter 'user_sub' should NOT appear in schema",
        )


if __name__ == "__main__":
    unittest.main()
