import unittest

from backend.common.communication_enums import ContextType
from backend.entity.email_thread_entity import EmailThreadEntity  # noqa: F401
from backend.entity.users_entity import UsersEntity  # noqa: F401
from backend.repository.email_thread_repository import EmailThreadRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestEmailThreadRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = EmailThreadRepository()

    async def test_create_without_a_user(self):
        thread = await self.repo.create(
            self.session,
            user_id=None,
            gmail_thread_id="g-1",
            subject="Hi",
            context_type=ContextType.INQUIRIES_INBOX,
            context_id=None,
        )
        self.assertIsNone(thread.user_id)
        self.assertIsNone(thread.archived_at)
        self.assertIsNone(thread.archived_by_user_id)


if __name__ == "__main__":
    unittest.main()
