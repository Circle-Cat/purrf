import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_assignment_entity import (
    ApplicationAssignmentEntity,
)
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management import recipient_registry
from backend.notification_management.recipient_registry import resolve_recipients
from backend.recruiting import recipient_resolvers  # noqa: F401  (registers)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a minimal, unsaved user row satisfying every NOT NULL column."""
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
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

    ``tests/backend_test/helpers/recruiting_fixtures.py`` (used by the task
    brief's literal code) does not exist in this repo. This subclasses
    ``BaseRepositoryTestLib`` instead, matching every other DB-backed test in
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
    ) -> ApplicationAssignmentEntity:
        """Create and insert an assignment row for the application's first round.

        Args:
            application_id (int): The application being assigned.
            assignee (UsersEntity): Who is now responsible for it.
            assigned_by (UsersEntity): Who made the assignment.

        Returns:
            ApplicationAssignmentEntity: The inserted assignment row.
        """
        assignment = ApplicationAssignmentEntity(
            application_id=application_id,
            stage=ApplicationStage.APPLIED,
            round=1,
            assignee_id=assignee.user_id,
            assigned_by=assigned_by.user_id,
        )
        await self.insert_entities([assignment])
        return assignment

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

    async def test_review_opened_reaches_the_reviewer_ids_on_the_event(self):
        """``reviewerIds`` is a cross-task contract, not an internal detail.

        Task 8's write site is the only producer of this key. If it spells
        it differently (e.g. ``reviewer_ids``) or nests it, this resolver
        returns an empty set with no exception and no log -- the review
        opens and nobody is told. This test is the only thing that would
        catch that mismatch.
        """
        job = await self._make_job([])
        event = _event(
            "recruiting.review_opened",
            "job",
            job.job_id,
            details={"reviewerIds": [21, 22]},
        )

        self.assertEqual(await resolve_recipients(self.session, event), {21, 22})

    async def test_mentioned_reaches_the_mentioned_ids_on_the_event(self):
        """``mentionedIds`` is a cross-task contract, not an internal detail.

        ``board_service.add_comment`` (migrated onto ``record_event`` in
        Task 8) is the sole producer of this key. A misspelling or
        restructuring there yields an empty recipient set with no exception
        and no log -- @-mentions would silently stop notifying anyone.
        """
        event = _event(
            "recruiting.mentioned",
            "application",
            1,
            details={"mentionedIds": [31, 32]},
        )

        self.assertEqual(await resolve_recipients(self.session, event), {31, 32})

    async def test_review_decided_reaches_the_job_owners(self):
        """Subject here is the job itself, not an application.

        This job has no application at all, so a resolver that mistakenly
        joined through ``ApplicationEntity`` (copy-pasted from the
        owners-only resolvers above) would find nothing and return an empty
        set here, failing this test instead of silently passing it.
        """
        owner_a, owner_b = _make_user(), _make_user()
        await self.insert_entities([owner_a, owner_b])
        job = await self._make_job([owner_a.user_id, owner_b.user_id])
        event = _event("recruiting.review_decided", "job", job.job_id)

        self.assertEqual(
            await resolve_recipients(self.session, event),
            {owner_a.user_id, owner_b.user_id},
        )


class RegistrationCoverageTest(unittest.TestCase):
    """Guards the wiring itself, not resolver behavior.

    The two behavior tests above cover the owners-only and
    owners-plus-assignees shapes; repeating them 14 times adds nothing. What
    actually goes wrong is registration: an event_type left unregistered, or
    one registered under a typo'd domain prefix that then never fires. This
    reads ``_RESOLVERS`` directly against the catalogue to catch exactly that.
    """

    NOTIFYING = {
        "recruiting.application_submitted",
        "recruiting.auto_rejected",
        "recruiting.blacklisted",
        "recruiting.stage_changed",
        "recruiting.round_advanced",
        "recruiting.reassigned",
        "recruiting.auto_assigned",
        "recruiting.sub_status_changed",
        "recruiting.evaluation_confirmed",
        "recruiting.interview_scheduled",
        "recruiting.interview_updated",
        "recruiting.interview_cancelled",
        "recruiting.review_opened",
        "recruiting.review_decided",
        "recruiting.mentioned",
    }
    SILENT = {
        "recruiting.email_sent",
        "recruiting.email_received",
        "recruiting.job_created",
        "recruiting.pending_edit_discarded",
    }

    def test_every_notifying_event_type_has_a_resolver(self):
        registered = set(recipient_registry._RESOLVERS)
        self.assertEqual(self.NOTIFYING - registered, set())

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
        self.assertEqual(recruiting - self.NOTIFYING, set())


if __name__ == "__main__":
    unittest.main()
