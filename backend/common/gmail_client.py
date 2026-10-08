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
from the stored refresh token; the built Gmail service is cached per thread and
reused across that thread's calls. Gmail API failures are translated into the
shared domain exceptions (429 -> ``RateLimitedError``; anything else ->
``RuntimeError``) so a failed send never looks like a success to the caller.
"""

import base64
import os
import re
import threading
from datetime import datetime, timezone
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import getaddresses, make_msgid, parseaddr
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
from backend.common.exceptions import (
    GmailNotFoundError,
    GmailUnavailableError,
    HistoryExpiredError,
    RateLimitedError,
)

# OAuth2 token endpoint the refresh token is redeemed against.
_TOKEN_URI = "https://oauth2.googleapis.com/token"
# "me" resolves to the authenticated account — the mailbox the refresh token
# belongs to, which is not necessarily the address a message is sent as.
_GMAIL_USER = "me"

# Messages per batched ``users.messages.get``. Google allows 100 per batch but
# recommends no more than 50, because larger batches are the thing that
# triggers rate limiting. Batching buys HTTP round-trips, never quota: a batch
# of n counts as n requests, so the only reason to grow it is latency, and
# past 50 that trade turns against us.
_MESSAGE_BATCH_SIZE = 50
# An anchor carrying an href, captured as (href, label). A link's URL lives in
# the tag, not between the tags, so the plain-text fallback has to pull it out
# before markup is stripped or it is lost with the tag.
_ANCHOR_RE = re.compile(
    r'(?is)<a\b[^>]*?\bhref\s*=\s*["\']([^"\']*)["\'][^>]*>(.*?)</a\s*>'
)
_TAG_RE = re.compile(r"<[^>]+>")


def _google_explanation(error):
    """Return Google's own account of an HttpError, or "" when it sent none.

    The status code alone rarely says what to fix: a 400 from ``watch`` can
    mean a malformed topic or a topic in the wrong project, and only the
    message tells them apart.

    Args:
        error (HttpError): The error googleapiclient raised.

    Returns:
        str: ``"<message> (<reason>)"``, either part left out when absent.
    """
    message = error.reason if isinstance(error.reason, str) else ""
    details = error.error_details
    reason = ""
    if isinstance(details, list) and details and isinstance(details[0], dict):
        reason = details[0].get("reason") or ""
    # Without a body googleapiclient falls back to the HTTP reason phrase,
    # which repeats the status and explains nothing.
    if message == getattr(error.resp, "reason", None):
        message = ""
    if message and reason:
        return f"{message} ({reason})"
    return message or reason


def _with_explanation(text, error):
    """Append Google's explanation of ``error`` to ``text`` when it gave one."""
    explanation = _google_explanation(error)
    return f"{text}: {explanation}" if explanation else text


class GmailClient:
    """Domain-agnostic Gmail send/read transport (see module docstring)."""

    def __init__(self, logger, retry_utils, sender_addresses):
        """
        Read the Gmail credentials from the environment.

        No network call is made here; the Gmail service is built lazily on each
        thread's first use and cached there.

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
        self._local = threading.local()

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
            to, subject, body, sender, rfc822_message_id, in_reply_to, references
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
            ``subject``, ``html``, ``plain``, ``snippet``,
            ``gmail_internal_date``, ``failed_recipients``, ``recipients``
            (To, Cc and every Delivered-To, lower-cased, de-duplicated),
            ``auto_submitted``, ``precedence`` and ``attachments`` (a list of
            ``{"name", "size", "gmailAttachmentId"}``).

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

    def get_attachment(self, message_id, attachment_id):
        """Download one attachment of a message.

        Args:
            message_id (str): Gmail message id.
            attachment_id (str): ``gmailAttachmentId`` from ``get_message``.

        Returns:
            bytes: The decoded attachment content.

        Raises:
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        request = (
            self._get_service()
            .users()
            .messages()
            .attachments()
            .get(userId=_GMAIL_USER, messageId=message_id, id=attachment_id)
        )
        response = self._execute(request, "get_attachment")
        return base64.urlsafe_b64decode(response["data"].encode("ascii"))

    def list_send_as_addresses(self):
        """Return the mailbox's Send-As addresses, lower-cased.

        Returns:
            set[str]: Every ``sendAsEmail`` configured on the mailbox.

        Raises:
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        request = (
            self._get_service().users().settings().sendAs().list(userId=_GMAIL_USER)
        )
        response = self._execute(request, "list_send_as_addresses")
        return {
            entry["sendAsEmail"].strip().lower()
            for entry in response.get("sendAs", [])
            if entry.get("sendAsEmail")
        }

    def get_messages(self, message_ids):
        """
        Fetch and parse many messages, batching the Gmail calls.

        One HTTP request carries up to ``_MESSAGE_BATCH_SIZE`` inner
        ``users.messages.get`` calls, which is the whole point: a per-message
        loop pays a round-trip each time and, run concurrently instead, trips
        Gmail's per-user concurrency limit. A batch is one request on one
        thread, so it does neither.

        Quota is unaffected — a batch of n counts as n requests — so this is a
        latency change, not a cost one.

        Failure behaviour matches ``get_message`` exactly: the first inner call
        that failed raises, and nothing is returned for the batch. Gmail may
        execute a batch's calls in any order, so results are re-ordered to
        match ``message_ids`` before returning.

        Args:
            message_ids (list[str]): Gmail message ids, in the order the
                caller wants them back.

        Returns:
            list[dict]: One parsed message per id, in ``message_ids`` order.
                Same shape as ``get_message``. Empty list for empty input.

        Raises:
            RateLimitedError: If Gmail throttles the batch, or reports 429 for
                one of its inner calls.
            RuntimeError: For any other Gmail API failure, including a 404 when
                a message was deleted after its id was listed.
        """
        if not message_ids:
            return []

        parsed = {}
        failures = []

        def _collect(request_id, response, exception):
            if exception is not None:
                failures.append(exception)
                return
            parsed[request_id] = self._parse_message(response)

        service = self._get_service()
        for start in range(0, len(message_ids), _MESSAGE_BATCH_SIZE):
            chunk = message_ids[start : start + _MESSAGE_BATCH_SIZE]
            batch = service.new_batch_http_request(callback=_collect)
            for message_id in chunk:
                batch.add(
                    service.users()
                    .messages()
                    .get(userId=_GMAIL_USER, id=message_id, format="full"),
                    request_id=message_id,
                )
            # A batch object exposes ``execute`` like a single request, so the
            # same retry and error translation applies. This covers the batch
            # request itself; an inner call's failure arrives via the callback.
            self._execute(batch, "get_messages")
            if failures:
                self._raise_batch_failure(failures[0])

        return [parsed[message_id] for message_id in message_ids]

    def _raise_batch_failure(self, exception):
        """Translate an inner batch failure the way ``_execute`` would.

        Inner calls never reach ``_execute`` — googleapiclient hands their
        errors to the batch callback instead — so the mapping from HTTP status
        to domain error has to be applied here too, or a rate-limited message
        inside a batch would surface as a generic RuntimeError and lose its
        retry.

        Args:
            exception (Exception): The error googleapiclient reported for one
                inner call.

        Raises:
            RateLimitedError: The inner call was rate limited (HTTP 429).
            GmailNotFoundError: The inner call got HTTP 404.
            GmailUnavailableError: The inner call got HTTP 5xx.
            RuntimeError: Any other inner-call failure.
        """
        if not isinstance(exception, HttpError):
            self._logger.error(
                "[GmailClient] get_messages failed for one message (status=None)"
            )
            raise RuntimeError("Gmail API error during get_messages") from exception
        self._raise_http_error(
            exception, "get_messages", "get_messages failed for one message"
        )

    def get_profile(self):
        """Read the mailbox address and its current history cursor.

        Returns:
            dict: ``email_address`` (lower-cased str) and ``history_id`` (int).

        Raises:
            GmailUnavailableError: Gmail answered 5xx.
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        request = (
            self._get_service()
            .users()
            .getProfile(userId=_GMAIL_USER, fields="emailAddress,historyId")
        )
        response = self._execute(request, "get_profile")
        return {
            "email_address": response["emailAddress"].lower(),
            "history_id": int(response["historyId"]),
        }

    def watch(self, topic_name):
        """Ask Gmail to publish INBOX changes to a Pub/Sub topic.

        Only INBOX is watched so that mail this application sends itself does
        not produce a push.

        Args:
            topic_name (str): Full topic name, ``projects/<p>/topics/<t>``.

        Returns:
            dict: ``history_id`` (int) at registration time and ``expiration``
                (timezone-aware UTC datetime) of the watch.

        Raises:
            GmailUnavailableError: Gmail answered 5xx.
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        request = (
            self._get_service()
            .users()
            .watch(
                userId=_GMAIL_USER,
                body={
                    "topicName": topic_name,
                    "labelIds": ["INBOX"],
                    "labelFilterBehavior": "include",
                },
            )
        )
        response = self._execute(request, "watch")
        return {
            "history_id": int(response["historyId"]),
            "expiration": datetime.fromtimestamp(
                int(response["expiration"]) / 1000, tz=timezone.utc
            ),
        }

    def list_history(self, start_history_id):
        """Thread ids that gained a message since a history cursor.

        No ``labelId`` is passed, so a message sent by hand from the Gmail web
        UI is reported as well, not just INBOX arrivals. A thread whose added
        messages all carry ``SENT`` holds only our own new mail.

        Args:
            start_history_id (int): Cursor to read changes after.

        Returns:
            dict: ``history_id`` (int), the mailbox cursor from the response
                (present even when nothing changed), ``thread_ids``
                (set[str]), and ``sent_only_thread_ids`` (set[str]), the
                threads among them whose added messages are all ``SENT``.

        Raises:
            HistoryExpiredError: The cursor is too old (HTTP 404); only a full
                resync recovers.
            GmailUnavailableError: Gmail answered 5xx.
            RateLimitedError: If Gmail throttles the request (HTTP 429).
            RuntimeError: For any other Gmail API failure.
        """
        thread_ids = set()
        not_sent = set()
        page_token = None
        while True:
            request = (
                self._get_service()
                .users()
                .history()
                .list(
                    userId=_GMAIL_USER,
                    startHistoryId=str(start_history_id),
                    historyTypes=["messageAdded"],
                    pageToken=page_token,
                )
            )
            try:
                response = self._execute(request, "list_history")
            except GmailNotFoundError as error:
                raise HistoryExpiredError(
                    f"history cursor {start_history_id} expired"
                ) from error
            for record in response.get("history", []):
                for added in record.get("messagesAdded", []):
                    message = added["message"]
                    thread_ids.add(message["threadId"])
                    if "SENT" not in (message.get("labelIds") or []):
                        not_sent.add(message["threadId"])
            page_token = response.get("nextPageToken")
            if not page_token:
                return {
                    "history_id": int(response["historyId"]),
                    "thread_ids": thread_ids,
                    "sent_only_thread_ids": thread_ids - not_sent,
                }

    def _get_service(self):
        """Build the Gmail service lazily and cache it on the calling thread.

        A service owns a single ``httplib2`` connection, and httplib2 requires
        one instance per thread: threads sharing a service write into the same
        socket and read each other's replies. Sends run concurrently — callers
        wrap them in ``asyncio.to_thread`` — so each thread resolves its own
        service, and its own credentials with it, since a ``Credentials``
        object holds a mutable access token and expiry that concurrent
        refreshes would race on.

        Building costs about a millisecond and no network call, because the
        discovery document ships with the library. The number of live
        connections is therefore bounded by the executor's thread count, and a
        thread reuses its own connection across calls.

        Returns:
            googleapiclient.discovery.Resource: The calling thread's service.
        """
        service = getattr(self._local, "service", None)
        if service is None:
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
            # messages.get / messages.list / threads.get / history.list /
            # watch / getProfile. Nothing here modifies
            # the mailbox, so gmail.modify is not needed.
            credentials = Credentials(
                token=None,
                refresh_token=self._refresh_token,
                client_id=self._client_id,
                client_secret=self._client_secret,
                token_uri=_TOKEN_URI,
            )
            service = build(
                "gmail", "v1", credentials=credentials, cache_discovery=False
            )
            self._local.service = service
        return service

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
            self._raise_http_error(error, operation, f"{operation} failed")

    def _raise_http_error(self, error, operation, log_label):
        """Log an HttpError and raise it as the matching domain error.

        Google's explanation goes into both the log and the raised message, so
        it reaches the ops alert and ``gmail_sync_state.last_error``.

        Args:
            error (HttpError): The error googleapiclient raised.
            operation (str): The Gmail call, for the raised message.
            log_label (str): What failed, for the log line.

        Raises:
            RateLimitedError: HTTP 429.
            GmailNotFoundError: HTTP 404.
            GmailUnavailableError: HTTP 5xx.
            RuntimeError: Any other status.
        """
        status = getattr(error.resp, "status", None)
        self._logger.error(
            "%s",
            _with_explanation(f"[GmailClient] {log_label} (status={status})", error),
        )
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            raise RateLimitedError(
                _with_explanation(f"Gmail rate limited during {operation}", error)
            ) from error
        if status == HTTPStatus.NOT_FOUND:
            raise GmailNotFoundError(
                _with_explanation(f"Gmail resource not found during {operation}", error)
            ) from error
        if status is not None and status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise GmailUnavailableError(
                _with_explanation(f"Gmail unavailable during {operation}", error)
            ) from error
        raise RuntimeError(
            _with_explanation(f"Gmail API error during {operation}", error)
        ) from error

    def _build_mime(
        self, to, subject, body, sender, rfc822_message_id, in_reply_to, references
    ):
        """Assemble a multipart/alternative message (plain fallback + HTML)."""
        message = MIMEMultipart("alternative")
        message["From"] = sender
        message["To"] = ", ".join(to)
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
        raw_headers = payload.get("headers", [])

        def _all(name):
            return [h["value"] for h in raw_headers if h["name"].lower() == name]

        recipients = []
        for _, addr in getaddresses(_all("to") + _all("cc") + _all("delivered-to")):
            addr = addr.strip().lower()
            if addr and addr not in recipients:
                recipients.append(addr)
        return {
            "gmail_message_id": message.get("id"),
            "gmail_thread_id": message.get("threadId"),
            "rfc822_message_id": headers.get("message-id"),
            "from_address": headers.get("from"),
            "to_addresses": headers.get("to"),
            "subject": headers.get("subject"),
            "html": html_body,
            "plain": plain_body,
            "snippet": message.get("snippet"),
            "gmail_internal_date": message.get("internalDate"),
            "failed_recipients": self._failed_recipients(headers),
            "recipients": recipients,
            "auto_submitted": headers.get("auto-submitted"),
            "precedence": headers.get("precedence"),
            "attachments": self._extract_attachments(payload),
        }

    @staticmethod
    def _extract_attachments(payload):
        """List the named attachment parts of a payload, without their bytes."""
        attachments = []
        stack = [payload]
        while stack:
            part = stack.pop()
            body = part.get("body", {})
            if part.get("filename") and body.get("attachmentId"):
                attachments.append({
                    "name": part["filename"],
                    "size": body.get("size", 0),
                    "gmailAttachmentId": body["attachmentId"],
                })
            stack.extend(reversed(part.get("parts", []) or []))
        return attachments

    @staticmethod
    def _failed_recipients(headers):
        """Who a delivery-failure report says could not be reached.

        A message is such a report when its Content-Type is
        ``multipart/report`` with ``report-type=delivery-status``, or when it
        carries ``X-Failed-Recipients``. ``Auto-Submitted`` does not decide it:
        Gmail sets ``auto-replied`` on its bounces and out-of-office replies
        alike. Nor does the From address, since a person can write from
        ``postmaster@``.

        Args:
            headers (dict[str, str]): The message's headers, names lower-cased.

        Returns:
            str | None: None for any other message; otherwise the raw
                ``X-Failed-Recipients`` value, or "" when there is none.
        """
        failed = headers.get("x-failed-recipients")
        content_type = Message()
        content_type["Content-Type"] = headers.get("content-type", "")
        is_report = (
            content_type.get_content_type() == "multipart/report"
            and str(content_type.get_param("report-type") or "").lower()
            == "delivery-status"
        )
        if failed is None and not is_report:
            return None
        return (failed or "").strip()

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
