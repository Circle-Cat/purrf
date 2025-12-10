from unittest import TestCase, main
from http import HTTPStatus
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from backend.common.fast_api_response_wrapper import api_response


def route_success(request):
    return api_response("OK", True, {"a": 1}, HTTPStatus.OK)


def route_empty(request):
    return api_response("Empty", True)


def route_error(request):
    return api_response("Fail", False, status_code=HTTPStatus.BAD_REQUEST)


class TestApiResponseWrapper(TestCase):
    def setUp(self):
        # Create a minimal Starlette app to test JSONResponse
        self.app = Starlette(
            routes=[
                Route("/test_success", route_success),
                Route("/test_empty", route_empty),
                Route("/test_error", route_error),
            ]
        )
        self.client = TestClient(self.app)

    def test_success_with_data(self):
        res = self.client.get("/test_success")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.json()
        self.assertEqual(payload["data"], {"a": 1})
        self.assertEqual(payload["message"], "OK")

    def test_success_with_empty_data(self):
        res = self.client.get("/test_empty")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.json()
        self.assertEqual(payload["data"], {})
        self.assertEqual(payload["message"], "Empty")

    def test_error_response(self):
        res = self.client.get("/test_error")
        self.assertEqual(res.status_code, HTTPStatus.BAD_REQUEST)
        payload = res.json()
        self.assertEqual(payload["data"], {})
        self.assertEqual(payload["message"], "Fail")


if __name__ == "__main__":
    main()
