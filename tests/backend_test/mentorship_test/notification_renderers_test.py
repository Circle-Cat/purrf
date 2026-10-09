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

    async def test_a_name_containing_markup_is_escaped_in_the_body(self):
        """The greeting is HTML, so a name has to reach it as text."""
        _, body = await self._render(_OPEN_ROUND, preferred_name="<b>Ada</b>")

        self.assertIn("<p>Dear &lt;b&gt;Ada&lt;/b&gt;,</p>", body)
        self.assertNotIn("<b>", body)

    async def test_a_round_name_containing_markup_is_escaped_in_the_body(self):
        details = {**_OPEN_ROUND, "roundName": "<i>2026 Fall</i>"}

        _, body = await self._render(details)

        self.assertIn(
            "registration form for &lt;i&gt;2026 Fall&lt;/i&gt;.",
            body,
        )
        self.assertNotIn("<i>", body)

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


def _prepared(details):
    return EventEntity(
        subject_type="mentorship_email_send",
        subject_id=5,
        actor_id=None,
        event_type="mentorship.email_send_prepared",
        details={
            "roundName": "Fall 2026",
            "stage": "match_result",
            "subject": "Your <match>",
            **details,
        },
    )


class EmailSendPreparedRendererTest(unittest.IsolatedAsyncioTestCase):
    """What the admin who created a Kit send is told; rendered from details only."""

    async def _render(self, details):
        return await render_registry.render(None, _prepared(details))

    async def test_scheduled_names_the_send_the_time_and_everyone_left_out(self):
        subject, body = await self._render({
            "status": "scheduled",
            "sendAt": "2026-10-20T16:00:00+00:00",
            "handedCount": 12,
            "notHanded": [
                {"name": "Cee", "result": "import_failed", "failureReason": "kit_422"},
                {"name": "Dee", "result": "unsubscribed", "failureReason": None},
                {
                    "name": "Eve",
                    "result": "unsubscribed",
                    "failureReason": "complained",
                },
                {"name": "Fay", "result": "bounced", "failureReason": None},
                {"name": "Gus", "result": "import_failed", "failureReason": "no_email"},
            ],
        })
        self.assertEqual(subject, "Kit email scheduled: Match result · Fall 2026")
        for text in (
            "<li>Round: Fall 2026</li>",
            "<li>Stage: Match result</li>",
            "<li>Kit draft: Your &lt;match&gt;</li>",
            "<li>Sends at: 2026-10-20 09:00 Pacific</li>",
            "<li>Handed to Kit: 12 people</li>",
            "Not handed to Kit (5)",
            "<li>Cee: could not be added to Kit (Kit error 422)</li>",
            "<li>Dee: unsubscribed</li>",
            "<li>Eve: marked an earlier email as spam</li>",
            "<li>Fay: email bounced</li>",
            "<li>Gus: no email address</li>",
            "Mentorship Management",
        ):
            self.assertIn(text, body)

    async def test_scheduled_with_everyone_handed_says_so(self):
        _, body = await self._render({
            "status": "scheduled",
            "sendAt": "2026-10-20T16:00:00+00:00",
            "handedCount": 1,
            "notHanded": [],
        })
        self.assertIn("<li>Handed to Kit: 1 person</li>", body)
        self.assertIn("Everyone you selected was handed to Kit.", body)
        self.assertNotIn("Not handed", body)

    async def test_failed_gives_the_reason_and_says_nothing_was_sent(self):
        subject, body = await self._render({
            "status": "failed",
            "failureCode": "time_passed",
            "errorMessage": "internal wording",
        })
        self.assertEqual(subject, "Kit email not scheduled: Match result · Fall 2026")
        self.assertIn(
            "Why: The send time passed while people were being added to Kit.", body
        )
        self.assertIn("No email was sent.", body)
        self.assertIn("<li>Kit draft: Your &lt;match&gt;</li>", body)
        self.assertNotIn("internal wording", body)

    async def test_kit_error_shows_the_recorded_details(self):
        _, body = await self._render({
            "status": "failed",
            "failureCode": "kit_error",
            "errorMessage": "Undoing the schedule failed: check <Kit>",
        })
        self.assertIn("Why: Something went wrong talking to Kit.", body)
        self.assertIn("Details: Undoing the schedule failed: check &lt;Kit&gt;", body)
        self.assertIn("No email was sent.", body)

    async def test_possibly_scheduled_failure_does_not_claim_nothing_was_sent(self):
        _, body = await self._render({
            "status": "failed",
            "failureCode": "kit_error",
            "errorMessage": "Undoing the schedule failed",
            "mayStillBeScheduled": True,
        })
        self.assertIn("Kit may still send this email", body)
        self.assertNotIn("No email was sent.", body)


if __name__ == "__main__":
    unittest.main()
