"""Serving course files on their own origin, and refusing them anywhere else."""

import unittest
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from starlette.exceptions import HTTPException
from starlette.requests import Request

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


def make_request(host, path):
    """Build a request the way an ASGI server would, with `host` in the headers.

    `host=None` builds one with no Host header at all, which is what a bare
    HTTP/1.0 client sends.
    """
    headers = [] if host is None else [(b"host", host.encode("ascii"))]
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

    async def get_asset(self, host, asset_path=ASSET_PATH, token=TOKEN):
        """Call the route and normalise however it reports a refusal.

        A rejection may come back as a response or be raised; either way the
        test cares about the status, the bytes and the headers.
        """
        request = make_request(host, f"/p/{token}/{asset_path}")
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


if __name__ == "__main__":
    unittest.main()
