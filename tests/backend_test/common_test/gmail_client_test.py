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
OTHER_SENDER = "notification@circlecat.org"

_ENV = {
    "GMAIL_CLIENT_ID": TEST_CLIENT_ID,
    "GMAIL_CLIENT_SECRET": TEST_CLIENT_SECRET,
    "GMAIL_REFRESH_TOKEN": TEST_REFRESH_TOKEN,
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

        self.client = GmailClient(
            logger=self.logger,
            retry_utils=self.retry_utils,
            sender_addresses=[TEST_SENDER],
        )

    # ---- construction / env validation --------------------------------

    def test_missing_env_var_raises_value_error(self):
        with patch.dict(os.environ, {"GMAIL_REFRESH_TOKEN": ""}, clear=False):
            with self.assertRaises(ValueError):
                GmailClient(
                    logger=self.logger,
                    retry_utils=self.retry_utils,
                    sender_addresses=[TEST_SENDER],
                )

    def test_no_sender_address_raises_value_error(self):
        # A mailbox with no configured From is unusable: every send would have
        # to invent one.
        for empty in ([], None, [""]):
            with self.subTest(sender_addresses=empty):
                with self.assertRaises(ValueError):
                    GmailClient(
                        logger=self.logger,
                        retry_utils=self.retry_utils,
                        sender_addresses=empty,
                    )

    def test_constructor_makes_no_network_call(self):
        # Building the client alone must not build the Gmail service.
        self.mock_build.assert_not_called()

    # ---- send_message -------------------------------------------------

    def _sent_mime(self):
        """Decode the raw MIME message passed to messages().send()."""
        send = self.mock_service.users().messages().send
        raw = send.call_args.kwargs["body"]["raw"]
        return email.message_from_bytes(base64.urlsafe_b64decode(raw))

    def _plain_part(self):
        """Decode the text/plain alternative of the sent message."""
        for part in self._sent_mime().walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode("utf-8")
        self.fail("message has no text/plain alternative")

    def _stub_send_result(self, message_id="m1", thread_id="t1"):
        self.mock_service.users().messages().send().execute.return_value = {
            "id": message_id,
            "threadId": thread_id,
        }

    def test_send_message_builds_multipart_alternative(self):
        self._stub_send_result()
        self.client.send_message(
            to=["alice@example.com"],
            cc=[],
            subject="Hi",
            body="<p>Hello</p>",
            sender=TEST_SENDER,
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

    def _send_body(self, body):
        self._stub_send_result()
        self.client.send_message(
            to=["alice@example.com"], cc=[], subject="Hi", body=body, sender=TEST_SENDER
        )

    def test_plain_part_keeps_the_url_of_a_link(self):
        url = "https://docs.google.com/forms/d/e/1FAIpQLS/viewform"
        self._send_body(f'<p>Please fill out <a href="{url}">this form</a>.</p>')
        self.assertEqual(
            self._plain_part().strip(), f"Please fill out this form ({url})."
        )

    def test_plain_part_strips_markup_inside_the_link_label(self):
        self._send_body(
            '<a href="https://x.test" target="_blank">click <b>here</b></a>'
        )
        self.assertEqual(self._plain_part().strip(), "click here (https://x.test)")

    def test_plain_part_does_not_repeat_a_url_that_is_its_own_label(self):
        self._send_body('<a href="https://x.test/a">https://x.test/a</a>')
        self.assertEqual(self._plain_part().strip(), "https://x.test/a")

    def test_plain_part_hides_the_mailto_scheme_when_the_label_is_the_address(self):
        self._send_body('<a href="mailto:hr@circlecat.org">hr@circlecat.org</a>')
        self.assertEqual(self._plain_part().strip(), "hr@circlecat.org")

    def test_plain_part_leaves_an_anchor_without_href_alone(self):
        self._send_body('<a name="top">Back to top</a>')
        self.assertEqual(self._plain_part().strip(), "Back to top")

    def test_send_message_without_a_sender_is_a_type_error(self):
        # ``sender`` has no default on purpose. Gmail does not reject an
        # unowned From, it silently rewrites it to the mailbox owner, so a
        # caller that forgets to say who it is must fail here instead.
        self._stub_send_result()
        with self.assertRaises(TypeError):
            self.client.send_message(
                to=["a@example.com"], cc=[], subject="Hi", body="<p>x</p>"
            )

    def test_send_message_uses_the_given_sender_as_from(self):
        client = GmailClient(
            logger=self.logger,
            retry_utils=self.retry_utils,
            sender_addresses=[TEST_SENDER, OTHER_SENDER],
        )
        self._stub_send_result()
        client.send_message(
            to=["a@example.com"],
            cc=[],
            subject="Hi",
            body="<p>x</p>",
            sender=OTHER_SENDER,
        )
        self.assertEqual(self._sent_mime()["From"], OTHER_SENDER)

    def test_send_message_keeps_a_display_name_in_from(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"],
            cc=[],
            subject="Hi",
            body="<p>x</p>",
            sender=f"Circle Cat Recruiting <{TEST_SENDER}>",
        )
        mime = self._sent_mime()
        self.assertEqual(mime["From"], f"Circle Cat Recruiting <{TEST_SENDER}>")
        # The Message-ID domain comes from the address, not the display name.
        self.assertTrue(mime["Message-ID"].endswith("@circlecat.org>"))

    def test_send_message_rejects_a_sender_the_mailbox_does_not_own(self):
        with self.assertRaises(ValueError):
            self.client.send_message(
                to=["a@example.com"],
                cc=[],
                subject="Hi",
                body="<p>x</p>",
                sender="someone-else@example.com",
            )
        # Rejected before any Gmail service is built, so nothing went out.
        self.mock_build.assert_not_called()

    def test_owns_address_ignores_case_and_reads_a_display_name_header(self):
        self.assertTrue(self.client.owns_address(TEST_SENDER))
        self.assertTrue(self.client.owns_address(TEST_SENDER.upper()))
        self.assertTrue(
            self.client.owns_address(f"Circle Cat Recruiting <{TEST_SENDER}>")
        )

    def test_owns_address_rejects_other_addresses_and_blanks(self):
        for value in ("cand@example.com", "recruiting@example.com", "", None):
            with self.subTest(value=value):
                self.assertFalse(self.client.owns_address(value))

    def test_send_message_sets_cc(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"],
            cc=["b@example.com", "c@example.com"],
            subject="Hi",
            body="<p>x</p>",
            sender=TEST_SENDER,
        )
        mime = self._sent_mime()
        self.assertEqual(mime["Cc"], "b@example.com, c@example.com")

    def test_send_message_returns_ids(self):
        self._stub_send_result(message_id="MID", thread_id="TID")
        result = self.client.send_message(
            to=["a@example.com"],
            cc=[],
            subject="Hi",
            body="<p>x</p>",
            sender=TEST_SENDER,
        )
        self.assertEqual(result["gmail_message_id"], "MID")
        self.assertEqual(result["gmail_thread_id"], "TID")
        self.assertTrue(result["rfc822_message_id"])
        # Minted under the sender's domain, not the mailbox owner's.
        self.assertTrue(result["rfc822_message_id"].endswith("@circlecat.org>"))
        # The returned rfc822 id is the one we put on the wire.
        self.assertEqual(result["rfc822_message_id"], self._sent_mime()["Message-ID"])

    def test_new_message_omits_thread_id(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"],
            cc=[],
            subject="Hi",
            body="<p>x</p>",
            sender=TEST_SENDER,
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
            sender=TEST_SENDER,
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
                to=["a@example.com"],
                cc=[],
                subject="Hi",
                body="<p>x</p>",
                sender=TEST_SENDER,
            )

    def test_send_message_server_error(self):
        self.mock_service.users().messages().send().execute.side_effect = _http_error(
            500
        )
        with self.assertRaises(RuntimeError):
            self.client.send_message(
                to=["a@example.com"],
                cc=[],
                subject="Hi",
                body="<p>x</p>",
                sender=TEST_SENDER,
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
                to=["a@example.com"],
                cc=[],
                subject="Hi",
                body="<p>x</p>",
                sender=TEST_SENDER,
            )

    def test_bad_client_credentials_are_not_reported_as_a_bad_token(self):
        # Both causes arrive as RefreshError. Reporting them the same way sent a
        # real incident looking for a revoked token when the client secret was
        # the problem, so the message must name the failing half.
        self.mock_service.users().messages().send().execute.side_effect = RefreshError(
            "invalid_client: The provided client secret is invalid.",
            {"error": "invalid_client"},
        )
        with self.assertRaises(RuntimeError) as caught:
            self.client.send_message(
                to=["a@example.com"],
                cc=[],
                subject="Hi",
                body="<p>x</p>",
                sender=TEST_SENDER,
            )
        message = str(caught.exception)
        self.assertIn("invalid_client", message)
        self.assertIn("client id/secret", message)
        self.assertNotIn("revoked", message)

    def test_revoked_token_says_so(self):
        self.mock_service.users().messages().send().execute.side_effect = RefreshError(
            "invalid_grant: Token has been expired or revoked.",
            {"error": "invalid_grant"},
        )
        with self.assertRaises(RuntimeError) as caught:
            self.client.send_message(
                to=["a@example.com"],
                cc=[],
                subject="Hi",
                body="<p>x</p>",
                sender=TEST_SENDER,
            )
        self.assertIn("invalid_grant", str(caught.exception))
        self.assertIn("re-authorize", str(caught.exception))

    def test_service_built_once_across_calls(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"],
            cc=[],
            subject="Hi",
            body="<p>x</p>",
            sender=TEST_SENDER,
        )
        self.client.send_message(
            to=["a@example.com"],
            cc=[],
            subject="Hi again",
            body="<p>y</p>",
            sender=TEST_SENDER,
        )
        self.assertEqual(self.mock_build.call_count, 1)

    def test_credentials_built_from_refresh_token(self):
        self._stub_send_result()
        self.client.send_message(
            to=["a@example.com"],
            cc=[],
            subject="Hi",
            body="<p>x</p>",
            sender=TEST_SENDER,
        )
        kwargs = self.mock_credentials.call_args.kwargs
        self.assertEqual(kwargs["refresh_token"], TEST_REFRESH_TOKEN)
        self.assertEqual(kwargs["client_id"], TEST_CLIENT_ID)
        self.assertEqual(kwargs["client_secret"], TEST_CLIENT_SECRET)
        # google-auth needs the token endpoint to refresh on its own.
        self.assertTrue(kwargs["token_uri"])
        # Scopes must NOT be sent on a refresh-token grant: Google rejects any
        # scope that is not a subset of what the token was granted.
        self.assertNotIn("scopes", kwargs)

    # ---- list_thread_message_ids --------------------------------------

    def _stub_thread_ids(self, messages):
        """Stub threads().get() for the metadata-only id listing."""
        self.mock_service.users().threads().get().execute.return_value = {
            "id": "THREAD",
            "messages": messages,
        }

    def test_list_thread_message_ids_returns_ids_in_gmail_order(self):
        self._stub_thread_ids([{"id": "g1"}, {"id": "g2"}, {"id": "g3"}])
        self.assertEqual(
            self.client.list_thread_message_ids("THREAD"), ["g1", "g2", "g3"]
        )

    def test_list_thread_message_ids_requests_metadata_only(self):
        # The whole point of the split: never pull bodies just to learn ids.
        self._stub_thread_ids([])
        self.client.list_thread_message_ids("THREAD")
        kwargs = self.mock_service.users().threads().get.call_args.kwargs
        self.assertEqual(kwargs["id"], "THREAD")
        self.assertEqual(kwargs["format"], "metadata")
        self.assertEqual(kwargs["fields"], "messages(id)")

    def test_list_thread_message_ids_empty_thread(self):
        self.mock_service.users().threads().get().execute.return_value = {"id": "T"}
        self.assertEqual(self.client.list_thread_message_ids("THREAD"), [])

    def test_list_thread_message_ids_rate_limited(self):
        self.mock_service.users().threads().get().execute.side_effect = _http_error(429)
        with self.assertRaises(RateLimitedError):
            self.client.list_thread_message_ids("THREAD")

    # ---- get_message ---------------------------------------------------

    def _stub_message(self, message):
        self.mock_service.users().messages().get().execute.return_value = message

    def test_get_message_parses_headers_and_bodies(self):
        self._stub_message({
            "id": "g1",
            "threadId": "THREAD",
            "snippet": "hello there",
            "internalDate": "1700000000000",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": TEST_SENDER},
                    {"name": "To", "value": "alice@example.com"},
                    {"name": "Cc", "value": "bob@example.com"},
                    {"name": "Subject", "value": "Hi"},
                    {"name": "Message-ID", "value": "<g1@mail>"},
                ],
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64("Hello there")}},
                    {
                        "mimeType": "text/html",
                        "body": {"data": _b64("<p>Hello there</p>")},
                    },
                ],
            },
        })
        message = self.client.get_message("g1")
        self.assertEqual(message["gmail_message_id"], "g1")
        self.assertEqual(message["gmail_thread_id"], "THREAD")
        self.assertEqual(message["rfc822_message_id"], "<g1@mail>")
        self.assertEqual(message["from_address"], TEST_SENDER)
        self.assertEqual(message["to_addresses"], "alice@example.com")
        self.assertEqual(message["cc_addresses"], "bob@example.com")
        self.assertEqual(message["subject"], "Hi")
        self.assertEqual(message["html"], "<p>Hello there</p>")
        self.assertEqual(message["plain"], "Hello there")
        self.assertEqual(message["snippet"], "hello there")
        self.assertEqual(message["gmail_internal_date"], "1700000000000")

    def test_get_message_handles_single_part_plain_body(self):
        self._stub_message({
            "id": "g2",
            "threadId": "THREAD",
            "snippet": "a reply",
            "internalDate": "1700000100000",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "Subject", "value": "Re: Hi"},
                ],
                "body": {"data": _b64("a reply")},
            },
        })
        message = self.client.get_message("g2")
        self.assertEqual(message["from_address"], "alice@example.com")
        self.assertEqual(message["plain"], "a reply")
        self.assertIsNone(message["html"])

    def test_get_message_requests_full_format(self):
        self._stub_message({"id": "g1", "payload": {}})
        self.client.get_message("g1")
        kwargs = self.mock_service.users().messages().get.call_args.kwargs
        self.assertEqual(kwargs["id"], "g1")
        self.assertEqual(kwargs["format"], "full")

    def test_get_message_rate_limited(self):
        self.mock_service.users().messages().get().execute.side_effect = _http_error(
            429
        )
        with self.assertRaises(RateLimitedError):
            self.client.get_message("g1")

    def test_get_message_not_found_raises_runtime_error(self):
        # A message deleted between listing ids and fetching it -> 404. The
        # transport must surface it as a clean RuntimeError; the service layer
        # deliberately lets it propagate (see Task 3).
        self.mock_service.users().messages().get().execute.side_effect = _http_error(
            404
        )
        with self.assertRaises(RuntimeError):
            self.client.get_message("gone")

    # ---- list_recent_message_thread_ids --------------------------------

    def _stub_message_pages(self, *pages):
        """Stub messages().list() with one response per page.

        Uses ``list.return_value`` rather than ``list()`` so the stub does not
        record a call — the pagination tests below assert on
        ``list.call_args_list`` and must see only the production calls.
        """
        self.mock_service.users().messages().list.return_value.execute.side_effect = (
            list(pages)
        )

    def test_list_recent_thread_ids_returns_deduped_set(self):
        # Two messages in the same thread must yield one thread id: the caller
        # syncs per thread, not per message.
        self._stub_message_pages({
            "messages": [
                {"threadId": "T1"},
                {"threadId": "T2"},
                {"threadId": "T1"},
            ]
        })
        self.assertEqual(self.client.list_recent_message_thread_ids(2), {"T1", "T2"})

    def test_list_recent_thread_ids_builds_query_and_field_mask(self):
        self._stub_message_pages({"messages": []})
        self.client.list_recent_message_thread_ids(2)
        kwargs = self.mock_service.users().messages().list.call_args.kwargs
        self.assertEqual(kwargs["q"], "newer_than:2d")
        # We only need threadId; id and resultSizeEstimate are dead weight.
        self.assertEqual(kwargs["fields"], "messages/threadId,nextPageToken")

    def test_list_recent_thread_ids_honours_lookback_days(self):
        self._stub_message_pages({"messages": []})
        self.client.list_recent_message_thread_ids(7)
        kwargs = self.mock_service.users().messages().list.call_args.kwargs
        self.assertEqual(kwargs["q"], "newer_than:7d")

    def test_list_recent_thread_ids_follows_pagination(self):
        self._stub_message_pages(
            {"messages": [{"threadId": "T1"}], "nextPageToken": "page2"},
            {"messages": [{"threadId": "T2"}]},
        )

        result = self.client.list_recent_message_thread_ids(2)

        self.assertEqual(result, {"T1", "T2"})
        calls = self.mock_service.users().messages().list.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertIsNone(calls[0].kwargs["pageToken"])
        self.assertEqual(calls[1].kwargs["pageToken"], "page2")

    def test_list_recent_thread_ids_empty_mailbox_window(self):
        # Gmail omits "messages" entirely when nothing matches.
        self._stub_message_pages({})
        self.assertEqual(self.client.list_recent_message_thread_ids(2), set())

    def test_list_recent_thread_ids_rate_limited(self):
        self.mock_service.users().messages().list.return_value.execute.side_effect = (
            _http_error(429)
        )
        with self.assertRaises(RateLimitedError):
            self.client.list_recent_message_thread_ids(2)


if __name__ == "__main__":
    main()
