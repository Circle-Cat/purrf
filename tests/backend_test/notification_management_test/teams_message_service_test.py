import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx

from backend.notification_management.teams_message_service import (
    BOT_FRAMEWORK_SCOPE,
    TeamsMessageService,
)

CONVERSATIONS_URL = "https://smba.trafficmanager.net/teams/v3/conversations"


class TeamsMessageServiceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self, *responses):
        """A service whose Bot Connector answers with ``responses`` in order."""
        self.requests = []
        queue = list(responses)

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return queue.pop(0)

        self.credential = MagicMock()
        self.credential.get_token = AsyncMock(
            return_value=SimpleNamespace(token="tok")
        )
        return TeamsMessageService(
            logger=MagicMock(),
            app_id="app",
            tenant_id="tenant",
            credential=self.credential,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    async def test_send_opens_chat_then_posts_activity(self):
        service = self._service(
            httpx.Response(201, json={"id": "a:conv"}),
            httpx.Response(201, json={"id": "1"}),
        )

        await service.send("aad-1", "<p>hi</p>")

        opened, posted = self.requests
        self.assertEqual(str(opened.url), CONVERSATIONS_URL)
        self.assertEqual(opened.headers["Authorization"], "Bearer tok")
        self.assertEqual(
            json.loads(opened.content),
            {
                "bot": {"id": "28:app"},
                "members": [{"id": "aad-1"}],
                "channelData": {"tenant": {"id": "tenant"}},
                "isGroup": False,
            },
        )
        self.assertEqual(str(posted.url), f"{CONVERSATIONS_URL}/a:conv/activities")
        self.assertEqual(posted.headers["Authorization"], "Bearer tok")
        self.assertEqual(
            json.loads(posted.content),
            {"type": "message", "textFormat": "xml", "text": "<p>hi</p>"},
        )

    async def test_send_raises_lookup_error_when_chat_forbidden(self):
        service = self._service(httpx.Response(403, json={}))

        with self.assertRaises(LookupError):
            await service.send("aad-1", "<p>hi</p>")
        self.assertEqual(len(self.requests), 1)

    async def test_send_raises_lookup_error_when_user_not_found(self):
        service = self._service(httpx.Response(404, json={}))

        with self.assertRaises(LookupError):
            await service.send("aad-1", "<p>hi</p>")

    async def test_send_raises_runtime_error_when_chat_fails(self):
        service = self._service(httpx.Response(500, json={}))

        with self.assertRaises(RuntimeError):
            await service.send("aad-1", "<p>hi</p>")

    async def test_send_raises_runtime_error_when_post_fails(self):
        service = self._service(
            httpx.Response(201, json={"id": "a:conv"}),
            httpx.Response(502, json={}),
        )

        with self.assertRaises(RuntimeError):
            await service.send("aad-1", "<p>hi</p>")

    async def test_send_asks_for_bot_framework_scope(self):
        service = self._service(
            httpx.Response(201, json={"id": "a:conv"}),
            httpx.Response(201, json={"id": "1"}),
        )

        await service.send("aad-1", "<p>hi</p>")

        self.assertEqual(BOT_FRAMEWORK_SCOPE, "https://api.botframework.com/.default")
        self.credential.get_token.assert_awaited_with(BOT_FRAMEWORK_SCOPE)


if __name__ == "__main__":
    unittest.main()
