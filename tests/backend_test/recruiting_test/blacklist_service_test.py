import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from backend.recruiting.blacklist_service import BlacklistService
from backend.entity.users_entity import UsersEntity


class TestBlacklistService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users_repo = MagicMock()
        self.user_emails_repo = AsyncMock()
        self.user_emails_repo.get_contact_emails_by_user_ids.return_value = {}
        self.session = AsyncMock()
        self.service = BlacklistService(self.users_repo, self.user_emails_repo)

    def _user(self, user_id=1, first="A", last="B", email="a@b.com", reason="cheated"):
        u = UsersEntity(first_name=first, last_name=last)
        u.user_id = user_id
        u.is_blocked = True
        u.blocked_reason = reason
        u.blocked_at = datetime.now(timezone.utc)
        return u

    async def test_list_blacklist_maps_users_to_dtos(self):
        user = self._user()
        self.users_repo.list_blocked_users = AsyncMock(return_value=[user])
        # The entry's email comes from user_emails, not the legacy column.
        self.user_emails_repo.get_contact_emails_by_user_ids.return_value = {
            user.user_id: "a@b.com"
        }

        result = await self.service.list_blacklist(self.session)

        self.users_repo.list_blocked_users.assert_awaited_once_with(
            self.session, search=None
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].user_id, user.user_id)
        self.assertEqual(result[0].name, "A B")
        self.assertEqual(result[0].email, "a@b.com")
        self.assertEqual(result[0].reason, "cheated")

    async def test_list_blacklist_passes_search_through(self):
        self.users_repo.list_blocked_users = AsyncMock(return_value=[])
        await self.service.list_blacklist(self.session, search="token")
        self.users_repo.list_blocked_users.assert_awaited_once_with(
            self.session, search="token"
        )

    async def test_list_blacklist_empty(self):
        self.users_repo.list_blocked_users = AsyncMock(return_value=[])
        result = await self.service.list_blacklist(self.session)
        self.assertEqual(result, [])

    async def test_list_blacklist_reason_defaults_to_empty_string(self):
        user = self._user(reason=None)
        self.users_repo.list_blocked_users = AsyncMock(return_value=[user])
        result = await self.service.list_blacklist(self.session)
        self.assertEqual(result[0].reason, "")
        # No user_emails rows at all: the email falls back to empty.
        self.assertEqual(result[0].email, "")

    async def test_unblock_clears_and_commits(self):
        self.users_repo.clear_block = AsyncMock()
        await self.service.unblock(self.session, 42)
        self.users_repo.clear_block.assert_awaited_once_with(self.session, 42)
        self.session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
