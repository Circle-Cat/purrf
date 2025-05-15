from unittest import TestCase, main
from http import HTTPStatus
from src.common.api_response_wrapper import api_response
from flask import Flask


class TestApiResponseWrapper(TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True
        self.client = self.app.test_client()

        @self.app.route("/test_success")
        def route_success():
            return api_response(True, "OK", {"a": 1}, HTTPStatus.OK)

        @self.app.route("/test_empty")
        def route_empty():
            return api_response(True, "Empty")

        @self.app.route("/test_error")
        def route_error():
            return api_response(False, "Fail", status_code=HTTPStatus.BAD_REQUEST)

    def test_success_with_data(self):
        res = self.client.get("/test_success")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.get_json()
        self.assertEqual(payload["data"], {"a": 1})
        self.assertEqual(payload["message"], "OK")

    def test_success_with_empty_data(self):
        res = self.client.get("/test_empty")
        self.assertEqual(res.status_code, HTTPStatus.OK)
        payload = res.get_json()
        self.assertEqual(payload["data"], {})
        self.assertEqual(payload["message"], "Empty")

    def test_error_response(self):
        res = self.client.get("/test_error")
        self.assertEqual(res.status_code, HTTPStatus.BAD_REQUEST)
        payload = res.get_json()
        self.assertEqual(payload["data"], {})
        self.assertEqual(payload["message"], "Fail")


if __name__ == "__main__":
    main()
