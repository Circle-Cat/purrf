import unittest
from unittest.mock import Mock

from backend.common.communication_enums import InboxService
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.communication import notification_renderers  # noqa: F401 (registers)
from backend.communication import recipient_resolvers  # noqa: F401 (registers)
from backend.entity.event_entity import EventEntity
from backend.notification_management import recipient_registry, render_registry


def _event(event_type, details):
    return EventEntity(
        subject_type=INBOX_SUBJECT_TYPE,
        subject_id=77,
        actor_id=None,
        event_type=event_type,
        details=details,
    )


class NeedsReplyRenderTest(unittest.IsolatedAsyncioTestCase):
    async def _render(self, **details):
        base = {
            "service": InboxService.MENTORSHIP,
            "subject": "A question",
            "from": "asker@ext.com",
        }
        return await render_registry.render(
            Mock(), _event(InboxEvent.NEEDS_REPLY, {**base, **details})
        )

    async def test_subject_and_body(self):
        subject, body = await self._render()

        self.assertEqual(subject, "New email needs a reply")
        self.assertTrue(
            body.startswith(
                "<p>A new email in the Mentorship inbox needs a reply: "
                "“A question” from asker@ext.com.</p>"
                "<p>Open Inbox in Purrf to read and reply.</p>"
            )
        )
        self.assertNotIn("href", body)

    async def test_each_service_is_named(self):
        for service, name in {
            InboxService.RECRUITING: "Recruiting",
            InboxService.INQUIRIES: "Inquiries",
        }.items():
            with self.subTest(service=service):
                _, body = await self._render(service=service)
                self.assertIn(f"in the {name} inbox", body)

    async def test_user_values_are_escaped(self):
        _, body = await self._render(
            subject="<script>alert(1)</script>", **{"from": '"Eve" <eve@x.com>'}
        )

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)
        self.assertNotIn("<script>", body)
        self.assertIn("&quot;Eve&quot; &lt;eve@x.com&gt;", body)


class BouncedRenderTest(unittest.IsolatedAsyncioTestCase):
    async def test_subject_body_and_escaping(self):
        subject, body = await render_registry.render(
            Mock(),
            _event(
                InboxEvent.BOUNCED,
                {
                    "bouncedTo": "<b>asker@ext.com</b>",
                    "subject": "<script>x</script>",
                    "senderUserId": 9,
                },
            ),
        )

        self.assertEqual(subject, "Your email was not delivered")
        self.assertTrue(
            body.startswith(
                "<p>Your email to &lt;b&gt;asker@ext.com&lt;/b&gt; about "
                "“&lt;script&gt;x&lt;/script&gt;” was not delivered.</p>"
                "<p>Open Inbox in Purrf to see the thread.</p>"
            )
        )
        self.assertNotIn("<script>", body)


class PairingTest(unittest.TestCase):
    def test_every_notifying_inbox_event_renders_and_vice_versa(self):
        inbox = {e.value for e in InboxEvent}
        resolved = {t for t in recipient_registry._RESOLVERS if t in inbox}
        rendered = {t for t in render_registry._RENDERERS if t in inbox}

        self.assertEqual(resolved, rendered)
        self.assertEqual(resolved, {InboxEvent.NEEDS_REPLY, InboxEvent.BOUNCED})


if __name__ == "__main__":
    unittest.main()
