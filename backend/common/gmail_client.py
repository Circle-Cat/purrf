"""
Gmail transport for the member-email feature.

``GmailClient`` wraps the Gmail API calls the email feature needs, using a
company-wide account authorized once via an OAuth2 refresh token (there is no
in-app OAuth flow):

- ``send_message`` — send a new mail or a reply. The body is HTML; the message
  goes out as ``multipart/alternative`` (HTML plus an auto-derived plain-text
  fallback, in which links become ``label (url)`` so their target survives).
  Replies carry ``threadId`` plus ``In-Reply-To`` / ``References`` so Gmail
  nests them in the original conversation.
- ``list_thread_message_ids`` — list a thread's message ids (metadata only, no
  bodies), so a caller can tell what is new without paying for what it already
  has.
- ``list_recent_message_thread_ids`` — ask the whole mailbox which threads
  received mail in a recent window, so a caller can skip the conversations
  that cannot have changed.
- ``get_message`` — pull back and parse one message (headers, HTML/plain
  bodies, snippet, timestamps).

One mailbox, one credential, but possibly several ``From`` addresses: Gmail
Send-As lets the account send as any address verified on it, so
``sender_addresses`` lists the ones this deployment may use, every
``send_message`` names which one it is sending as, and ``owns_address`` answers
"is this ``From`` one of ours?". An address outside the list is refused here,
because Gmail does not reject an unowned ``From`` — it silently rewrites it to
the mailbox owner, which would look like a clean send.

This class is deliberately **domain-agnostic**: it knows nothing about our DB,
permissions, templates, contexts, or the OUTBOUND/INBOUND enum. ``get_message``
returns each message's raw ``from_address``; turning that into a direction
belongs to the domain layer, which asks ``owns_address`` and maps the answer.

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
from email.utils import make_msgid, parseaddr
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
)
from backend.common.exceptions import RateLimitedError

# OAuth2 token endpoint the refresh token is redeemed against.
_TOKEN_URI = "https://oauth2.googleapis.com/token"
# "me" resolves to the authenticated account — the mailbox the refresh token
# belongs to, which is not necessarily the address a message is sent as.
_GMAIL_USER = "me"
# An anchor carrying an href, captured as (href, label). A link's URL lives in
# the tag, not between the tags, so the plain-text fallback has to pull it out
# before markup is stripped or it is lost with the tag.
_ANCHOR_RE = re.compile(
    r'(?is)<a\b[^>]*?\bhref\s*=\s*["\']([^"\']*)["\'][^>]*>(.*?)</a\s*>'
)
_TAG_RE = re.compile(r"<[^>]+>")


def _refresh_failure_cause(error) -> str:
    """Describe why google-auth could not redeem the refresh token.

    ``RefreshError`` carries Google's token-endpoint payload as one of its args;
    the ``error`` code in there is the only thing that separates a bad app
    credential from a bad token, and the two need opposite fixes.

    Args:
        error (RefreshError): The exception raised during the refresh.

    Returns:
        str: A one-line cause, naming the failing half where Google identified it.
    """
    code = ""
    for arg in error.args:
        if isinstance(arg, dict) and arg.get("error"):
            code = arg["error"]
            break
    if code == "invalid_client":
        return (
            "the OAuth client id/secret pair was rejected (invalid_client) — the "
            "refresh token was not examined; check the client credentials, not "
            "the token"
        )
    if code == "invalid_grant":
        return (
            "the refresh token was rejected (invalid_grant) — revoked, expired, "
            "or minted by a different OAuth client; re-authorize the mailbox"
        )
    return f"the token refresh was rejected ({code or error})"


class GmailClient:
    """Domain-agnostic Gmail send/read transport (see module docstring)."""

    def __init__(self, logger, retry_utils, sender_addresses):
        """
        Read the Gmail credentials from the environment.

        No network call is made here; the Gmail service is built lazily on first
        use and cached.

        Args:
            logger: Application logger.
            retry_utils: Provides ``get_retry_on_transient(fn)`` to wrap calls.
            sender_addresses (list[str]): Every address this mailbox may send
                as — one per sending service. Passed in rather than read from
                the environment: which services exist is a wiring question, and
                this class stays unaware of them. Each must be verified as a
                Send-As on the mailbox.

        Raises:
            ValueError: If any required environment variable is missing, if
                ``sender_addresses`` is empty, or if ``logger`` /
                ``retry_utils`` is not provided.
        """
        self._client_id = os.getenv(GMAIL_CLIENT_ID)
        self._client_secret = os.getenv(GMAIL_CLIENT_SECRET)
        self._refresh_token = os.getenv(GMAIL_REFRESH_TOKEN)
        self._sender_addresses = {
            parseaddr(address)[1].lower()
            for address in (sender_addresses or [])
            if parseaddr(address or "")[1]
        }
        self._logger = logger
        self._retry_utils = retry_utils
        self._service = None

        if not self._client_id:
            raise ValueError("Missing environment variable: GMAIL_CLIENT_ID")
        if not self._client_secret:
            raise ValueError("Missing environment variable: GMAIL_CLIENT_SECRET")
        if not self._refresh_token:
            raise ValueError("Missing environment variable: GMAIL_REFRESH_TOKEN")
        if not self._sender_addresses:
            raise ValueError("sender_addresses must hold at least one address")
        if not self._logger:
            raise ValueError("logger must be provided")
        if not self._retry_utils:
            raise ValueError("retry_utils must be provided")

    def owns_address(self, address) -> bool:
        """Whether ``address`` is one of the addresses this mailbox sends as.

        Answers "is this us?" for a synced message's ``From`` (OUTBOUND when
        True, INBOUND otherwise). A raw header is fine: a display name is
        stripped and case is ignored. Blank or unparseable input is not ours.

        Args:
            address (str | None): An address or a full ``From`` header value.

        Returns:
            bool: True when the address is configured on this client.
        """
        return parseaddr(address or "")[1].lower() in self._sender_addresses

    def send_message(
        self,
        to,
        cc,
        subject,
        body,
        sender,
        thread_id=None,
        in_reply_to=None,
        references=None,
    ):
        """
        Send an HTML email as one of our addresses, optionally as a thread reply.

        The message is sent as ``multipart/alternative`` — the HTML ``body`` plus
        a plain-text fallback derived from it. A fresh ``Message-ID`` is minted
        and set on the outgoing mail so the caller can persist it without a
        follow-up read.

        Args:
            to (list[str]): Recipient addresses.
            cc (list[str]): Cc addresses (may be empty).
            subject (str): Subject line.
            body (str): HTML body.
            sender (str): The address to send as — an address this client owns,
                optionally with a display name (``Name <addr>``). Required: the
                transport holds no default sender, so a caller that omits it
                fails here instead of silently going out as the mailbox owner.
            thread_id (str | None): Gmail thread id to reply into (``None`` for a
                new thread).
            in_reply_to (str | None): ``Message-ID`` of the message being replied
                to (reply only).
            references (str | None): ``References`` header value (reply only).

        Returns:
            dict: ``{"gmail_message_id", "gmail_thread_id", "rfc822_message_id"}``.

        Raises:
            ValueError: If ``sender`` is not an address this mailbox sends as.
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        if not self.owns_address(sender):
            raise ValueError(
                f"Not a configured sender address for this mailbox: {sender!r}"
            )
        sender_domain = parseaddr(sender)[1].split("@")[-1]
        rfc822_message_id = make_msgid(domain=sender_domain)
        mime = self._build_mime(
            to, cc, subject, body, sender, rfc822_message_id, in_reply_to, references
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

    def list_thread_message_ids(self, thread_id):
        """
        List a thread's Gmail message ids — no headers, no bodies.

        This is the cheap half of an incremental sync: the caller diffs these
        ids against what it already stored and fetches bodies only for the
        ones it lacks (``get_message``). ``format="metadata"`` plus a
        ``messages(id)`` field mask keeps the response to a list of ids
        regardless of how long the conversation has grown.

        Args:
            thread_id (str): Gmail thread id.

        Returns:
            list[str]: Gmail message ids, in the order Gmail returns them.

        Raises:
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        request = (
            self._get_service()
            .users()
            .threads()
            .get(
                userId=_GMAIL_USER,
                id=thread_id,
                format="metadata",
                fields="messages(id)",
            )
        )
        thread = self._execute(request, "list_thread_message_ids")
        return [message["id"] for message in thread.get("messages", [])]

    def get_message(self, message_id):
        """
        Fetch and parse one message.

        ``users.messages.get`` returns the same Message resource that appears
        inside a thread, so the parsed dict is identical in shape to what a
        whole-thread read used to yield per message.

        Args:
            message_id (str): Gmail message id.

        Returns:
            dict: Keys ``gmail_message_id``, ``gmail_thread_id``,
            ``rfc822_message_id``, ``from_address``, ``to_addresses``,
            ``cc_addresses``, ``subject``, ``html``, ``plain``, ``snippet``,
            ``gmail_internal_date``.

        Raises:
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure, including a 404 when
                the message was deleted after its id was listed.
        """
        request = (
            self._get_service()
            .users()
            .messages()
            .get(userId=_GMAIL_USER, id=message_id, format="full")
        )
        return self._parse_message(self._execute(request, "get_message"))

    def list_recent_message_thread_ids(self, lookback_days):
        """
        Thread ids that received mail within the last ``lookback_days`` days.

        This is the whole-mailbox half of an incremental sync: one flat-cost
        call tells the caller which conversations are worth looking at, instead
        of asking each conversation in turn. The reply spans the entire
        mailbox, so the caller must filter it down to threads it actually
        tracks.

        The window is expressed as Gmail's ``newer_than:Nd`` search operator.
        That is day-granular — Gmail documents no finer relative form, and
        epoch timestamps are not a documented input — so callers should pass a
        window with slack rather than one that is exactly right.

        Args:
            lookback_days (int): Size of the search window, in days.

        Returns:
            set[str]: Distinct Gmail thread ids. Empty when nothing matched.

        Raises:
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        thread_ids = set()
        page_token = None
        while True:
            request = (
                self._get_service()
                .users()
                .messages()
                .list(
                    userId=_GMAIL_USER,
                    q=f"newer_than:{lookback_days}d",
                    fields="messages/threadId,nextPageToken",
                    pageToken=page_token,
                )
            )
            response = self._execute(request, "list_recent_message_thread_ids")
            for message in response.get("messages", []):
                thread_ids.add(message["threadId"])
            page_token = response.get("nextPageToken")
            if not page_token:
                return thread_ids

    def _get_service(self):
        """Build the Gmail service once (lazily) and cache it on the instance."""
        if self._service is None:
            # No scopes are passed: on a refresh-token grant google-auth would
            # send them as the `scope` param, and Google rejects any value that
            # is not a subset of what the token was actually granted
            # (invalid_scope). Omitting it yields an access token carrying the
            # token's full granted scopes, which is what we authorized once
            # out-of-band.
            #
            # Since the scopes appear nowhere in code, this is their only
            # record: a replacement token must be minted with
            # https://www.googleapis.com/auth/gmail.send plus
            # https://www.googleapis.com/auth/gmail.readonly — send, plus
            # messages.get / messages.list / threads.get. Nothing here modifies
            # the mailbox, so gmail.modify is not needed.
            credentials = Credentials(
                token=None,
                refresh_token=self._refresh_token,
                client_id=self._client_id,
                client_secret=self._client_secret,
                token_uri=_TOKEN_URI,
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
            # token. Two unrelated causes land here and used to be reported
            # identically as "refresh token rejected", which sends whoever reads
            # the log after the wrong one: `invalid_client` means the OAuth
            # client id/secret pair was rejected and the token was never even
            # examined, while `invalid_grant` means the token itself is gone
            # (revoked, expired, or minted by a different OAuth client). Google
            # puts the distinction in the error payload, so pass it through.
            cause = _refresh_failure_cause(error)
            self._logger.error("[GmailClient] %s failed: %s.", operation, cause)
            raise RuntimeError(
                f"Gmail authentication failed during {operation}: {cause}"
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
        self, to, cc, subject, body, sender, rfc822_message_id, in_reply_to, references
    ):
        """Assemble a multipart/alternative message (plain fallback + HTML)."""
        message = MIMEMultipart("alternative")
        message["From"] = sender
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
    def _expand_link(match):
        """
        Render one anchor as ``label (url)`` for the plain-text fallback.

        The url is kept whenever there is one, so a link never reaches a
        plain-text reader as unclickable prose. It is only left out when the
        label already *is* the url, where repeating it would read as
        ``https://x (https://x)``; a ``mailto:`` scheme is likewise dropped when
        the label is the bare address.
        """
        href = match.group(1).strip()
        label = _TAG_RE.sub("", match.group(2)).strip()
        if not href:
            return label
        if not label:
            return href
        bare = unescape(href).removeprefix("mailto:")
        if unescape(label).rstrip("/") in (
            unescape(href).rstrip("/"),
            bare.rstrip("/"),
        ):
            return label
        return f"{label} ({href})"

    @staticmethod
    def _html_to_text(html):
        """Derive a readable plain-text fallback from an HTML body."""
        text = re.sub(r"(?i)<br\s*/?>", "\n", html)
        text = re.sub(r"(?i)</p\s*>", "\n\n", text)
        text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
        text = re.sub(r"(?i)</(h[1-6]|div|ul|ol)\s*>", "\n", text)
        # Must run before the tag strip below, which would take the href with it.
        text = _ANCHOR_RE.sub(GmailClient._expand_link, text)
        text = _TAG_RE.sub("", text)
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
