import unittest
import uuid
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.users_entity import UsersEntity
from backend.repository.user_permissions_repository import UserPermissionsRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestUserPermissionsRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = UserPermissionsRepository()
        # user_permissions.user_id / granted_by / revoked_by are FKs to users,
        # so insert real users first and grant against their real ids.
        self.u1 = self._make_user("u1")
        self.u2 = self._make_user("u2")
        self.admin = self._make_user("admin")
        await self.insert_entities([self.u1, self.u2, self.admin])

    def _make_user(
        self, tag, *, is_active=True, is_blocked=False, is_super_admin=False
    ):
        return UsersEntity(
            first_name=tag,
            last_name="T",
            timezone="UTC",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=is_active,
            is_blocked=is_blocked,
            is_super_admin=is_super_admin,
            updated_timestamp=datetime.now(timezone.utc),
        )

    async def test_get_grants_for_user_includes_and_excludes_revoked(self):
        await self.repo.grant(
            self.session,
            self.u1.user_id,
            ["a.read", "b.read"],
            "admin",
            granted_by=self.admin.user_id,
        )
        await self.repo.revoke(
            self.session, self.u1.user_id, ["a.read"], revoked_by=self.admin.user_id
        )

        active = await self.repo.get_grants_for_user(
            self.session, self.u1.user_id, include_revoked=False
        )
        self.assertEqual({g.permission_name for g in active}, {"b.read"})

        full = await self.repo.get_grants_for_user(
            self.session, self.u1.user_id, include_revoked=True
        )
        self.assertEqual(len(full), 2)

    async def test_get_active_users_with_permission_dedups_and_skips_inactive(self):
        perm = f"approve.{uuid.uuid4().hex[:8]}"
        # u1 holds two active grants -> must appear exactly once.
        await self.repo.grant(self.session, self.u1.user_id, [perm], "admin")
        await self.repo.grant(self.session, self.u1.user_id, [perm], "system_internal")
        # u2 holds it but is inactive -> excluded (u2 is not a super-admin).
        await self.repo.grant(self.session, self.u2.user_id, [perm], "admin")
        self.u2.is_active = False
        await self.session.flush()
        # admin's only grant is revoked -> excluded (admin is not a super-admin).
        await self.repo.grant(self.session, self.admin.user_id, [perm], "admin")
        await self.repo.revoke(self.session, self.admin.user_id, [perm])

        users = await self.repo.get_active_users_with_permission(self.session, perm)
        user_ids = {u.user_id for u in users}

        # u1 must be present and deduplicated.
        self.assertIn(self.u1.user_id, user_ids)
        self.assertEqual(sum(1 for u in users if u.user_id == self.u1.user_id), 1)
        # inactive u2 and revoked-only admin must not appear via explicit grants.
        self.assertNotIn(self.u2.user_id, user_ids)
        self.assertNotIn(self.admin.user_id, user_ids)

    async def test_get_active_users_with_permission_includes_active_super_admin(self):
        """An active super-admin with no explicit grant must be included; an
        inactive super-admin must not."""
        perm = f"approve.{uuid.uuid4().hex[:8]}"
        # Create an active super-admin with no explicit grant for this perm.
        active_sa = self._make_user("sa_active")
        active_sa.is_super_admin = True
        # Create an inactive super-admin (also no explicit grant) -> must be excluded.
        inactive_sa = self._make_user("sa_inactive")
        inactive_sa.is_super_admin = True
        inactive_sa.is_active = False
        await self.insert_entities([active_sa, inactive_sa])

        users = await self.repo.get_active_users_with_permission(self.session, perm)
        user_ids = {u.user_id for u in users}

        self.assertIn(active_sa.user_id, user_ids)
        self.assertNotIn(inactive_sa.user_id, user_ids)

    async def test_blocked_holder_is_excluded(self):
        """A blocked holder can never sign in, so offering them as a pick
        creates a dead letter: the job/request lands on someone unreachable."""
        perm = f"approve.{uuid.uuid4().hex[:8]}"
        blocked = self._make_user("blocked", is_active=True, is_blocked=True)
        await self.insert_entities([blocked])
        await self.repo.grant(self.session, blocked.user_id, [perm], "admin")

        users = await self.repo.get_active_users_with_permission(self.session, perm)

        self.assertNotIn(blocked.user_id, {u.user_id for u in users})

    async def test_blocked_super_admin_is_excluded(self):
        """The super-admin branch is an OR, so it must be gated too."""
        perm = f"approve.{uuid.uuid4().hex[:8]}"
        blocked_sa = self._make_user(
            "blocked_sa", is_active=True, is_blocked=True, is_super_admin=True
        )
        await self.insert_entities([blocked_sa])

        users = await self.repo.get_active_users_with_permission(self.session, perm)

        self.assertNotIn(blocked_sa.user_id, {u.user_id for u in users})

    async def test_active_unblocked_holder_still_returned(self):
        """Non-regression: the existing behaviour is unchanged for clean rows."""
        perm = f"approve.{uuid.uuid4().hex[:8]}"
        clean = self._make_user("clean", is_active=True, is_blocked=False)
        await self.insert_entities([clean])
        await self.repo.grant(self.session, clean.user_id, [perm], "admin")

        users = await self.repo.get_active_users_with_permission(self.session, perm)

        self.assertIn(clean.user_id, {u.user_id for u in users})

    async def test_deactivated_holder_still_excluded(self):
        """Non-regression: is_active filtering must not be lost."""
        perm = f"approve.{uuid.uuid4().hex[:8]}"
        gone = self._make_user("gone", is_active=False, is_blocked=False)
        await self.insert_entities([gone])
        await self.repo.grant(self.session, gone.user_id, [perm], "admin")

        users = await self.repo.get_active_users_with_permission(self.session, perm)

        self.assertNotIn(gone.user_id, {u.user_id for u in users})

    async def test_list_audit_filters_and_paginates(self):
        await self.repo.grant(
            self.session, self.u1.user_id, ["a.read", "b.read", "c.read"], "admin"
        )
        await self.repo.revoke(self.session, self.u1.user_id, ["a.read"])

        revoked, total = await self.repo.list_audit(
            self.session, user_id=self.u1.user_id, action="revoked"
        )
        self.assertEqual(total, 1)
        self.assertEqual(revoked[0].permission_name, "a.read")

        page, total_all = await self.repo.list_audit(
            self.session, user_id=self.u1.user_id, limit=2, offset=0
        )
        self.assertEqual(total_all, 3)
        self.assertEqual(len(page), 2)


if __name__ == "__main__":
    unittest.main()
