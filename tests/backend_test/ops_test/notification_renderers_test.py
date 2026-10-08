import unittest
from unittest.mock import Mock

from backend.common.ops_enums import OPS_ALERT_SUBJECT_TYPE, OpsEvent
from backend.entity.event_entity import EventEntity
from backend.notification_management import recipient_registry, render_registry
from backend.ops import notification_renderers  # noqa: F401 (registers)
from backend.ops import recipient_resolvers  # noqa: F401 (registers)


def _event(kind, detail="boom"):
    return EventEntity(
        subject_type=OPS_ALERT_SUBJECT_TYPE,
        subject_id=3,
        actor_id=None,
        event_type=OpsEvent.GMAIL_SYNC_ALERT,
        details={"kind": kind, "detail": detail, "mailbox": "purrf@example.com"},
    )


class GmailSyncAlertRenderTest(unittest.IsolatedAsyncioTestCase):
    async def _render(self, kind, detail="boom"):
        return await render_registry.render(Mock(), _event(kind, detail))

    async def test_each_kind_has_its_own_title(self):
        expected = {
            "watch_renewal_failed": "Gmail sync: watch renewal failed",
            "history_expired": "Gmail sync: history expired, full resync started",
            "sync_failed": "Gmail sync: sync failed",
            "unrouted_mail": "Gmail sync: new mail matched no Inbox alias",
        }
        for kind, title in expected.items():
            with self.subTest(kind=kind):
                subject, _ = await self._render(kind)
                self.assertEqual(subject, title)

    async def test_body_names_the_mailbox_and_the_detail(self):
        _, body = await self._render("sync_failed", "quota exceeded")

        self.assertIn("purrf@example.com", body)
        self.assertIn("quota exceeded", body)

    async def test_only_a_failed_renewal_warns_that_new_mail_stops(self):
        for kind, warns in {
            "watch_renewal_failed": True,
            "history_expired": False,
            "sync_failed": False,
        }.items():
            with self.subTest(kind=kind):
                _, body = await self._render(kind)
                self.assertEqual("new mail stops arriving" in body, warns)
                self.assertIn("[GmailSync]", body)

    async def test_detail_is_escaped(self):
        _, body = await self._render("sync_failed", "<script>alert(1)</script>")

        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>", body)

    async def test_the_event_both_notifies_and_renders(self):
        self.assertIn(OpsEvent.GMAIL_SYNC_ALERT, recipient_registry._RESOLVERS)
        self.assertIn(OpsEvent.GMAIL_SYNC_ALERT, render_registry._RENDERERS)


if __name__ == "__main__":
    unittest.main()
