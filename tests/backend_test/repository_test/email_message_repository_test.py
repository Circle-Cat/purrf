import unittest
from datetime import datetime, timezone

from backend.common.communication_enums import (
    ContextType,
    EmailDirection,
    InboundKind,
)
from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.email_message_entity import EmailMessageEntity
from backend.entity.email_thread_entity import EmailThreadEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.email_message_repository import EmailMessageRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    return UsersEntity(
        first_name="Cand",
        last_name="Idate",
        timezone="Asia/Shanghai",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestEmailMessageRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = EmailMessageRepository()

        self.user = _make_user()
        await self.insert_entities([self.user])

        self.thread = EmailThreadEntity(
            user_id=self.user.user_id,
            gmail_thread_id="gt-primary",
            subject="Hi",
            context_type=ContextType.APPLICATION,
            context_id=1,
        )
        self.other_thread = EmailThreadEntity(
            user_id=self.user.user_id,
            gmail_thread_id="gt-other",
            subject="Other",
            context_type=ContextType.APPLICATION,
            context_id=2,
        )
        await self.insert_entities([self.thread, self.other_thread])

    async def _add_message(self, thread, gmail_message_id):
        await self.insert_entities([
            EmailMessageEntity(
                thread_id=thread.thread_id,
                gmail_message_id=gmail_message_id,
                direction=EmailDirection.OUTBOUND,
            )
        ])

    async def test_create_keeps_kind_and_attachments(self):
        msg = await self.repo.create(
            self.session,
            thread_id=self.thread.thread_id,
            gmail_message_id="m-kind",
            direction=EmailDirection.INBOUND,
            inbound_kind=InboundKind.AUTO_REPLY,
            attachments=[
                {"name": "cv.pdf", "size": 1024, "gmailAttachmentId": "att-1"}
            ],
        )
        self.assertEqual(msg.inbound_kind, "auto_reply")
        self.assertEqual(msg.attachments[0]["name"], "cv.pdf")

    async def test_create_defaults_kind_and_attachments_to_none(self):
        msg = await self.repo.create(
            self.session,
            thread_id=self.thread.thread_id,
            gmail_message_id="m-plain",
            direction=EmailDirection.OUTBOUND,
        )
        self.assertIsNone(msg.inbound_kind)
        self.assertIsNone(msg.attachments)

    async def test_create_keeps_a_bounce_failed_recipients(self):
        bounce = await self.repo.create(
            self.session,
            thread_id=self.thread.thread_id,
            gmail_message_id="g-bounce",
            direction=EmailDirection.INBOUND,
            failed_recipients="a@x.com",
        )
        reply = await self.repo.create(
            self.session,
            thread_id=self.thread.thread_id,
            gmail_message_id="g-reply",
            direction=EmailDirection.INBOUND,
        )
        await self.session.refresh(bounce)
        await self.session.refresh(reply)

        self.assertEqual(bounce.failed_recipients, "a@x.com")
        self.assertIsNone(reply.failed_recipients)

    async def test_returns_empty_set_when_thread_has_no_messages(self):
        result = await self.repo.list_gmail_message_ids_by_thread(
            self.session, self.thread.thread_id
        )
        self.assertEqual(result, set())

    async def test_returns_every_stored_id_for_the_thread(self):
        await self._add_message(self.thread, "g1")
        await self._add_message(self.thread, "g2")
        result = await self.repo.list_gmail_message_ids_by_thread(
            self.session, self.thread.thread_id
        )
        self.assertEqual(result, {"g1", "g2"})

    async def test_excludes_ids_belonging_to_other_threads(self):
        await self._add_message(self.thread, "mine")
        await self._add_message(self.other_thread, "theirs")
        result = await self.repo.list_gmail_message_ids_by_thread(
            self.session, self.thread.thread_id
        )
        self.assertEqual(result, {"mine"})

    async def test_sender_ids_are_the_distinct_purrf_senders_of_one_thread(self):
        first, second, elsewhere = _make_user(), _make_user(), _make_user()
        await self.insert_entities([first, second, elsewhere])
        await self.insert_entities([
            EmailMessageEntity(
                thread_id=thread.thread_id,
                gmail_message_id=gmail_message_id,
                direction=direction,
                sent_by_user_id=None if sender is None else sender.user_id,
            )
            for thread, gmail_message_id, direction, sender in (
                (self.thread, "a1", EmailDirection.OUTBOUND, first),
                (self.thread, "a2", EmailDirection.OUTBOUND, second),
                (self.thread, "a3", EmailDirection.OUTBOUND, first),
                # Sent from the Gmail web UI: no sender recorded.
                (self.thread, "a4", EmailDirection.OUTBOUND, None),
                (self.thread, "a5", EmailDirection.INBOUND, None),
                (self.other_thread, "b1", EmailDirection.OUTBOUND, elsewhere),
            )
        ])

        result = await self.repo.list_sender_ids_by_thread(
            self.session, self.thread.thread_id
        )

        self.assertEqual(result, {first.user_id, second.user_id})


if __name__ == "__main__":
    unittest.main()
