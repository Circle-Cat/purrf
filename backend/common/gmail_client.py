"""
Gmail transport for the member-email feature.

``GmailClient`` wraps the two Gmail API calls the email feature needs, using a
company-wide account authorized once via an OAuth2 refresh token (there is no
in-app OAuth flow):

- ``send_message`` — send a new mail or a reply. The body is HTML; the message
  goes out as ``multipart/alternative`` (HTML plus an auto-derived plain-text
  fallback). Replies carry ``threadId`` plus ``In-Reply-To`` / ``References`` so
  Gmail nests them in the original conversation.
- ``get_thread``   — pull back every message in a thread, parsed into plain
  dicts (headers, HTML/plain bodies, snippet, timestamps).

This class is deliberately **domain-agnostic**: it knows nothing about our DB,
permissions, templates, contexts, or the OUTBOUND/INBOUND enum. ``get_thread``
returns each message's raw ``from_address``; deciding direction (by comparing it
to the sender) belongs to the domain layer, not here.

An ``access_token`` is obtained and refreshed automatically by ``google-auth``
from the stored refresh token; the built Gmail service is cached on the
instance and reused across calls. Gmail API failures are translated into the
shared domain exceptions (429 -> ``RateLimitedError``; anything else ->
``RuntimeError``) so a failed send never looks like a success to the caller.
"""

import base64
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from html import unescape
from http import HTTPStatus

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.common.environment_constants import (
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_REFRESH_TOKEN,
    GMAIL_SENDER_ADDRESS,
)
from backend.common.exceptions import RateLimitedError

# OAuth2 token endpoint the refresh token is redeemed against.
_TOKEN_URI = "https://oauth2.googleapis.com/token"
# gmail.modify covers both send and read (threads.get).
_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
# "me" resolves to the authenticated account (our sender).
_GMAIL_USER = "me"


class GmailClient:
    """Domain-agnostic Gmail send/read transport (see module docstring)."""

    def __init__(self, logger, retry_utils):
        """
        Read the Gmail credentials from the environment.

        No network call is made here; the Gmail service is built lazily on first
        use and cached.

        Args:
            logger: Application logger.
            retry_utils: Provides ``get_retry_on_transient(fn)`` to wrap calls.

        Raises:
            ValueError: If any required environment variable is missing, or if
                ``logger`` / ``retry_utils`` is not provided.
        """
        self._client_id = os.getenv(GMAIL_CLIENT_ID)
        self._client_secret = os.getenv(GMAIL_CLIENT_SECRET)
        self._refresh_token = os.getenv(GMAIL_REFRESH_TOKEN)
        self._sender = os.getenv(GMAIL_SENDER_ADDRESS)
        self._logger = logger
        self._retry_utils = retry_utils
        self._service = None

        if not self._client_id:
            raise ValueError("Missing environment variable: GMAIL_CLIENT_ID")
        if not self._client_secret:
            raise ValueError("Missing environment variable: GMAIL_CLIENT_SECRET")
        if not self._refresh_token:
            raise ValueError("Missing environment variable: GMAIL_REFRESH_TOKEN")
        if not self._sender:
            raise ValueError("Missing environment variable: GMAIL_SENDER_ADDRESS")
        if not self._logger:
            raise ValueError("logger must be provided")
        if not self._retry_utils:
            raise ValueError("retry_utils must be provided")

    def send_message(
        self,
        to,
        cc,
        subject,
        body,
        thread_id=None,
        in_reply_to=None,
        references=None,
    ):
        """
        Send an HTML email as the company account, optionally as a thread reply.

        The message is sent as ``multipart/alternative`` — the HTML ``body`` plus
        a plain-text fallback derived from it. A fresh ``Message-ID`` is minted
        and set on the outgoing mail so the caller can persist it without a
        follow-up read.

        Args:
            to (list[str]): Recipient addresses.
            cc (list[str]): Cc addresses (may be empty).
            subject (str): Subject line.
            body (str): HTML body.
            thread_id (str | None): Gmail thread id to reply into (``None`` for a
                new thread).
            in_reply_to (str | None): ``Message-ID`` of the message being replied
                to (reply only).
            references (str | None): ``References`` header value (reply only).

        Returns:
            dict: ``{"gmail_message_id", "gmail_thread_id", "rfc822_message_id"}``.

        Raises:
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        rfc822_message_id = make_msgid(domain=self._sender.split("@")[-1])
        mime = self._build_mime(
            to, cc, subject, body, rfc822_message_id, in_reply_to, references
        )
        request_body = {
            "raw": base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
        }
        if thread_id:
            request_body["threadId"] = thread_id

        request = (
            self._get_service()
            .users()
            .messages()
            .send(userId=_GMAIL_USER, body=request_body)
        )
        result = self._execute(request, "send_message")
        return {
            "gmail_message_id": result["id"],
            "gmail_thread_id": result["threadId"],
            "rfc822_message_id": rfc822_message_id,
        }

    def get_thread(self, thread_id):
        """
        Fetch and parse every message in a Gmail thread.

        Args:
            thread_id (str): Gmail thread id.

        Returns:
            list[dict]: One dict per message, in the order Gmail returns them,
            each with keys: ``gmail_message_id``, ``gmail_thread_id``,
            ``rfc822_message_id``, ``from_address``, ``to_addresses``,
            ``cc_addresses``, ``subject``, ``html``, ``plain``, ``snippet``,
            ``gmail_internal_date``.

        Raises:
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        request = (
            self._get_service()
            .users()
            .threads()
            .get(userId=_GMAIL_USER, id=thread_id, format="full")
        )
        thread = self._execute(request, "get_thread")
        return [self._parse_message(message) for message in thread.get("messages", [])]

    def _get_service(self):
        """Build the Gmail service once (lazily) and cache it on the instance."""
        if self._service is None:
            credentials = Credentials(
                token=None,
                refresh_token=self._refresh_token,
                client_id=self._client_id,
                client_secret=self._client_secret,
                token_uri=_TOKEN_URI,
                scopes=_SCOPES,
            )
            self._service = build(
                "gmail", "v1", credentials=credentials, cache_discovery=False
            )
        return self._service

    def _execute(self, request, operation):
        """Run a Gmail request with retry, translating errors to domain types."""
        try:
            return self._retry_utils.get_retry_on_transient(request.execute)
        except RefreshError as error:
            # google-auth could not exchange the refresh token for an access
            # token — almost always because the token was revoked or expired
            # (e.g. the sender account's password changed, or the OAuth app
            # slipped out of Internal/published status). Re-authorize the
            # account per the runbook (RFC appendix A) and update the secret.
            self._logger.error(
                "[GmailClient] %s failed: refresh token rejected — "
                "re-authorization of the sender account is required.",
                operation,
            )
            raise RuntimeError(
                f"Gmail authentication failed during {operation}: "
                "refresh token rejected (re-authorization required)"
            ) from error
        except HttpError as error:
            status = getattr(error.resp, "status", None)
            self._logger.error("[GmailClient] %s failed (status=%s)", operation, status)
            if status == HTTPStatus.TOO_MANY_REQUESTS:
                raise RateLimitedError(
                    f"Gmail rate limited during {operation}"
                ) from error
            raise RuntimeError(f"Gmail API error during {operation}") from error

    def _build_mime(
        self, to, cc, subject, body, rfc822_message_id, in_reply_to, references
    ):
        """Assemble a multipart/alternative message (plain fallback + HTML)."""
        message = MIMEMultipart("alternative")
        message["From"] = self._sender
        message["To"] = ", ".join(to)
        if cc:
            message["Cc"] = ", ".join(cc)
        message["Subject"] = subject
        message["Message-ID"] = rfc822_message_id
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references
        # Least-preferred alternative first, most-preferred (HTML) last.
        message.attach(MIMEText(self._html_to_text(body), "plain", "utf-8"))
        message.attach(MIMEText(body, "html", "utf-8"))
        return message

    @staticmethod
    def _html_to_text(html):
        """Derive a readable plain-text fallback from an HTML body."""
        text = re.sub(r"(?i)<br\s*/?>", "\n", html)
        text = re.sub(r"(?i)</p\s*>", "\n\n", text)
        text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
        text = re.sub(r"(?i)</(h[1-6]|div|ul|ol)\s*>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        # Collapse runs of blank lines and trailing spaces.
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _parse_message(self, message):
        """Flatten a Gmail message resource into a transport-level dict."""
        payload = message.get("payload", {})
        headers = {
            header["name"].lower(): header["value"]
            for header in payload.get("headers", [])
        }
        html_body, plain_body = self._extract_bodies(payload)
        return {
            "gmail_message_id": message.get("id"),
            "gmail_thread_id": message.get("threadId"),
            "rfc822_message_id": headers.get("message-id"),
            "from_address": headers.get("from"),
            "to_addresses": headers.get("to"),
            "cc_addresses": headers.get("cc"),
            "subject": headers.get("subject"),
            "html": html_body,
            "plain": plain_body,
            "snippet": message.get("snippet"),
            "gmail_internal_date": message.get("internalDate"),
        }

    def _extract_bodies(self, payload):
        """Walk a message payload, returning (html, plain) — either may be None."""
        html_body = None
        plain_body = None
        stack = [payload]
        while stack:
            part = stack.pop()
            mime_type = part.get("mimeType", "")
            data = part.get("body", {}).get("data")
            if data and mime_type == "text/html" and html_body is None:
                html_body = self._decode(data)
            elif data and mime_type == "text/plain" and plain_body is None:
                plain_body = self._decode(data)
            stack.extend(part.get("parts", []) or [])
        return html_body, plain_body

    @staticmethod
    def _decode(data):
        """Decode a base64url Gmail body part to text."""
        return base64.urlsafe_b64decode(data.encode("ascii")).decode(
            "utf-8", errors="replace"
        )
