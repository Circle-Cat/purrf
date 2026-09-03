"""Serving course files on their own origin, and refusing them anywhere else."""

import unittest
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from starlette.exceptions import HTTPException
from starlette.requests import Request

from backend.training.byte_range import UnsatisfiableRange, resolve_range
from backend.training.content_host import resolve_content_host
from backend.training.training_content_controller import (
    _CACHE_CONTROL,
    TrainingContentController,
)
from backend.training.training_content_service import ContentAsset
from backend.training.training_content_token import InvalidContentToken

CONTENT_HOST = "training-content.example.com"
APP_HOST = "app.example.com"
TOKEN = "eyJlIjoxfQ.c2lnbmF0dXJl"
ASSET_PATH = "scormcontent/assets/lesson.mp3"
ASSET_BYTES = b"\x00\x01course-audio-bytes\x02\x03"
ASSET_CONTENT_TYPE = "audio/mpeg"


def make_request(host, path, range_header=None):
    """Build a request the way an ASGI server would, with `host` in the headers.

    `host=None` builds one with no Host header at all, which is what a bare
    HTTP/1.0 client sends.
    """
    headers = [] if host is None else [(b"host", host.encode("ascii"))]
    if range_header is not None:
        headers.append((b"range", range_header.encode("latin-1")))
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "root_path": "",
        "query_string": b"",
        "headers": headers,
        "server": (host.split(":")[0] if host else "unknown", 443),
        "client": ("203.0.113.7", 51234),
    })


async def read_body(response):
    """Collect the bytes of either a buffered or a streaming response."""
    if hasattr(response, "body"):
        return bytes(response.body)
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else str(chunk).encode())
    return b"".join(chunks)


class TestTrainingContentController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.content_service = MagicMock()
        self.content_service.read_asset = AsyncMock(
            return_value=ContentAsset(data=ASSET_BYTES, content_type=ASSET_CONTENT_TYPE)
        )
        self.logger = MagicMock()
        self.controller = TrainingContentController(
            self.content_service, CONTENT_HOST, self.database, self.logger
        )

    async def get_asset(
        self, host, asset_path=ASSET_PATH, token=TOKEN, range_header=None
    ):
        """Call the route and normalise however it reports a refusal.

        A rejection may come back as a response or be raised; either way the
        test cares about the status, the bytes and the headers.
        """
        request = make_request(host, f"/p/{token}/{asset_path}", range_header)
        try:
            response = await self.controller.get_asset(token, asset_path, request)
        except HTTPException as error:
            return SimpleNamespace(
                status_code=int(error.status_code),
                body=str(error.detail).encode("utf-8"),
                headers=error.headers or {},
            )
        return SimpleNamespace(
            status_code=int(response.status_code),
            body=await read_body(response),
            headers=response.headers,
        )

    def assert_refused_without_the_asset(self, outcome):
        self.assertNotEqual(outcome.status_code, HTTPStatus.OK)
        self.assertGreaterEqual(outcome.status_code, 400)
        self.assertLess(outcome.status_code, 500)
        self.assertNotIn(ASSET_BYTES, outcome.body)

    async def test_a_request_on_the_content_host_returns_the_asset(self):
        outcome = await self.get_asset(CONTENT_HOST)

        self.assertEqual(outcome.status_code, HTTPStatus.OK)
        self.assertEqual(outcome.body, ASSET_BYTES)
        self.assertEqual(outcome.headers["content-type"], ASSET_CONTENT_TYPE)

    async def test_the_same_asset_is_refused_on_the_app_host(self):
        """Serving it here would re-anchor course files on the app origin, and
        the course would be same-origin with everything the learner can do."""
        outcome = await self.get_asset(APP_HOST)

        self.assert_refused_without_the_asset(outcome)

    async def test_a_host_header_carrying_a_port_is_still_the_content_host(self):
        outcome = await self.get_asset(f"{CONTENT_HOST}:443")

        self.assertEqual(outcome.status_code, HTTPStatus.OK)
        self.assertEqual(outcome.body, ASSET_BYTES)

    async def test_a_host_header_in_another_case_is_still_the_content_host(self):
        """Host is case-insensitive, and the configured value must be lowercase.

        A proxy that preserves the case an operator typed would otherwise 404
        every course file, and the middleware exemption would stop applying at
        the same moment, turning that into a 401.
        """
        outcome = await self.get_asset(CONTENT_HOST.upper())

        self.assertEqual(outcome.status_code, HTTPStatus.OK)
        self.assertEqual(outcome.body, ASSET_BYTES)

    async def test_a_host_that_only_resembles_the_content_host_is_refused(self):
        """Neither a prefix nor a suffix of the real name is the real name."""
        for host in [
            f"evil-{CONTENT_HOST}",
            f"{CONTENT_HOST}.evil.test",
        ]:
            with self.subTest(host=host):
                outcome = await self.get_asset(host)

                self.assert_refused_without_the_asset(outcome)

    async def test_a_request_with_no_host_header_is_refused(self):
        """An absent Host is not the content host, so it fails closed."""
        outcome = await self.get_asset(None)

        self.assert_refused_without_the_asset(outcome)

    async def test_a_refusal_says_which_host_asked_and_which_one_is_expected(self):
        await self.get_asset(APP_HOST)

        template, *arguments = self.logger.warning.call_args.args
        logged = template % tuple(arguments)
        self.assertIn(APP_HOST, logged)
        self.assertIn(CONTENT_HOST, logged)

    async def test_a_host_header_cannot_forge_a_log_line(self):
        """The Host header is whatever the client sent, newlines included."""
        await self.get_asset("evil.test\r\nWARNING forged log line")

        template, *arguments = self.logger.warning.call_args.args
        logged = template % tuple(arguments)
        self.assertNotIn("\n", logged)
        self.assertNotIn("\r", logged)

    async def test_an_overlong_host_header_is_not_logged_whole(self):
        await self.get_asset("a" * 5000 + ".test")

        template, *arguments = self.logger.warning.call_args.args
        logged = template % tuple(arguments)
        self.assertLess(len(logged), 400)

    async def test_an_expired_token_is_401_and_returns_no_bytes(self):
        """401 is what tells the app page to mint a fresh session token."""
        self.content_service.read_asset.side_effect = InvalidContentToken(
            "Content token has expired."
        )

        outcome = await self.get_asset(CONTENT_HOST)

        self.assertEqual(outcome.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertNotIn(ASSET_BYTES, outcome.body)

    async def test_a_path_escaping_the_package_is_a_client_error_not_a_500(self):
        self.content_service.read_asset.side_effect = PermissionError(
            "Asset path escapes the package."
        )

        outcome = await self.get_asset(CONTENT_HOST, asset_path="../../etc/passwd")

        self.assert_refused_without_the_asset(outcome)

    async def test_a_served_asset_is_cacheable_within_the_session(self):
        """A new token changes the URL, which is what invalidates the cache."""
        self.assertEqual(_CACHE_CONTROL, "private, max-age=3600")

        outcome = await self.get_asset(CONTENT_HOST)

        self.assertEqual(outcome.headers["cache-control"], _CACHE_CONTROL)

    async def test_the_content_origin_sets_no_cookie_and_echoes_no_credential(self):
        """This origin is deliberately cookie-free: a course reading one here
        is the failure the separate hostname exists to prevent."""
        outcome = await self.get_asset(CONTENT_HOST)

        self.assertNotIn("set-cookie", outcome.headers)
        for name, value in outcome.headers.items():
            self.assertNotIn(TOKEN, value, msg=name)
        self.assertNotIn(TOKEN.encode("ascii"), outcome.body)


class TestDisabledContentHosting(unittest.IsolatedAsyncioTestCase):
    """A content host that cannot be shown to differ from the app's own
    origins disables the route outright, rather than stopping the app."""

    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.content_service = MagicMock()
        self.content_service.read_asset = AsyncMock(
            return_value=ContentAsset(data=ASSET_BYTES, content_type=ASSET_CONTENT_TYPE)
        )
        self.logger = MagicMock()
        # APP_ORIGINS is missing, so the resolver hands the controller nothing.
        self.resolved_host = resolve_content_host(CONTENT_HOST, None, self.logger)
        self.controller = TrainingContentController(
            self.content_service, self.resolved_host, self.database, self.logger
        )

    def test_the_resolver_disabled_hosting(self):
        self.assertIsNone(self.resolved_host)

    async def test_no_host_gets_an_asset_out_of_the_route(self):
        for host in [CONTENT_HOST, APP_HOST, f"{CONTENT_HOST}:443", None]:
            with self.subTest(host=host):
                request = make_request(host, f"/p/{TOKEN}/{ASSET_PATH}")

                response = await self.controller.get_asset(TOKEN, ASSET_PATH, request)

                self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
                self.assertEqual(await read_body(response), b"")

    async def test_the_route_never_reaches_storage(self):
        request = make_request(CONTENT_HOST, f"/p/{TOKEN}/{ASSET_PATH}")

        await self.controller.get_asset(TOKEN, ASSET_PATH, request)

        self.content_service.read_asset.assert_not_awaited()
        self.database.session.assert_not_called()


class TestByteRanges(unittest.IsolatedAsyncioTestCase):
    """What a `<video>` element asks this route for.

    The real mentee onboarding package ships a 3.7 MB MP4, and Safari and iOS
    will not play a media element that answers a range request with a 200.
    """

    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.database = MagicMock()
        self.database.session.return_value.__aenter__.return_value = self.session
        self.database.session.return_value.__aexit__.return_value = None

        self.content_service = MagicMock()
        self.content_service.read_asset = AsyncMock(side_effect=self.serve)
        self.logger = MagicMock()
        self.controller = TrainingContentController(
            self.content_service, CONTENT_HOST, self.database, self.logger
        )

    async def serve(self, session, token, asset_path, byte_range=None):
        """Stand in for the service, honouring whatever range reaches it."""
        if byte_range is None:
            return ContentAsset(data=ASSET_BYTES, content_type=ASSET_CONTENT_TYPE)
        resolved = resolve_range(byte_range, len(ASSET_BYTES))
        if resolved is None:
            raise UnsatisfiableRange(len(ASSET_BYTES))
        return ContentAsset(
            data=ASSET_BYTES[resolved.start : resolved.end + 1],
            content_type=ASSET_CONTENT_TYPE,
            partial=resolved,
        )

    async def get_asset(self, range_header=None):
        request = make_request(CONTENT_HOST, f"/p/{TOKEN}/{ASSET_PATH}", range_header)
        response = await self.controller.get_asset(TOKEN, ASSET_PATH, request)
        return SimpleNamespace(
            status_code=int(response.status_code),
            body=await read_body(response),
            headers=response.headers,
        )

    def requested_range(self):
        """The range the route handed the service."""
        call = self.content_service.read_asset.call_args
        if len(call.args) > 3:
            return call.args[3]
        return call.kwargs.get("byte_range")

    async def test_a_request_with_no_range_gets_the_whole_object(self):
        outcome = await self.get_asset()

        self.assertEqual(outcome.status_code, HTTPStatus.OK)
        self.assertEqual(outcome.body, ASSET_BYTES)
        self.assertIsNone(self.requested_range())

    async def test_a_whole_object_says_ranges_are_available(self):
        """Without this a media element never asks for one in the first place."""
        outcome = await self.get_asset()

        self.assertEqual(outcome.headers["accept-ranges"], "bytes")
        self.assertNotIn("content-range", outcome.headers)

    async def test_a_bounded_range_comes_back_as_partial_content(self):
        outcome = await self.get_asset("bytes=2-7")

        self.assertEqual(outcome.status_code, HTTPStatus.PARTIAL_CONTENT)
        self.assertEqual(outcome.body, ASSET_BYTES[2:8])
        self.assertEqual(
            outcome.headers["content-range"], f"bytes 2-7/{len(ASSET_BYTES)}"
        )
        self.assertEqual(outcome.headers["accept-ranges"], "bytes")

    async def test_both_ends_of_a_range_are_inclusive(self):
        outcome = await self.get_asset("bytes=0-0")

        self.assertEqual(outcome.status_code, HTTPStatus.PARTIAL_CONTENT)
        self.assertEqual(outcome.body, ASSET_BYTES[:1])
        self.assertEqual(outcome.headers["content-length"], "1")

    async def test_an_open_ended_range_runs_to_the_last_byte(self):
        outcome = await self.get_asset("bytes=4-")

        self.assertEqual(outcome.status_code, HTTPStatus.PARTIAL_CONTENT)
        self.assertEqual(outcome.body, ASSET_BYTES[4:])
        self.assertEqual(
            outcome.headers["content-range"],
            f"bytes 4-{len(ASSET_BYTES) - 1}/{len(ASSET_BYTES)}",
        )

    async def test_a_leading_dash_asks_for_the_last_bytes(self):
        outcome = await self.get_asset("bytes=-5")

        self.assertEqual(outcome.status_code, HTTPStatus.PARTIAL_CONTENT)
        self.assertEqual(outcome.body, ASSET_BYTES[-5:])
        self.assertEqual(
            outcome.headers["content-range"],
            f"bytes {len(ASSET_BYTES) - 5}-{len(ASSET_BYTES) - 1}/{len(ASSET_BYTES)}",
        )

    async def test_an_end_past_the_object_is_clamped_to_it(self):
        outcome = await self.get_asset("bytes=3-999999")

        self.assertEqual(outcome.status_code, HTTPStatus.PARTIAL_CONTENT)
        self.assertEqual(outcome.body, ASSET_BYTES[3:])
        self.assertEqual(
            outcome.headers["content-range"],
            f"bytes 3-{len(ASSET_BYTES) - 1}/{len(ASSET_BYTES)}",
        )

    async def test_a_start_past_the_object_is_refused_with_its_size(self):
        outcome = await self.get_asset(f"bytes={len(ASSET_BYTES)}-")

        self.assertEqual(
            outcome.status_code, HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE
        )
        self.assertEqual(
            outcome.headers["content-range"], f"bytes */{len(ASSET_BYTES)}"
        )
        self.assertEqual(outcome.body, b"")

    async def test_a_refusal_does_not_claim_ranges_alongside_no_body(self):
        """Accept-Ranges belongs with a body; the 416 already says ranges are
        understood."""
        outcome = await self.get_asset(f"bytes={len(ASSET_BYTES)}-")

        self.assertNotIn("accept-ranges", outcome.headers)

    async def test_a_refused_range_leaves_a_line_naming_the_size(self):
        await self.get_asset("bytes=99999-")

        template, *arguments = self.logger.info.call_args.args
        logged = template % tuple(arguments)
        self.assertIn(str(len(ASSET_BYTES)), logged)

    async def test_a_malformed_range_serves_the_whole_object(self):
        """An unreadable Range is ignored, never an error."""
        for value in ["bytes=abc", "bytes=", "items=0-10", "bytes=9-3"]:
            with self.subTest(value=value):
                outcome = await self.get_asset(value)

                self.assertEqual(outcome.status_code, HTTPStatus.OK)
                self.assertEqual(outcome.body, ASSET_BYTES)
                self.assertEqual(outcome.headers["accept-ranges"], "bytes")

    async def test_several_ranges_at_once_get_the_whole_object(self):
        outcome = await self.get_asset("bytes=0-3,8-11")

        self.assertEqual(outcome.status_code, HTTPStatus.OK)
        self.assertEqual(outcome.body, ASSET_BYTES)

    async def test_a_range_header_cannot_forge_a_log_line(self):
        await self.get_asset("bytes=99999-\r\nWARNING forged")

        for call in self.logger.info.call_args_list + self.logger.debug.call_args_list:
            template, *arguments = call.args
            logged = template % tuple(arguments)
            self.assertNotIn("\n", logged)
            self.assertNotIn("\r", logged)

    async def test_an_overlong_range_header_is_not_logged_whole(self):
        await self.get_asset("bytes=" + "9" * 5000)

        for call in self.logger.info.call_args_list + self.logger.debug.call_args_list:
            template, *arguments = call.args
            self.assertLess(len(template % tuple(arguments)), 400)

    async def test_a_range_still_caches_the_way_a_whole_object_does(self):
        outcome = await self.get_asset("bytes=0-3")

        self.assertEqual(outcome.headers["cache-control"], _CACHE_CONTROL)

    async def test_a_range_is_not_a_way_onto_the_app_host(self):
        """The host check runs before anything looks at a Range header."""
        request = make_request(APP_HOST, f"/p/{TOKEN}/{ASSET_PATH}", "bytes=0-3")

        response = await self.controller.get_asset(TOKEN, ASSET_PATH, request)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(await read_body(response), b"")
        self.content_service.read_asset.assert_not_awaited()

    async def test_a_range_is_not_a_way_past_the_token_check(self):
        self.content_service.read_asset.side_effect = InvalidContentToken("expired")

        outcome = await self.get_asset("bytes=0-3")

        self.assertEqual(outcome.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(outcome.body, b"")

    async def test_a_range_is_not_a_way_out_of_the_package(self):
        self.content_service.read_asset.side_effect = PermissionError("escapes")

        outcome = await self.get_asset("bytes=0-3")

        self.assertEqual(outcome.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(outcome.body, b"")

    async def test_serving_a_range_leaves_no_line_per_asset(self):
        """A course load is hundreds of requests and a seek is hundreds more."""
        await self.get_asset("bytes=0-3")

        self.logger.info.assert_not_called()
        self.logger.warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
