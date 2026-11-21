import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.constants import MICROSOFT_AAD_ID_BY_LDAP_KEY
from backend.notification_management.notification_teams_service import (
    NotificationTeamsService,
    build_notification_teams_service,
)

_FOOTER = "<p>This is an automated message from Purrf.</p>"


class NotificationTeamsServiceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self, addresses, aad_id="aad-1"):
        """``addresses`` is a list of (email, otp_confirmed)."""
        self.user_emails_repository = AsyncMock()
        self.user_emails_repository.list_by_user_id.return_value = [
            SimpleNamespace(email=email, otp_confirmed=confirmed)
            for email, confirmed in addresses
        ]
        self.redis_client = MagicMock()
        self.redis_client.hget.return_value = aad_id
        self.compose = AsyncMock(
            return_value=(
                "A & B",
                '<p>x</p><p><a href="u">Open in Purrf</a></p>' + _FOOTER,
            )
        )
        self.teams = AsyncMock()
        return NotificationTeamsService(
            logger=MagicMock(),
            user_emails_repository=self.user_emails_repository,
            redis_client=self.redis_client,
            compose=self.compose,
            teams_message_service=self.teams,
        )

    async def test_send_posts_subject_and_body_without_footer(self):
        service = self._service([("alice@circlecat.org", True)])
        notification = SimpleNamespace(user_id=7, event_id=3, notification_id=11)
        session = object()

        await service.send(session, notification)

        self.user_emails_repository.list_by_user_id.assert_awaited_once_with(
            session, 7
        )
        self.redis_client.hget.assert_called_once_with(
            MICROSOFT_AAD_ID_BY_LDAP_KEY, "alice"
        )
        self.compose.assert_awaited_once_with(session, notification)
        self.teams.send.assert_awaited_once_with(
            "aad-1",
            '<p><strong>A &amp; B</strong></p><p>x</p><p><a href="u">Open in Purrf</a></p>',
        )

    async def test_send_reads_a_bytes_id(self):
        service = self._service([("alice@circlecat.org", True)], aad_id=b"aad-1")

        await service.send(object(), SimpleNamespace(user_id=7, notification_id=11))

        self.assertEqual(self.teams.send.await_args.args[0], "aad-1")

    async def test_send_skips_unconfirmed_company_address(self):
        service = self._service([("alice@circlecat.org", False)])

        await service.send(object(), SimpleNamespace(user_id=7, notification_id=11))

        self.redis_client.hget.assert_not_called()
        self.teams.send.assert_not_awaited()

    async def test_send_skips_external_user(self):
        service = self._service([("bob@gmail.com", True)])

        await service.send(object(), SimpleNamespace(user_id=7, notification_id=11))

        self.redis_client.hget.assert_not_called()
        self.teams.send.assert_not_awaited()

    async def test_send_skips_when_ldap_has_no_id(self):
        service = self._service([("alice@circlecat.org", True)], aad_id=None)

        await service.send(object(), SimpleNamespace(user_id=7, notification_id=11))

        self.compose.assert_not_awaited()
        self.teams.send.assert_not_awaited()


class BuildNotificationTeamsServiceTest(unittest.TestCase):
    def _build(self):
        return build_notification_teams_service(
            logger=MagicMock(),
            user_emails_repository=MagicMock(),
            redis_client=MagicMock(),
            compose=AsyncMock(),
        )

    def test_no_bot_id_means_no_teams(self):
        with patch.dict(os.environ, {"TEAMS_BOT_APP_ID": ""}):
            self.assertIsNone(self._build())

    @patch(
        "backend.notification_management.notification_teams_service.WorkloadIdentityCredential"
    )
    def test_bot_id_builds_the_service(self, credential):
        with patch.dict(
            os.environ, {"TEAMS_BOT_APP_ID": "app", "AZURE_TENANT_ID": "tenant"}
        ):
            service = self._build()

        credential.assert_called_once_with(client_id="app")
        sender = service.teams_message_service
        self.assertEqual(sender.app_id, "app")
        self.assertEqual(sender.tenant_id, "tenant")
        self.assertEqual(sender.http_client.timeout.read, 10.0)
        self.assertEqual(sender.http_client.timeout.connect, 10.0)


if __name__ == "__main__":
    unittest.main()
