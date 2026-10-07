"""A job posting review end to end against a real database, through the
shared approval flow: submit, then approve, reject or withdraw, and read back
the posting, the request and the events."""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy import select

from backend.approval.approval_service import ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.recruiting import notification_renderers  # noqa: F401 (registers)
from backend.recruiting import recipient_resolvers  # noqa: F401 (registers)
from backend.recruiting.job_review_handler import JobReviewHandler
from backend.recruiting.job_service import JobService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from backend.repository.event_repository import EventRepository
from backend.repository.job_repository import JobRepository
from backend.repository.notification_repository import NotificationRepository
from backend.repository.user_emails_repository import UserEmailsRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.repository.users_repository import UsersRepository
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


class JobReviewFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.submitter = _user("Ada")
        # Super admins hold every permission: the reviewer can approve and
        # the owner can advance applications.
        self.reviewer = _user("Rae", super_admin=True)
        self.owner = _user("Olu", super_admin=True)
        await self.insert_entities([self.submitter, self.reviewer, self.owner])
        self.job = JobEntity(
            kind=JobKind.EMPLOYMENT,
            title="Backend Engineer",
            status=JobStatus.DRAFT,
            pipeline_config={
                "stages": [{"key": "screening", "defaultAssigneeId": None}],
                "ownerIds": [self.owner.user_id],
            },
        )
        await self.insert_entities([self.job])

        perms = UserPermissionsRepository()
        job_repository = JobRepository()
        approvals = ApprovalService(
            approval_request_repository=ApprovalRequestRepository(),
            user_permissions_repository=perms,
            users_repository=UsersRepository(),
            logger=MagicMock(),
            handlers=[
                JobReviewHandler(
                    job_repository=job_repository, user_permissions_repository=perms
                )
            ],
        )
        self.service = JobService(
            job_repository,
            RecruitingMapper(),
            perms,
            NotificationRepository(),
            UsersRepository(),
            UserEmailsRepository(),
            EventRepository(),
            approval_service=approvals,
        )

    async def _submit(self, message="Ready to go live"):
        return await self.service.submit_for_review(
            self.session,
            self.job.job_id,
            reviewer_id=self.reviewer.user_id,
            submitted_by=self.submitter.user_id,
            message=message,
        )

    async def _request(self) -> ApprovalRequestEntity:
        return (
            await self.session.execute(
                select(ApprovalRequestEntity).where(
                    ApprovalRequestEntity.target_id == str(self.job.job_id)
                )
            )
        ).scalar_one()

    async def _events(self):
        return (
            await self.session.execute(
                select(EventEntity.event_type, EventEntity.details)
                .where(
                    EventEntity.subject_type == "job",
                    EventEntity.subject_id == self.job.job_id,
                )
                .order_by(EventEntity.event_id)
            )
        ).all()

    async def test_submitting_then_approving_publishes_the_posting(self):
        submitted = await self._submit()
        self.assertEqual(submitted.status, JobStatus.PENDING_REVIEW)
        request = await self._request()
        self.assertEqual(request.payload, {"kind": "initial"})

        queue = await self.service.list_reviews_for_reviewer(
            self.session, self.reviewer.user_id
        )
        self.assertEqual(
            [(r.review_id, r.job_title, r.submit_message) for r in queue],
            [(request.request_id, "Backend Engineer", "Ready to go live")],
        )

        approved = await self.service.approve(
            self.session, request.request_id, self.reviewer.user_id
        )

        self.assertEqual(approved.status, JobStatus.PUBLISHED)
        events = await self._events()
        self.assertEqual(
            [(t, d.get("decision")) for t, d in events],
            [
                ("recruiting.review_opened", None),
                ("recruiting.review_decided", "approved"),
            ],
        )
        self.assertEqual(events[0][1]["kind"], "initial")
        self.assertEqual(events[0][1]["reviewId"], request.request_id)
        self.assertEqual(events[0][1]["message"], "Ready to go live")

    async def test_a_rejection_sends_it_back_and_shows_why(self):
        await self._submit()
        request = await self._request()

        rejected = await self.service.reject(
            self.session,
            request.request_id,
            "Add a salary range",
            self.reviewer.user_id,
        )

        self.assertEqual(rejected.status, JobStatus.DRAFT)
        job = await self.service.get_job(self.session, self.job.job_id)
        self.assertEqual(
            (job.last_reject_comment, job.last_reject_kind),
            ("Add a salary range", "initial"),
        )
        self.assertIsNone(job.reviewer_id)
        events = await self._events()
        self.assertEqual(events[-1][1]["comment"], "Add a salary range")

    async def test_the_submitter_can_withdraw_and_the_posting_goes_back(self):
        await self._submit(message=None)

        withdrawn = await self.service.withdraw_review(
            self.session, self.job.job_id, acting_user_id=self.submitter.user_id
        )

        self.assertEqual(withdrawn.status, JobStatus.DRAFT)
        request = await self._request()
        self.assertIs(request.status, ApprovalRequestStatus.WITHDRAWN)
        self.assertIsNone(request.reason)
        events = await self._events()
        self.assertEqual(events[-1][1]["decision"], "withdrawn")

    async def test_a_second_submission_while_one_waits_is_refused(self):
        # The posting's pending status refuses it first; the one-pending
        # index is what holds under a race.
        await self._submit()

        with self.assertRaises(ValueError):
            await self.service.request_close(
                self.session,
                self.job.job_id,
                reviewer_id=self.reviewer.user_id,
                submitted_by=self.submitter.user_id,
                message=None,
            )

    async def test_get_job_names_who_the_open_review_waits_on(self):
        await self._submit()

        job = await self.service.get_job(self.session, self.job.job_id)
        listed = {j.id: j for j in await self.service.list_all_jobs(self.session)}

        self.assertEqual(
            (job.reviewer_id, job.submitted_by, job.submit_message),
            (self.reviewer.user_id, self.submitter.user_id, "Ready to go live"),
        )
        self.assertEqual(listed[self.job.job_id].reviewer_id, self.reviewer.user_id)


if __name__ == "__main__":
    unittest.main()
