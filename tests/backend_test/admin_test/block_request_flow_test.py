"""A block request end to end against a real database, through the shared
approval flow: raise, then approve, reject or withdraw, and read back the
person, the request, the events and who was told."""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy import select

from backend.admin.block_service import BlockService
from backend.admin.block_user_handler import BlockUserHandler
from backend.approval.approval_service import ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.event_entity import EventEntity
from backend.entity.notification_entity import NotificationEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.application_interview_repository import (
    ApplicationInterviewRepository,
)
from backend.repository.application_repository import ApplicationRepository
from backend.repository.application_submission_repository import (
    ApplicationSubmissionRepository,
)
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.repository.users_repository import UsersRepository
from backend.user_identity import notification_renderers  # noqa: F401 (registers)
from backend.user_identity import user_recipient_resolvers  # noqa: F401 (registers)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _user(first, *, super_admin=False):
    return UsersEntity(
        first_name=first,
        last_name=uuid.uuid4().hex[:8],
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        is_super_admin=super_admin,
        updated_timestamp=datetime.now(timezone.utc),
    )


class BlockRequestFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.raiser = _user("Ada")
        # Super admins hold every permission, USER_ADMIN among them.
        self.reviewer = _user("Rae", super_admin=True)
        self.operator = _user("Opa", super_admin=True)
        self.target = _user("Tom")
        await self.insert_entities([
            self.raiser,
            self.reviewer,
            self.operator,
            self.target,
        ])

        users = UsersRepository()
        perms = UserPermissionsRepository()
        applications = ApplicationRepository()
        submissions = ApplicationSubmissionRepository()
        interviews = ApplicationInterviewRepository()
        # The target has no applications, so no interview is ever cancelled.
        scheduling = MagicMock()
        approvals = ApprovalService(
            approval_request_repository=ApprovalRequestRepository(),
            user_permissions_repository=perms,
            users_repository=users,
            logger=MagicMock(),
        )
        approvals.register(
            BlockUserHandler(users, applications, submissions, interviews, scheduling)
        )
        self.service = BlockService(
            users,
            applications,
            submissions,
            interviews,
            scheduling,
            approvals,
            perms,
            logger=MagicMock(),
        )

    async def _raise(self, reason=None):
        return await self.service.raise_request(
            self.session,
            actor_id=self.raiser.user_id,
            user_id=self.target.user_id,
            reason=reason,
            reviewer_id=self.reviewer.user_id,
            raised_from="recruiting_application",
        )

    async def _request(self) -> ApprovalRequestEntity:
        return (
            await self.session.execute(
                select(ApprovalRequestEntity).where(
                    ApprovalRequestEntity.action == "block_user",
                    ApprovalRequestEntity.target_id == str(self.target.user_id),
                )
            )
        ).scalar_one()

    async def _events(self):
        return (
            await self.session.execute(
                select(
                    EventEntity.event_id, EventEntity.event_type, EventEntity.details
                )
                .where(
                    EventEntity.subject_type == "user",
                    EventEntity.subject_id == self.target.user_id,
                )
                .order_by(EventEntity.event_id)
            )
        ).all()

    async def _told(self, event_id) -> set[int]:
        rows = await self.session.execute(
            select(NotificationEntity.user_id).where(
                NotificationEntity.event_id == event_id
            )
        )
        return set(rows.scalars().all())

    async def test_raising_without_a_reason_then_approving_blocks_the_person(self):
        raised = await self._raise()
        self.assertIsNone(raised.reason)
        self.assertEqual(raised.status, "pending")
        self.assertEqual(raised.raised_from, "recruiting_application")
        self.assertEqual(raised.target_user_id, self.target.user_id)

        decided = await self.service.decide(
            self.session,
            actor_id=self.reviewer.user_id,
            request_id=raised.id,
            approved=True,
            note=None,
        )

        self.assertEqual(decided.status, "approved")
        await self.session.refresh(self.target)
        self.assertTrue(self.target.is_blocked)
        self.assertEqual(self.target.blocked_by, self.reviewer.user_id)
        self.assertIsNone(self.target.blocked_reason)
        events = await self._events()
        types = [e[1] for e in events]
        self.assertEqual(types[0], "user.block_requested")
        self.assertIn("user.blocked", types)
        self.assertEqual(types[-1], "user.block_request_decided")
        self.assertEqual(events[-1][2]["decision"], "approved")
        self.assertEqual(await self._told(events[0][0]), {self.reviewer.user_id})
        self.assertEqual(await self._told(events[-1][0]), {self.raiser.user_id})

    async def test_approving_carries_the_raisers_reason_onto_the_person(self):
        raised = await self._raise(reason="  Harassed an interviewer  ")

        await self.service.decide(
            self.session,
            actor_id=self.reviewer.user_id,
            request_id=raised.id,
            approved=True,
            note=None,
        )

        await self.session.refresh(self.target)
        self.assertEqual(self.target.blocked_reason, "Harassed an interviewer")

    async def test_a_rejection_needs_a_note_and_leaves_the_person_alone(self):
        raised = await self._raise(reason="Spam")

        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session,
                actor_id=self.reviewer.user_id,
                request_id=raised.id,
                approved=False,
                note="  ",
            )
        decided = await self.service.decide(
            self.session,
            actor_id=self.reviewer.user_id,
            request_id=raised.id,
            approved=False,
            note="Not enough evidence",
        )

        self.assertEqual(decided.status, "rejected")
        self.assertEqual(decided.decision_note, "Not enough evidence")
        await self.session.refresh(self.target)
        self.assertFalse(self.target.is_blocked)
        events = await self._events()
        self.assertEqual(events[-1][2]["comment"], "Not enough evidence")

    async def test_the_raiser_can_withdraw_and_the_reviewer_is_told(self):
        raised = await self._raise()

        withdrawn = await self.service.withdraw(
            self.session, actor_id=self.raiser.user_id, request_id=raised.id
        )

        self.assertEqual(withdrawn.status, "withdrawn")
        events = await self._events()
        self.assertEqual(events[-1][2]["decision"], "withdrawn")
        self.assertEqual(await self._told(events[-1][0]), {self.reviewer.user_id})
        # Nothing waits any more, so another request can be raised.
        again = await self._raise()
        self.assertEqual(again.status, "pending")

    async def test_a_second_request_while_one_waits_is_a_conflict(self):
        await self._raise()

        with self.assertRaises(ConflictError):
            await self._raise()

    async def test_blocking_directly_supersedes_the_waiting_request(self):
        await self._raise()

        await self.service.block_directly(
            self.session,
            actor_id=self.operator.user_id,
            user_id=self.target.user_id,
            reason="Seen enough",
        )

        request = await self._request()
        self.assertIs(request.status, ApprovalRequestStatus.SUPERSEDED)
        self.assertEqual(request.decided_by, self.operator.user_id)
        await self.session.refresh(self.target)
        self.assertEqual(self.target.blocked_reason, "Seen enough")
        self.assertEqual(
            await self.service.list_pending_for_reviewer(
                self.session, self.reviewer.user_id
            ),
            [],
        )

    async def test_the_pending_lists_show_the_request_to_both_sides(self):
        raised = await self._raise()

        for_reviewer = await self.service.list_pending_for_reviewer(
            self.session, self.reviewer.user_id
        )
        for_raiser = await self.service.list_pending_raised_by_actor(
            self.session, self.raiser.user_id
        )

        self.assertEqual([r.id for r in for_reviewer], [raised.id])
        self.assertEqual([r.id for r in for_raiser], [raised.id])
        self.assertEqual(for_reviewer[0].reviewer_name.split()[0], "Rae")


if __name__ == "__main__":
    unittest.main()
