from http import HTTPStatus
from unittest import TestCase, main
from unittest.mock import patch
from flask import Flask
from src.frontend_service.frontend_api import frontend_bp
from src.common.constants import MicrosoftAccountStatus

MICROSOFT_LDAP_FETCHER_API = "/api/microsoft/{status}/ldaps"


class TestAppRoutes(TestCase):
    @classmethod
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(frontend_bp)
        self.client = app.test_client()
        app.testing = True

    @patch("src.frontend_service.frontend_api.get_all_ldaps_and_displaynames")
    def test_get_microsoft_ldaps_success(self, mock_get_all_ldaps):
        mock_result = {"user1": "ldap1", "user2": "ldap2"}
        mock_get_all_ldaps.return_value = mock_result
        response = self.client.get(
            MICROSOFT_LDAP_FETCHER_API.format(
                status=MicrosoftAccountStatus.ACTIVE.value
            )
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json["data"], mock_result)
        mock_get_all_ldaps.assert_called_once_with(MicrosoftAccountStatus.ACTIVE)

    def test_get_microsoft_ldaps_invalid_status_raises(self):
        with self.assertRaises(ValueError) as context:
            self.client.get(MICROSOFT_LDAP_FETCHER_API.format(status="invalid_status"))


if __name__ == "__main__":
    main()
