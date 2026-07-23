import base64
import email
import os
from unittest import TestCase, main
from unittest.mock import Mock, patch

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from backend.common.exceptions import RateLimitedError
from backend.common.gmail_client import GmailClient

TEST_CLIENT_ID = "test-client-id"
TEST_CLIENT_SECRET = "test-client-secret"
TEST_REFRESH_TOKEN = "test-refresh-token"
TEST_SENDER = "recruiting@circlecat.org"

_ENV = {
    "GMAIL_CLIENT_ID": TEST_CLIENT_ID,
    "GMAIL_CLIENT_SECRET": TEST_CLIENT_SECRET,
    "GMAIL_REFRESH_TOKEN": TEST_REFRESH_TOKEN,
    "GMAIL_SENDER_ADDRESS": TEST_SENDER,
}


def _http_error(status: int) -> HttpError:
    """Build a googleapiclient HttpError carrying the given HTTP status."""
    resp = Mock()
    resp.status = status
    return HttpError(resp=resp, content=b"{}")


def _b64(text: str) -> str:
    """URL-safe base64 encode a body part the way the Gmail API returns it."""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


class TestGmailClient(TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, _ENV, clear=False)
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.logger = Mock()

        # retry_utils.get_retry_on_transient(fn) simply runs fn (no retries).
        self.retry_utils = Mock()
        self.retry_utils.get_retry_on_transient.side_effect = lambda fn: fn()

        # Patch the Gmail service builder so no network / discovery happens.
        self.build_patcher = patch("backend.common.gmail_client.build")
        self.mock_build = self.build_patcher.start()
        self.addCleanup(self.build_patcher.stop)
        self.mock_service = Mock()
        self.mock_build.return_value = self.mock_service

        # Patch Credentials so we can assert how it is constructed.
        self.creds_patcher = patch("backend.common.gmail_client.Credentials")
        self.mock_credentials = self.creds_patcher.start()
        self.addCleanup(self.creds_patcher.stop)

        self.client = GmailClient(logger=self.logger, retry_utils=self.retry_utils)

    # ---- construction / env validation --------------------------------

    def test_missing_env_var_raises_value_error(self):
        with patch.dict(os.environ, {"GMAIL_REFRESH_TOKEN": ""}, clear=False):
            with self.assertRaises(ValueError):
                GmailClient(logger=self.logger, retry_utils=self.retry_utils)

    def test_constructor_makes_no_network_call(self):
        # Building the client alone must not build the Gmail service.
        self.mock_build.assert_not_called()

    # ---- send_message -------------------------------------------------

    def _sent_mime(self):
        """Decode the raw MIME message passed to messages().send()."""
        send = self.mock_service.users().messages().send
        raw = send.call_args.kwargs["body"]["raw"]
        return email.message_from_bytes(base64.urlsafe_b64decode(raw))

    def _stub_send_result(self, message_id="m1", thread_id="t1"):
        self.mock_service.users().messages().send().execute.return_value = {
            "id": message_id,
            "threadId": thread_id,
        }

    def test_send_message_builds_multipart_alternative(self):
        self._stub_send_result()
        self.client.send_message(
            to=["alice@example.com"], cc=[], subject="Hi", body="<p>Hello</p>"
        )
        mime = self._sent_mime()
        self.assertEqual(mime["From"], TEST_SENDER)
        self.assertEqual(mime["To"], "alice@example.com")
        self.assertEqual(mime["Subject"], "Hi")
        self.assertTrue(mime["Message-ID"])
        self.assertEqual(mime.get_content_type(), "multipart/alternative")
        parts = {
            p.get_content_type(): p.get_payload(decode=True).decode("utf-8")
            for p in mime.walk()
            if not p.is_multipart()
        }
        self.assertIn("<p>Hello</p>", parts["text/html"])
        self.assertIn("Hello", parts["text/plain"])
        self.assertNotIn("<p>", parts["text/plain"])

    def test_send_message_sets_cc(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"],
            cc=["b@example.com", "c@example.com"],
            subject="Hi",
            body="<p>x</p>",
        )
        mime = self._sent_mime()
        self.assertEqual(mime["Cc"], "b@example.com, c@example.com")

    def test_send_message_returns_ids(self):
        self._stub_send_result(message_id="MID", thread_id="TID")
        result = self.client.send_message(
            to=["a@example.com"], cc=[], subject="Hi", body="<p>x</p>"
        )
        self.assertEqual(result["gmail_message_id"], "MID")
        self.assertEqual(result["gmail_thread_id"], "TID")
        self.assertTrue(result["rfc822_message_id"])
        # The returned rfc822 id is the one we put on the wire.
        self.assertEqual(result["rfc822_message_id"], self._sent_mime()["Message-ID"])

    def test_new_message_omits_thread_id(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"], cc=[], subject="Hi", body="<p>x</p>"
        )
        body = self.mock_service.users().messages().send.call_args.kwargs["body"]
        self.assertNotIn("threadId", body)

    def test_reply_sets_thread_id_and_headers(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"],
            cc=[],
            subject="Re: Hi",
            body="<p>reply</p>",
            thread_id="THREAD",
            in_reply_to="<m0@mail>",
            references="<m0@mail>",
        )
        body = self.mock_service.users().messages().send.call_args.kwargs["body"]
        self.assertEqual(body["threadId"], "THREAD")
        mime = self._sent_mime()
        self.assertEqual(mime["In-Reply-To"], "<m0@mail>")
        self.assertEqual(mime["References"], "<m0@mail>")

    def test_send_message_rate_limited(self):
        self.mock_service.users().messages().send().execute.side_effect = _http_error(
            429
        )
        with self.assertRaises(RateLimitedError):
            self.client.send_message(
                to=["a@example.com"], cc=[], subject="Hi", body="<p>x</p>"
            )

    def test_send_message_server_error(self):
        self.mock_service.users().messages().send().execute.side_effect = _http_error(
            500
        )
        with self.assertRaises(RuntimeError):
            self.client.send_message(
                to=["a@example.com"], cc=[], subject="Hi", body="<p>x</p>"
            )

    def test_send_message_refresh_error_translated(self):
        # A revoked/expired refresh token surfaces as RefreshError from inside
        # execute(); the transport must translate it to a clean RuntimeError
        # rather than leaking the raw google-auth exception.
        self.mock_service.users().messages().send().execute.side_effect = RefreshError(
            "invalid_grant"
        )
        with self.assertRaises(RuntimeError):
            self.client.send_message(
                to=["a@example.com"], cc=[], subject="Hi", body="<p>x</p>"
            )

    def test_service_built_once_across_calls(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"], cc=[], subject="Hi", body="<p>x</p>"
        )
        self.client.send_message(
            to=["a@example.com"], cc=[], subject="Hi again", body="<p>y</p>"
        )
        self.assertEqual(self.mock_build.call_count, 1)

    def test_credentials_built_from_refresh_token(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"], cc=[], subject="Hi", body="<p>x</p>"
        )
        kwargs = self.mock_credentials.call_args.kwargs
        self.assertEqual(kwargs["refresh_token"], TEST_REFRESH_TOKEN)
        self.assertEqual(kwargs["client_id"], TEST_CLIENT_ID)
        self.assertEqual(kwargs["client_secret"], TEST_CLIENT_SECRET)
        # google-auth needs the token endpoint and scopes to refresh on its own.
        self.assertTrue(kwargs["token_uri"])
        self.assertTrue(kwargs["scopes"])

    # ---- get_thread ---------------------------------------------------

    def _stub_thread(self, messages):
        self.mock_service.users().threads().get().execute.return_value = {
            "id": "THREAD",
            "messages": messages,
        }

    def test_get_thread_parses_headers_and_bodies(self):
        self._stub_thread([
            {
                "id": "g1",
                "threadId": "THREAD",
                "snippet": "hello there",
                "internalDate": "1700000000000",
                "payload": {
                    "mimeType": "multipart/alternative",
                    "headers": [
                        {"name": "From", "value": TEST_SENDER},
                        {"name": "To", "value": "alice@example.com"},
                        {"name": "Subject", "value": "Hi"},
                        {"name": "Message-ID", "value": "<g1@mail>"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": _b64("Hello there")},
                        },
                        {
                            "mimeType": "text/html",
                            "body": {"data": _b64("<p>Hello there</p>")},
                        },
                    ],
                },
            },
            {
                "id": "g2",
                "threadId": "THREAD",
                "snippet": "a reply",
                "internalDate": "1700000100000",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": "alice@example.com"},
                        {"name": "To", "value": TEST_SENDER},
                        {"name": "Subject", "value": "Re: Hi"},
                        {"name": "Message-ID", "value": "<g2@mail>"},
                    ],
                    "body": {"data": _b64("a reply")},
                },
            },
        ])
        messages = self.client.get_thread("THREAD")
        self.assertEqual(len(messages), 2)

        first = messages[0]
        self.assertEqual(first["gmail_message_id"], "g1")
        self.assertEqual(first["rfc822_message_id"], "<g1@mail>")
        self.assertEqual(first["from_address"], TEST_SENDER)
        self.assertEqual(first["to_addresses"], "alice@example.com")
        self.assertEqual(first["subject"], "Hi")
        self.assertEqual(first["html"], "<p>Hello there</p>")
        self.assertEqual(first["plain"], "Hello there")
        self.assertEqual(first["snippet"], "hello there")
        self.assertEqual(first["gmail_internal_date"], "1700000000000")

        second = messages[1]
        self.assertEqual(second["from_address"], "alice@example.com")
        self.assertEqual(second["plain"], "a reply")
        self.assertIsNone(second["html"])

    def test_get_thread_passes_id_and_full_format(self):
        self._stub_thread([])
        self.client.get_thread("THREAD")
        kwargs = self.mock_service.users().threads().get.call_args.kwargs
        self.assertEqual(kwargs["id"], "THREAD")
        self.assertEqual(kwargs["format"], "full")

    def test_get_thread_rate_limited(self):
        self.mock_service.users().threads().get().execute.side_effect = _http_error(429)
        with self.assertRaises(RateLimitedError):
            self.client.get_thread("THREAD")


if __name__ == "__main__":
    main()
