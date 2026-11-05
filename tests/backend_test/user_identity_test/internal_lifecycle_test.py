import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.common.permissions import INTERNAL_EMPLOYEE_PERMISSIONS
from backend.user_identity.internal_lifecycle import absorb_internal_identity

_USER_ID = 7
_EMAIL = "ada@circlecat.org"


class TestAbsorbInternalIdentity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()
        self.permissions_repo = AsyncMock()
        self.permissions_repo.get_active_permission_names.return_value = [
            str(p) for p in INTERNAL_EMPLOYEE_PERMISSIONS
        ]
        self.emails_repo = AsyncMock()
        self.emails_repo.get_by_user_and_email.return_value = None
        self.users_repo = AsyncMock()
        self.onboarding = AsyncMock()
        self.logger = MagicMock()

    async def _absorb(self):
        await absorb_internal_identity(
            self.session,
            _USER_ID,
            _EMAIL,
            user_permissions_repository=self.permissions_repo,
            user_emails_repository=self.emails_repo,
            users_repository=self.users_repo,
            internal_onboarding_training_service=self.onboarding,
            logger=self.logger,
        )

    async def test_becoming_internal_assigns_the_employment_onboarding_training(self):
        """The third thing this moment means, alongside the flag and the
        permission bundle."""
        await self._absorb()

        self.onboarding.ensure_for_internal.assert_awaited_once_with(
            session=self.session, user_id=_USER_ID, email=_EMAIL
        )

    async def test_still_flags_the_user_internal(self):
        await self._absorb()

        self.users_repo.set_internal.assert_awaited_once_with(self.session, _USER_ID)

    async def test_does_not_commit(self):
        await self._absorb()

        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
