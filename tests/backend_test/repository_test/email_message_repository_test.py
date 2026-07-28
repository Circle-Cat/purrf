import unittest
from datetime import datetime, timezone

from backend.common.communication_enums import ContextType, EmailDirection
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


if __name__ == "__main__":
    unittest.main()
