import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod, ParticipantRole
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship import notification_renderers  # noqa: F401 (registers)
from backend.notification_management import render_registry
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_OPEN_ROUND = {
    "mentorshipRole": "mentor",
    "roundId": 12,
    "roundName": "2026 Fall",
    "registrationDeadlineAt": "2026-09-30T15:59:00+00:00",
    "matchNotificationAt": "2026-10-15T00:00:00+00:00",
}

_NO_ROUND = {
    "mentorshipRole": "mentor",
    "roundId": None,
    "roundName": None,
    "registrationDeadlineAt": None,
    "matchNotificationAt": None,
}


class MentorAdmittedRendererTest(BaseRepositoryTestLib):
    """The admission email a mentor receives, rendered from the event."""

    async def _make_recipient(
        self,
        first_name="Ada",
        last_name="Lovelace",
        preferred_name=None,
        tz="Asia/Shanghai",
    ) -> UsersEntity:
        user = UsersEntity(
            first_name=first_name,
            last_name=last_name,
            preferred_name=preferred_name,
            timezone=tz,
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )
        await self.insert_entities([user])
        return user

    async def _make_event(self, recipient: UsersEntity, details: dict) -> EventEntity:
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            title="Mentorship Mentor",
            status=JobStatus.PUBLISHED,
        )
        await self.insert_entities([job])
        application = ApplicationEntity(
            job_id=job.job_id, user_id=recipient.user_id, stage=ApplicationStage.HIRED
        )
        await self.insert_entities([application])
        event = EventEntity(
            subject_type="application",
            subject_id=application.application_id,
            actor_id=None,
            event_type="mentorship.mentor_admitted",
            details=details,
        )
        await self.insert_entities([event])
        return event

    async def _render(self, details, **recipient_kwargs):
        recipient = await self._make_recipient(**recipient_kwargs)
        event = await self._make_event(recipient, details)
        return await render_registry.render(self.session, event)

    async def test_open_round_names_the_round_and_both_dates(self):
        subject, body = await self._render(_OPEN_ROUND)

        self.assertEqual(
            subject,
            "Welcome to Circle Cat Mentorship! Your application has been approved",
        )
        self.assertIn("<p>Dear Ada,</p>", body)
        self.assertIn("complete the mentorship registration form for 2026 Fall.", body)
        self.assertIn(
            "Registration Deadline: September 30, 2026, at 11:59 PM (Asia/Shanghai)",
            body,
        )
        self.assertIn(
            "Matching Results: Expected on October 15, 2026 (Asia/Shanghai)", body
        )

    async def test_no_open_round_omits_the_dates_and_promises_a_follow_up(self):
        subject, body = await self._render(_NO_ROUND)

        self.assertEqual(
            subject,
            "Welcome to Circle Cat Mentorship! Your application has been approved",
        )
        self.assertIn("Registration for the upcoming round is not open just yet", body)
        self.assertIn("We will be in touch soon with the next steps!", body)
        self.assertNotIn("Key Dates", body)

    async def test_deadline_is_converted_to_the_recipients_timezone(self):
        """The same instant, stated where the recipient lives -- 11:59 PM in
        Shanghai is 8:59 AM the same day in Los Angeles."""
        _, body = await self._render(_OPEN_ROUND, tz="America/Los_Angeles")

        self.assertIn(
            "Registration Deadline: September 30, 2026, at 8:59 AM "
            "(America/Los_Angeles)",
            body,
        )

    async def test_matching_date_is_converted_before_it_is_truncated_to_a_day(self):
        """Taking the stored date component first would print October 15 for a
        Shanghai recipient, a day early."""
        details = {**_OPEN_ROUND, "matchNotificationAt": "2026-10-15T20:00:00+00:00"}

        _, body = await self._render(details, tz="Asia/Shanghai")

        self.assertIn(
            "Matching Results: Expected on October 16, 2026 (Asia/Shanghai)", body
        )

    async def test_a_naive_deadline_falls_back_to_the_no_round_variant(self):
        """The one-off import wrote bare dates. There is no instant to convert,
        and inventing midnight would state a deadline nobody set."""
        details = {**_OPEN_ROUND, "registrationDeadlineAt": "2026-09-30"}

        _, body = await self._render(details)

        self.assertIn("Registration for the upcoming round is not open just yet", body)
        self.assertNotIn("Key Dates", body)

    async def test_an_unparseable_matching_date_falls_back_to_the_no_round_variant(
        self,
    ):
        details = {**_OPEN_ROUND, "matchNotificationAt": "not a date"}

        _, body = await self._render(details)

        self.assertIn("Registration for the upcoming round is not open just yet", body)

    async def test_an_unresolvable_timezone_falls_back_to_los_angeles(self):
        _, body = await self._render(_OPEN_ROUND, tz="Mars/Olympus_Mons")

        self.assertIn("(America/Los_Angeles)", body)

    async def test_an_empty_timezone_falls_back_to_los_angeles(self):
        _, body = await self._render(_OPEN_ROUND, tz="")

        self.assertIn("(America/Los_Angeles)", body)

    async def test_the_preferred_name_wins_over_the_legal_name(self):
        _, body = await self._render(_OPEN_ROUND, preferred_name="Ari")

        self.assertIn("<p>Dear Ari,</p>", body)

    async def test_a_name_that_resolves_to_nothing_greets_without_one(self):
        _, body = await self._render(_OPEN_ROUND, first_name="", last_name="")

        self.assertIn("<p>Hello,</p>", body)
        self.assertNotIn("Dear", body)

    async def test_a_blank_round_name_drops_the_round_from_the_sentence(self):
        details = {**_OPEN_ROUND, "roundName": "  "}

        _, body = await self._render(details)

        self.assertIn("complete the mentorship registration form.", body)
        self.assertNotIn("form for", body)

    async def test_both_variants_carry_the_do_not_reply_footer(self):
        footer = (
            "<p>This is an automated message from Purrf. Please do not reply "
            "directly to this email as this inbox is not monitored.</p>"
        )

        _, with_round = await self._render(_OPEN_ROUND)
        _, without_round = await self._render(_NO_ROUND)

        self.assertTrue(with_round.endswith(footer))
        self.assertTrue(without_round.endswith(footer))

    async def test_the_key_dates_block_is_a_list(self):
        _, body = await self._render(_OPEN_ROUND)

        self.assertIn("<p>Key Dates:</p><ul><li>", body)
        self.assertEqual(body.count("<li>"), 2)


if __name__ == "__main__":
    unittest.main()
