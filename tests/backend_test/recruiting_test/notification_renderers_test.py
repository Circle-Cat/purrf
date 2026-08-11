import unittest
from datetime import datetime, timedelta, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management import recipient_registry, render_registry
from backend.recruiting import notification_renderers  # noqa: F401 (registers)
from backend.recruiting import recipient_resolvers  # noqa: F401 (registers)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user(first_name="U", last_name="Ser") -> UsersEntity:
    return UsersEntity(
        first_name=first_name,
        last_name=last_name,
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class NotificationRenderersTest(BaseRepositoryTestLib):
    """DB-backed tests for the recruiting event_type -> email-copy wiring.

    Mirrors ``recipient_resolvers_test.py``'s ``BaseRepositoryTestLib``
    pattern (no ``tests/backend_test/helpers`` fixtures module exists in
    this repo).
    """

    async def _make_job(self, kind=JobKind.EMPLOYMENT) -> JobEntity:
        job = JobEntity(kind=kind, title="Backend Engineer", status=JobStatus.PUBLISHED)
        await self.insert_entities([job])
        return job

    async def _make_application(
        self, job_id: int, candidate: UsersEntity, stage=ApplicationStage.APPLIED
    ) -> ApplicationEntity:
        application = ApplicationEntity(
            job_id=job_id, user_id=candidate.user_id, stage=stage
        )
        await self.insert_entities([application])
        return application

    async def _make_event(
        self,
        event_type: str,
        subject_type: str,
        subject_id: int,
        actor: UsersEntity | None,
        details: dict | None = None,
    ) -> EventEntity:
        event = EventEntity(
            subject_type=subject_type,
            subject_id=subject_id,
            actor_id=None if actor is None else actor.user_id,
            event_type=event_type,
            details=details or {},
        )
        await self.insert_entities([event])
        return event

    async def test_application_submitted_names_the_applicant_job_and_stage(self):
        owner, candidate = _make_user("Grace", "Hopper"), _make_user("Ada", "Lovelace")
        await self.insert_entities([owner, candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        event = await self._make_event(
            "recruiting.application_submitted",
            "application",
            application.application_id,
            owner,
            details={"stage": ApplicationStage.RECRUITER_SCREENING.value},
        )

        subject, body = await render_registry.render(self.session, event)

        self.assertEqual(subject, "New application: Ada Lovelace for Backend Engineer")
        self.assertIn("Recruiter screening stage", body)

    async def test_base_dto_resolves_the_candidate_primary_address(self):
        """The primary address wins over an older claim.

        A candidate typically has more than one row: the address seeded from
        their first login, plus whatever they later made primary. Picking the
        first row found would name the stale one, so this asserts the mail
        goes through the same primary-else-oldest rule the board and the
        blacklist page read.
        """
        candidate = _make_user("Ada", "Lovelace")
        await self.insert_entities([candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        await self.insert_entities([
            UserEmailsEntity(
                user_id=candidate.user_id,
                email="old@example.com",
                otp_confirmed=True,
                is_primary=False,
            ),
            UserEmailsEntity(
                user_id=candidate.user_id,
                email="ada@example.com",
                otp_confirmed=True,
                is_primary=True,
            ),
        ])
        event = await self._make_event(
            "recruiting.application_submitted",
            "application",
            application.application_id,
            candidate,
            details={"stage": ApplicationStage.RECRUITER_SCREENING.value},
        )

        dto = await notification_renderers._base_dto(self.session, event)

        self.assertEqual(dto.applicant_email, "ada@example.com")

        # And it reaches the body: the copy tests prove the line's shape from
        # a hand-built dto, which cannot catch the renderer failing to feed it.
        _, body = await render_registry.render(self.session, event)
        self.assertIn("Candidate: Ada Lovelace (ada@example.com)", body)

    async def test_base_dto_leaves_the_address_none_when_there_is_none(self):
        """A candidate with no email rows, and a job-scoped event that has no
        candidate at all, both resolve to None rather than "" -- the copy
        decides what to print from that."""
        candidate = _make_user("Ada", "Lovelace")
        await self.insert_entities([candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        application_event = await self._make_event(
            "recruiting.application_submitted",
            "application",
            application.application_id,
            candidate,
            details={"stage": ApplicationStage.RECRUITER_SCREENING.value},
        )
        job_event = await self._make_event(
            "recruiting.review_decided",
            "job",
            job.job_id,
            candidate,
            details={"kind": "initial", "decision": "approved", "comment": None},
        )

        self.assertIsNone(
            (
                await notification_renderers._base_dto(self.session, application_event)
            ).applicant_email
        )
        self.assertIsNone(
            (
                await notification_renderers._base_dto(self.session, job_event)
            ).applicant_email
        )

    async def test_application_submitted_reads_as_auto_hired_when_a_rule_hired_it(
        self,
    ):
        """A screen rule hiring outright is the same event, worded differently.

        Both land as ``application_submitted``; the auto-hire marker in the
        details is the only thing separating "someone applied, go look" from
        "this is already decided". Without it an owner would be sent chasing
        work a rule already finished.
        """
        owner, candidate = _make_user("Grace", "Hopper"), _make_user("Ada", "Lovelace")
        await self.insert_entities([owner, candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        event = await self._make_event(
            "recruiting.application_submitted",
            "application",
            application.application_id,
            owner,
            details={
                "stage": ApplicationStage.HIRED.value,
                "screenAutoHireRuleId": "rule-1",
            },
        )

        subject, body = await render_registry.render(self.session, event)

        # Same stage, no marker: the marker is then the only difference
        # between the two renders, so this cannot pass on stage wording alone.
        plain_subject, plain_body = await render_registry.render(
            self.session,
            await self._make_event(
                "recruiting.application_submitted",
                "application",
                application.application_id,
                owner,
                details={"stage": ApplicationStage.HIRED.value},
            ),
        )
        self.assertNotEqual(subject, plain_subject)
        self.assertNotEqual(body, plain_body)

    async def test_mentioned_names_the_actor_and_applicant(self):
        actor, candidate = _make_user("Grace", "Hopper"), _make_user("Ada", "Lovelace")
        await self.insert_entities([actor, candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        event = await self._make_event(
            "recruiting.mentioned", "application", application.application_id, actor
        )

        subject, _ = await render_registry.render(self.session, event)

        self.assertEqual(
            subject, "Grace Hopper mentioned you: Ada Lovelace (Backend Engineer)"
        )

    async def test_auto_assigned_reads_as_automatic_when_the_event_has_no_actor(self):
        """A null actor must reach the "nobody did this" branch of the copy.

        ``_display_name`` answers "" for a user it cannot resolve, which is
        also what a deleted actor looks like -- and the copy deliberately
        words that case as "Someone assigned you", because claiming an
        assignment was automatic when a person made it would be a lie. So a
        null actor has to arrive as None, not as "": resolving it first
        collapses the two and mislabels the pipeline's own rule as a person.
        """
        candidate = _make_user("Ada", "Lovelace")
        await self.insert_entities([candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        event = await self._make_event(
            "recruiting.auto_assigned",
            "application",
            application.application_id,
            None,
            details={"stage": ApplicationStage.RECRUITER_SCREENING.value, "round": 1},
        )

        _, body = await render_registry.render(self.session, event)

        self.assertIn("You were automatically assigned", body)
        self.assertIn("default assignee", body)
        self.assertNotIn("Someone", body)

    async def test_review_decided_dispatches_to_approved_or_rejected_by_details(self):
        actor = _make_user("Grace", "Hopper")
        await self.insert_entities([actor])
        job = await self._make_job()
        approved_event = await self._make_event(
            "recruiting.review_decided",
            "job",
            job.job_id,
            actor,
            details={"kind": "initial", "decision": "approved", "comment": None},
        )
        rejected_event = await self._make_event(
            "recruiting.review_decided",
            "job",
            job.job_id,
            actor,
            details={"kind": "initial", "decision": "rejected", "comment": "no"},
        )

        approved_subject, approved_body = await render_registry.render(
            self.session, approved_event
        )
        rejected_subject, _ = await render_registry.render(self.session, rejected_event)

        self.assertEqual(approved_subject, "Posting approved: Backend Engineer")
        self.assertIn("Grace Hopper approved your submission", approved_body)
        self.assertEqual(rejected_subject, "Posting rejected: Backend Engineer")

    async def test_blacklisted_carries_the_reason_and_points_at_the_blacklist_page(
        self,
    ):
        actor, candidate = _make_user("Grace", "Hopper"), _make_user("Ada", "Lovelace")
        await self.insert_entities([actor, candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        event = await self._make_event(
            "recruiting.blacklisted",
            "application",
            application.application_id,
            actor,
            details={"fromStage": "tech", "reason": "fabricated credentials"},
        )

        subject, body = await render_registry.render(self.session, event)

        self.assertEqual(
            subject, "Application blacklisted: Ada Lovelace (Backend Engineer)"
        )
        self.assertIn("fabricated credentials", body)
        self.assertIn("Blacklist", body)

    async def test_rendered_emails_carry_the_automated_footer(self):
        """Each renderer appends the footer itself -- nothing downstream of
        here adds one -- so a renderer that skipped it would send a body with
        no footer and nothing else would notice."""
        actor, candidate = _make_user("Grace", "Hopper"), _make_user("Ada", "Lovelace")
        await self.insert_entities([actor, candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        event = await self._make_event(
            "recruiting.blacklisted",
            "application",
            application.application_id,
            actor,
            details={"fromStage": "tech", "reason": "fabricated credentials"},
        )

        _, body = await render_registry.render(self.session, event)

        self.assertIn("Replies to this address aren't monitored", body)

    async def test_stage_changed_reads_the_snapshot_not_the_live_stage(self):
        """The application may have moved on again by the time this email
        renders (redelivery up to the 24h EXPIRY). The body must report the
        stage the event recorded, not whatever the row says right now."""
        actor, candidate = _make_user("Grace", "Hopper"), _make_user("Ada", "Lovelace")
        await self.insert_entities([actor, candidate])
        job = await self._make_job()
        application = await self._make_application(
            job.job_id, candidate, stage=ApplicationStage.TECH
        )
        event = await self._make_event(
            "recruiting.stage_changed",
            "application",
            application.application_id,
            actor,
            details={
                "fromStage": ApplicationStage.RECRUITER_SCREENING.value,
                "toStage": ApplicationStage.BEHAVIORAL.value,
            },
        )
        # The application has since moved on to a stage the event never saw.
        application.stage = ApplicationStage.BOARD_REVIEW
        await self.session.flush()

        _, body = await render_registry.render(self.session, event)

        self.assertIn("Behavioral stage", body)
        self.assertNotIn("Board review", body)

    async def test_interview_scheduled_formats_the_start_time_in_utc(self):
        actor, candidate = _make_user("Grace", "Hopper"), _make_user("Ada", "Lovelace")
        await self.insert_entities([actor, candidate])
        job = await self._make_job()
        application = await self._make_application(job.job_id, candidate)
        start_at = datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc)
        event = await self._make_event(
            "recruiting.interview_scheduled",
            "application",
            application.application_id,
            actor,
            details={
                "stage": ApplicationStage.TECH.value,
                "round": 2,
                "startAt": start_at.isoformat(),
                "endAt": (start_at + timedelta(hours=1)).isoformat(),
            },
        )

        _, body = await render_registry.render(self.session, event)

        self.assertIn("2026-08-12 15:00 UTC", body)
        self.assertIn("Tech, session 2", body)


class RegistrationCoverageTest(unittest.TestCase):
    """Every recipient-notifying recruiting event type must also render.

    A recipient with no renderer is the exact silent-non-delivery failure
    the whole design exists to prevent: ``record_event`` picks a recipient,
    the notification row is written and published, and delivery permanently
    fails with ``KeyError`` (a ``LookupError``) the first time anyone tries
    to send it.
    """

    def test_every_notifying_event_type_has_a_renderer(self):
        notifying = {
            event_type
            for event_type in recipient_registry._RESOLVERS
            if event_type.startswith("recruiting.")
        }
        registered = set(render_registry._RENDERERS)
        self.assertEqual(notifying - registered, set())

    def test_no_recruiting_renderer_is_registered_outside_what_notifies(self):
        notifying = {
            event_type
            for event_type in recipient_registry._RESOLVERS
            if event_type.startswith("recruiting.")
        }
        registered_recruiting = {
            event_type
            for event_type in render_registry._RENDERERS
            if event_type.startswith("recruiting.")
        }
        self.assertEqual(registered_recruiting - notifying, set())


if __name__ == "__main__":
    unittest.main()
