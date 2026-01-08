from unittest import TestCase, main
from http import HTTPStatus
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from backend.common.fast_api_response_wrapper import api_response
from datetime import datetime
from uuid import UUID


def route_success(request):
    return api_response("OK", True, {"a": 1}, HTTPStatus.OK)


def route_string(request):
    return api_response(
        "String Test", True, {"message": "Hello, World!"}, HTTPStatus.OK
    )


def route_float(request):
    return api_response("Float Test", True, {"value": 3.14}, HTTPStatus.OK)


def route_boolean(request):
    return api_response("Boolean Test", True, {"is_active": True}, HTTPStatus.OK)


def route_empty(request):
    return api_response("Empty", True, None, HTTPStatus.OK)


def route_error(request):
    return api_response("Fail", False, status_code=HTTPStatus.BAD_REQUEST)


def route_with_datetime(request):
    return api_response(
        "Datetime Test", True, {"timestamp": datetime.now()}, HTTPStatus.OK
    )


def route_with_uuid(request):
    return api_response(
        "UUID Test",
        True,
        {"user_uuid": UUID("885b2abc-bf44-4d39-83b8-afcc0ea855b3")},
        HTTPStatus.OK,
    )


def route_none(request):
    return api_response("No Data", True, None, HTTPStatus.OK)


class TestApiResponseWrapper(TestCase):
    def setUp(self):
        # Create a minimal Starlette app to test JSONResponse
        self.app = Starlette(
            routes=[
                Route("/test_success", route_success),
                Route("/test_empty", route_empty),
                Route("/test_error", route_error),
                Route("/test_datetime", route_with_datetime),
                Route("/test_uuid", route_with_uuid),
                Route("/test_none", route_none),
                Route("/test_string", route_string),
                Route("/test_float", route_float),
                Route("/test_boolean", route_boolean),
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
        self.assertEqual(payload["data"], None)
        self.assertEqual(payload["message"], "Empty")

    def test_error_response(self):
        res = self.client.get("/test_error")
        self.assertEqual(res.status_code, HTTPStatus.BAD_REQUEST)
        payload = res.json()
        self.assertEqual(payload["data"], None)
        self.assertEqual(payload["message"], "Fail")

    def test_success_with_datetime(self):
        res = self.client.get("/test_datetime")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.json()

        self.assertTrue("timestamp" in payload["data"])
        self.assertTrue(isinstance(payload["data"]["timestamp"], str))
        self.assertTrue(payload["data"]["timestamp"].count("-") == 2)

    def test_success_with_uuid(self):
        res = self.client.get("/test_uuid")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.json()

        self.assertTrue("user_uuid" in payload["data"])
        self.assertTrue(isinstance(payload["data"]["user_uuid"], str))
        self.assertEqual(
            payload["data"]["user_uuid"], "885b2abc-bf44-4d39-83b8-afcc0ea855b3"
        )

    def test_success_with_none_data(self):
        res = self.client.get("/test_none")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.json()

        self.assertEqual(payload["data"], None)
        self.assertEqual(payload["message"], "No Data")

    def test_success_with_string_data(self):
        res = self.client.get("/test_string")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.json()
        self.assertEqual(payload["data"], {"message": "Hello, World!"})
        self.assertEqual(payload["message"], "String Test")

    def test_success_with_float_data(self):
        res = self.client.get("/test_float")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.json()
        self.assertEqual(payload["data"], {"value": 3.14})
        self.assertEqual(payload["message"], "Float Test")

    def test_success_with_boolean_data(self):
        res = self.client.get("/test_boolean")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.json()
        self.assertEqual(payload["data"], {"is_active": True})
        self.assertEqual(payload["message"], "Boolean Test")


if __name__ == "__main__":
    main()
