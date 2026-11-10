from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock

from backend.notification_management.chat_subscription_check_service import (
    MONITOR_EVENT,
    ChatSubscriptionCheckService,
)

TEAMS_CHAT = "19:meeting_prod@thread.v2"
OTHER_TEAMS_CHAT = "19:other@thread.v2"
OUR_URL = "https://cf.example/purrf-prod-microsoft-chat"
TEST_ENV_URL = "https://test-cf.example/purrf-test-microsoft-chat"

SPACE = "spaces/AAAAprod"
OTHER_SPACE = "spaces/BBBBother"
OUR_TOPIC = "projects/p/topics/purrf-prod-chat-google-events"
TEST_ENV_TOPIC = "projects/p/topics/purrf-test-chat-google-events"

NOW = datetime.now(timezone.utc)
IN_TWO_DAYS = NOW + timedelta(days=2)
AN_HOUR_AGO = NOW - timedelta(hours=1)


def teams_sub(chat_id, url, expires):
    return SimpleNamespace(
        resource=f"/chats/{chat_id}/messages",
        notification_url=url,
        expiration_date_time=expires,
    )


def chat_sub(space, topic, state="ACTIVE", reason=None, expire="2026-11-11T00:00:00Z"):
    sub = {
        "targetResource": f"//chat.googleapis.com/{space}",
        "notificationEndpoint": {"pubsubTopic": topic},
        "state": state,
        "expireTime": expire,
    }
    if reason:
        sub["suspensionReason"] = reason
    return sub


class TestChatSubscriptionCheckService(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.microsoft_service = MagicMock()
        self.microsoft_service.list_all_subscriptions = AsyncMock(return_value=[])
        self.events_client = MagicMock()
        self.pages = [{"subscriptions": []}]
        self.list_calls = []

        def list_subscriptions(**kwargs):
            self.list_calls.append(kwargs)
            request = MagicMock()
            request.execute.return_value = self.pages[len(self.list_calls) - 1]
            return request

        self.events_client.subscriptions.return_value.list.side_effect = (
            list_subscriptions
        )
        self.retry_utils = MagicMock()
        self.retry_utils.get_retry_on_transient.side_effect = lambda fn: fn()

    def service(self, teams=(TEAMS_CHAT,), spaces=(SPACE,)):
        return ChatSubscriptionCheckService(
            logger=self.logger,
            microsoft_service=self.microsoft_service,
            google_workspaceevents_client=self.events_client,
            retry_utils=self.retry_utils,
            expected_teams_chats=list(teams),
            expected_google_chat_spaces=list(spaces),
            teams_notification_url=OUR_URL,
            google_chat_events_topic=OUR_TOPIC,
        )

    def statuses(self, result, provider):
        return {r["target"]: r["status"] for r in result[provider]}

    async def test_teams_ok_when_our_subscription_is_live(self):
        self.microsoft_service.list_all_subscriptions.return_value = [
            teams_sub(TEAMS_CHAT, OUR_URL, IN_TWO_DAYS)
        ]

        result = await self.service(spaces=()).check()

        self.assertEqual(
            result["teams"],
            [
                {
                    "target": TEAMS_CHAT,
                    "status": "ok",
                    "expiresAt": IN_TWO_DAYS.isoformat(),
                }
            ],
        )

    async def test_teams_missing_when_only_another_chat_is_subscribed(self):
        self.microsoft_service.list_all_subscriptions.return_value = [
            teams_sub(OTHER_TEAMS_CHAT, OUR_URL, IN_TWO_DAYS)
        ]

        result = await self.service(spaces=()).check()

        self.assertEqual(self.statuses(result, "teams"), {TEAMS_CHAT: "missing"})

    async def test_teams_missing_when_another_environment_holds_the_chat(self):
        self.microsoft_service.list_all_subscriptions.return_value = [
            teams_sub(TEAMS_CHAT, TEST_ENV_URL, IN_TWO_DAYS)
        ]

        result = await self.service(spaces=()).check()

        self.assertEqual(self.statuses(result, "teams"), {TEAMS_CHAT: "missing"})

    async def test_teams_expired_when_past_its_expiration(self):
        self.microsoft_service.list_all_subscriptions.return_value = [
            teams_sub(TEAMS_CHAT, OUR_URL, AN_HOUR_AGO)
        ]

        result = await self.service(spaces=()).check()

        self.assertEqual(self.statuses(result, "teams"), {TEAMS_CHAT: "expired"})

    async def test_google_chat_ok_when_active_on_our_topic(self):
        self.pages = [{"subscriptions": [chat_sub(SPACE, OUR_TOPIC)]}]

        result = await self.service(teams=()).check()

        self.assertEqual(
            result["googleChat"],
            [{"target": SPACE, "status": "ok", "expiresAt": "2026-11-11T00:00:00Z"}],
        )

    async def test_google_chat_reports_suspended_state_and_reason(self):
        self.pages = [
            {
                "subscriptions": [
                    chat_sub(
                        SPACE,
                        OUR_TOPIC,
                        state="SUSPENDED",
                        reason="USER_AUTHORIZATION_FAILURE",
                    )
                ]
            }
        ]

        result = await self.service(teams=()).check()

        self.assertEqual(
            self.statuses(result, "googleChat"),
            {SPACE: "suspended_user_authorization_failure"},
        )

    async def test_google_chat_missing_when_only_another_topic_or_space(self):
        self.pages = [
            {
                "subscriptions": [
                    chat_sub(SPACE, TEST_ENV_TOPIC),
                    chat_sub(OTHER_SPACE, OUR_TOPIC),
                ]
            }
        ]

        result = await self.service(teams=()).check()

        self.assertEqual(self.statuses(result, "googleChat"), {SPACE: "missing"})

    async def test_google_chat_reads_every_page(self):
        self.pages = [
            {
                "subscriptions": [chat_sub(OTHER_SPACE, OUR_TOPIC)],
                "nextPageToken": "t2",
            },
            {"subscriptions": [chat_sub(SPACE, OUR_TOPIC)]},
        ]

        result = await self.service(teams=()).check()

        self.assertEqual(self.statuses(result, "googleChat"), {SPACE: "ok"})
        self.assertEqual([c["pageToken"] for c in self.list_calls], [None, "t2"])
        self.assertTrue(
            all(c["filter"].startswith("event_types:") for c in self.list_calls)
        )

    async def test_nothing_expected_calls_no_api(self):
        result = await self.service(teams=(), spaces=()).check()

        self.assertEqual(result, {"teams": [], "googleChat": []})
        self.microsoft_service.list_all_subscriptions.assert_not_called()
        self.events_client.subscriptions.assert_not_called()
        self.logger.info.assert_not_called()
        self.logger.warning.assert_not_called()

    async def test_api_failure_propagates_without_logging_a_status(self):
        self.microsoft_service.list_all_subscriptions.side_effect = RuntimeError(
            "graph down"
        )

        with self.assertRaises(RuntimeError):
            await self.service().check()

        self.logger.warning.assert_not_called()

    async def test_logs_one_structured_line_per_target(self):
        self.microsoft_service.list_all_subscriptions.return_value = [
            teams_sub(TEAMS_CHAT, OUR_URL, IN_TWO_DAYS)
        ]
        self.pages = [{"subscriptions": []}]

        await self.service().check()

        self.logger.info.assert_called_once()
        self.assertEqual(
            self.logger.info.call_args.kwargs["extra"],
            {
                "monitor_event": MONITOR_EVENT,
                "provider": "teams",
                "target": TEAMS_CHAT,
                "status": "ok",
                "expires_at": IN_TWO_DAYS.isoformat(),
            },
        )
        self.logger.warning.assert_called_once()
        self.assertEqual(
            self.logger.warning.call_args.kwargs["extra"],
            {
                "monitor_event": MONITOR_EVENT,
                "provider": "google_chat",
                "target": SPACE,
                "status": "missing",
                "expires_at": None,
            },
        )


if __name__ == "__main__":
    main()
