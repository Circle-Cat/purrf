import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import (
    ApplicationStage,
    JobKind,
    JobReviewKind,
    JobStatus,
    RecruitingEvent,
)
from backend.entity.application_assignment_entity import (
    ApplicationAssignmentEntity,
)
from backend.entity.application_comment_entity import ApplicationCommentEntity
from backend.entity.application_comment_mention_entity import (
    ApplicationCommentMentionEntity,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.job_review_entity import JobReviewEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management import recipient_registry
from backend.notification_management.recipient_registry import resolve_recipients
from backend.recruiting import recipient_resolvers  # noqa: F401  (registers)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user(is_active: bool = True) -> UsersEntity:
    """Build a minimal, unsaved user row satisfying every NOT NULL column.

    Args:
        is_active (bool): Whether the user is still with the org. Offboarded
            users must not be resolved as recipients.

    Returns:
        UsersEntity: The unsaved user.
    """
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=is_active,
        updated_timestamp=datetime.now(timezone.utc),
    )


def _event(
    event_type: str,
    subject_type: str,
    subject_id: int,
    details: dict | None = None,
) -> EventEntity:
    """Build an unsaved event for feeding straight into ``resolve_recipients``.

    Args:
        event_type (str): Domain-prefixed type, e.g. ``"recruiting.reassigned"``.
        subject_type (str): What the event is about, e.g. ``"application"``.
        subject_id (int): Primary key of that subject.
        details (dict | None): Extra payload for rendering. Defaults to ``{}``.

    Returns:
        EventEntity: An event with actor_id=0 and no details, unsaved.
    """
    return EventEntity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=0,
        event_type=event_type,
        details=details or {},
    )


class RecipientResolversTest(BaseRepositoryTestLib):
    """DB-backed tests for the recruiting event_type -> recipients wiring.

    Subclasses ``BaseRepositoryTestLib``, like every other DB-backed test in
    this codebase, so each test runs in its own rolled-back transaction and
    the shared CI database never accumulates rows.
    """

    async def _make_job(self, owner_ids: list[int]) -> JobEntity:
        """Create and insert a job whose pipeline_config carries the given owners.

        Args:
            owner_ids (list[int]): Owner user ids to store under ``ownerIds``.

        Returns:
            JobEntity: The inserted job, with ``job_id`` populated.
        """
        job = JobEntity(
            kind=JobKind.EMPLOYMENT,
            title="T",
            status=JobStatus.PUBLISHED,
            pipeline_config={"ownerIds": owner_ids},
        )
        await self.insert_entities([job])
        return job

    async def _make_application(
        self, job_id: int, candidate: UsersEntity
    ) -> ApplicationEntity:
        """Create and insert an application for ``candidate`` against ``job_id``.

        Args:
            job_id (int): The job being applied to.
            candidate (UsersEntity): The applicant. Never a recipient.

        Returns:
            ApplicationEntity: The inserted application, with
                ``application_id`` populated.
        """
        application = ApplicationEntity(
            job_id=job_id,
            user_id=candidate.user_id,
            stage=ApplicationStage.APPLIED,
        )
        await self.insert_entities([application])
        return application

    async def _make_assignment(
        self,
        application_id: int,
        assignee: UsersEntity,
        assigned_by: UsersEntity,
        stage: ApplicationStage = ApplicationStage.APPLIED,
        round: int = 1,
    ) -> ApplicationAssignmentEntity:
        """Create and insert an assignment row for one stage and round.

        Args:
            application_id (int): The application being assigned.
            assignee (UsersEntity): Who is responsible for that stage/round.
            assigned_by (UsersEntity): Who made the assignment.
            stage (ApplicationStage): Stage the assignment covers.
            round (int): Round within that stage.

        Returns:
            ApplicationAssignmentEntity: The inserted assignment row.
        """
        assignment = ApplicationAssignmentEntity(
            application_id=application_id,
            stage=stage,
            round=round,
            assignee_id=assignee.user_id,
            assigned_by=assigned_by.user_id,
        )
        await self.insert_entities([assignment])
        return assignment

    async def _make_review(
        self,
        job_id: int,
        submitted_by: UsersEntity,
        reviewer: UsersEntity,
    ) -> JobReviewEntity:
        """Create and insert a pending initial review of a job.

        Args:
            job_id (int): The job under review.
            submitted_by (UsersEntity): Who sent it up and waits on the verdict.
            reviewer (UsersEntity): Who can decide it.

        Returns:
            JobReviewEntity: The inserted review, with ``review_id`` populated.
        """
        review = JobReviewEntity(
            job_id=job_id,
            submitted_by=submitted_by.user_id,
            reviewer_id=reviewer.user_id,
            kind=JobReviewKind.INITIAL,
        )
        await self.insert_entities([review])
        return review

    async def _make_comment_mentioning(
        self, application_id: int, author: UsersEntity, mentioned: list[UsersEntity]
    ) -> ApplicationCommentEntity:
        """Create and insert a comment plus one mention row per mentioned user.

        Args:
            application_id (int): The application commented on.
            author (UsersEntity): Who wrote the comment.
            mentioned (list[UsersEntity]): Who the comment names.

        Returns:
            ApplicationCommentEntity: The inserted comment, with ``comment_id``
                populated.
        """
        comment = ApplicationCommentEntity(
            application_id=application_id,
            author_id=author.user_id,
            body="see this",
        )
        await self.insert_entities([comment])
        await self.insert_entities([
            ApplicationCommentMentionEntity(
                comment_id=comment.comment_id, mentioned_user_id=user.user_id
            )
            for user in mentioned
        ])
        return comment

    async def test_application_submitted_goes_to_the_job_owners(self):
        owner_a, owner_b, candidate = _make_user(), _make_user(), _make_user()
        await self.insert_entities([owner_a, owner_b, candidate])
        job = await self._make_job([owner_a.user_id, owner_b.user_id])
        application = await self._make_application(job.job_id, candidate)
        event = _event(
            "recruiting.application_submitted",
            "application",
            application.application_id,
        )

        self.assertEqual(
            await resolve_recipients(self.session, event),
            {owner_a.user_id, owner_b.user_id},
        )

    async def test_reassigned_reaches_the_assignee_written_moments_ago(self):
        """Guards the ordering rule: record_event must run after the business write."""
        owner, candidate, assignee = _make_user(), _make_user(), _make_user()
        await self.insert_entities([owner, candidate, assignee])
        job = await self._make_job([owner.user_id])
        application = await self._make_application(job.job_id, candidate)
        await self._make_assignment(application.application_id, assignee, owner)
        event = _event(
            "recruiting.reassigned", "application", application.application_id
        )

        self.assertEqual(
            await resolve_recipients(self.session, event),
            {owner.user_id, assignee.user_id},
        )

    async def test_the_candidate_is_never_a_recipient(self):
        owner, candidate = _make_user(), _make_user()
        await self.insert_entities([owner, candidate])
        job = await self._make_job([owner.user_id])
        application = await self._make_application(job.job_id, candidate)
        event = _event(
            "recruiting.stage_changed", "application", application.application_id
        )

        self.assertNotIn(
            candidate.user_id, await resolve_recipients(self.session, event)
        )

    async def test_legacy_scalar_owner_id_is_still_resolved(self):
        """Guards the legacy ``pipeline_config`` shape.

        Configs saved before multi-owner store a scalar ``ownerId`` instead
        of an ``ownerIds`` list. ``normalized_owner_ids`` is the only thing
        standing between this and a silent empty recipient set for every job
        created before that migration.
        """
        owner, candidate = _make_user(), _make_user()
        await self.insert_entities([owner, candidate])
        job = JobEntity(
            kind=JobKind.EMPLOYMENT,
            title="T",
            status=JobStatus.PUBLISHED,
            pipeline_config={"ownerId": owner.user_id},
        )
        await self.insert_entities([job])
        application = await self._make_application(job.job_id, candidate)
        event = _event(
            "recruiting.application_submitted",
            "application",
            application.application_id,
        )

        self.assertEqual(await resolve_recipients(self.session, event), {owner.user_id})

    async def test_only_the_current_stage_and_round_assignee_is_reached(self):
        """Assignment rows accumulate; interviewers from finished rounds are done.

        Reassignment overwrites only within one (application, stage, round),
        so an unscoped read keeps every earlier screener as a recipient for
        the rest of the application's life.
        """
        owner, candidate = _make_user(), _make_user()
        past, current = _make_user(), _make_user()
        await self.insert_entities([owner, candidate, past, current])
        job = await self._make_job([owner.user_id])
        application = await self._make_application(job.job_id, candidate)
        await self._make_assignment(application.application_id, past, owner, round=1)
        await self._make_assignment(application.application_id, current, owner, round=3)
        application.current_round = 3
        await self.session.flush()
        event = _event(
            "recruiting.interview_cancelled", "application", application.application_id
        )

        self.assertEqual(
            await resolve_recipients(self.session, event),
            {owner.user_id, current.user_id},
        )

    async def test_an_offboarded_assignee_is_not_reached(self):
        """A left assignee whose row is still there must stop accruing notifications."""
        owner, candidate = _make_user(), _make_user()
        gone = _make_user(is_active=False)
        await self.insert_entities([owner, candidate, gone])
        job = await self._make_job([owner.user_id])
        application = await self._make_application(job.job_id, candidate)
        await self._make_assignment(application.application_id, gone, owner)
        event = _event(
            "recruiting.reassigned", "application", application.application_id
        )

        self.assertEqual(await resolve_recipients(self.session, event), {owner.user_id})

    async def test_auto_assigned_reaches_only_the_assignee(self):
        """Owners hear about a submission once, from application_submitted."""
        owner, candidate, assignee = _make_user(), _make_user(), _make_user()
        await self.insert_entities([owner, candidate, assignee])
        job = await self._make_job([owner.user_id])
        application = await self._make_application(job.job_id, candidate)
        await self._make_assignment(application.application_id, assignee, owner)
        event = _event(
            "recruiting.auto_assigned", "application", application.application_id
        )

        self.assertEqual(
            await resolve_recipients(self.session, event), {assignee.user_id}
        )

    async def test_review_opened_reaches_the_reviewer_on_the_review(self):
        """The review row is the truth; the event carries only its id."""
        submitter, reviewer = _make_user(), _make_user()
        await self.insert_entities([submitter, reviewer])
        job = await self._make_job([])
        review = await self._make_review(job.job_id, submitter, reviewer)
        event = _event(
            "recruiting.review_opened",
            "job",
            job.job_id,
            details={"reviewId": review.review_id},
        )

        self.assertEqual(
            await resolve_recipients(self.session, event), {reviewer.user_id}
        )

    async def test_review_decided_reaches_the_submitter_not_the_owners(self):
        """Submitting is gated on permission, not ownership.

        The owner set here deliberately excludes the submitter, so a resolver
        reading ``pipeline_config`` would reach the wrong people.
        """
        owner, submitter, reviewer = _make_user(), _make_user(), _make_user()
        await self.insert_entities([owner, submitter, reviewer])
        job = await self._make_job([owner.user_id])
        review = await self._make_review(job.job_id, submitter, reviewer)
        event = _event(
            "recruiting.review_decided",
            "job",
            job.job_id,
            details={"reviewId": review.review_id},
        )

        self.assertEqual(
            await resolve_recipients(self.session, event), {submitter.user_id}
        )

    async def test_mentioned_reaches_the_users_named_in_the_comment(self):
        """Mentions are rows written in the same transaction, not a JSONB list."""
        owner, candidate = _make_user(), _make_user()
        named_a, named_b = _make_user(), _make_user()
        await self.insert_entities([owner, candidate, named_a, named_b])
        job = await self._make_job([owner.user_id])
        application = await self._make_application(job.job_id, candidate)
        comment = await self._make_comment_mentioning(
            application.application_id, owner, [named_a, named_b]
        )
        event = _event(
            "recruiting.mentioned",
            "application",
            application.application_id,
            details={"commentId": comment.comment_id},
        )

        self.assertEqual(
            await resolve_recipients(self.session, event),
            {named_a.user_id, named_b.user_id},
        )

    async def test_a_pointer_the_write_site_did_not_carry_is_an_error(self):
        """Failing open here is how @-mentions would silently reach nobody."""
        job = await self._make_job([])
        event = _event("recruiting.review_opened", "job", job.job_id)

        with self.assertRaises(ValueError):
            await resolve_recipients(self.session, event)

    async def test_a_pointer_naming_no_row_is_an_error(self):
        job = await self._make_job([])
        event = _event(
            "recruiting.review_opened", "job", job.job_id, details={"reviewId": 987654}
        )

        with self.assertRaises(ValueError):
            await resolve_recipients(self.session, event)

    async def test_a_subject_of_the_wrong_kind_is_an_error(self):
        """A job id read as an application id resolves an unrelated posting's owners."""
        owner = _make_user()
        await self.insert_entities([owner])
        job = await self._make_job([owner.user_id])
        event = _event("recruiting.application_submitted", "job", job.job_id)

        with self.assertRaises(ValueError):
            await resolve_recipients(self.session, event)


class RegistrationCoverageTest(unittest.TestCase):
    """Guards the wiring itself, not resolver behavior.

    The behavior tests above cover each resolver shape once; repeating them
    per event type adds nothing. What actually goes wrong is registration: an
    event type left unregistered, or one registered under a typo'd string that
    then never fires. This compares ``_RESOLVERS`` against ``RecruitingEvent``
    -- the catalogue itself, not a copy of it, so the two cannot drift apart.
    """

    SILENT = {
        RecruitingEvent.EMAIL_SENT,
        RecruitingEvent.EMAIL_RECEIVED,
        RecruitingEvent.JOB_CREATED,
        RecruitingEvent.PENDING_EDIT_DISCARDED,
    }

    def test_every_event_type_outside_the_silent_set_has_a_resolver(self):
        registered = set(recipient_registry._RESOLVERS)
        expected = set(RecruitingEvent) - self.SILENT
        self.assertEqual(expected - registered, set())

    def test_silent_event_types_stay_unregistered(self):
        """Timeline-only events notify nobody by having no resolver at all."""
        registered = set(recipient_registry._RESOLVERS)
        self.assertEqual(self.SILENT & registered, set())

    def test_no_recruiting_resolver_is_registered_outside_the_catalogue(self):
        """A typo'd event_type would register but never fire; catch it here."""
        recruiting = {
            key
            for key in recipient_registry._RESOLVERS
            if key.startswith("recruiting.")
        }
        self.assertEqual(recruiting - set(RecruitingEvent), set())

    def test_every_resolver_declares_the_subject_it_reads(self):
        """subject_id is an integer either way; only the declaration separates them."""
        for event_type, (subject_type, _) in recipient_registry._RESOLVERS.items():
            if not event_type.startswith("recruiting."):
                continue
            with self.subTest(event_type=event_type):
                self.assertIn(subject_type, {"application", "job"})


if __name__ == "__main__":
    unittest.main()
