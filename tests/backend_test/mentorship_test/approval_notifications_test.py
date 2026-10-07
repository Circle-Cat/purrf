"""Who hears about a mentorship approval request, and what the email says."""

import unittest
from datetime import datetime, timezone

from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.event_entity import EventEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship import notification_renderers  # noqa: F401 (registers)
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.notification_management import recipient_registry, render_registry
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _user(first_name, last_name) -> UsersEntity:
    return UsersEntity(
        first_name=first_name,
        last_name=last_name,
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class ApprovalNotificationsTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.raiser = _user("Ada", "Ng")
        self.reviewer = _user("Rae", "Kim")
        self.new_reviewer = _user("Sam", "Oyelaran")
        await self.insert_entities([self.raiser, self.reviewer, self.new_reviewer])
        self.request = ApprovalRequestEntity(
            action="publish_matching",
            target_type="matching_run",
            target_id="r7-x-y",
            payload={"round_id": 7},
            reason="Reviewed <every> pair",
            raised_by=self.raiser.user_id,
            reviewer_id=self.reviewer.user_id,
            status=ApprovalRequestStatus.PENDING,
        )
        await self.insert_entities([self.request])

    async def _event(self, event_type, actor, **details):
        event = EventEntity(
            subject_type="mentorship_round",
            subject_id=7,
            actor_id=actor.user_id,
            event_type=event_type,
            details={
                "requestId": self.request.request_id,
                "action": "publish_matching",
                "roundName": "Spring 2026",
                **details,
            },
        )
        await self.insert_entities([event])
        return event

    async def test_a_new_request_reaches_its_reviewer(self):
        event = await self._event("mentorship.approval_requested", self.raiser)

        recipients = await recipient_registry.resolve_recipients(self.session, event)

        self.assertEqual(recipients, {self.reviewer.user_id})

    async def test_a_handover_reaches_the_reviewer_it_was_handed_to(self):
        self.request.reviewer_id = self.new_reviewer.user_id
        await self.session.flush()
        event = await self._event("mentorship.approval_reassigned", self.raiser)

        recipients = await recipient_registry.resolve_recipients(self.session, event)

        self.assertEqual(recipients, {self.new_reviewer.user_id})

    async def test_a_decision_reaches_the_raiser(self):
        for decision in ("approved", "rejected"):
            with self.subTest(decision=decision):
                event = await self._event(
                    "mentorship.approval_decided", self.reviewer, decision=decision
                )

                recipients = await recipient_registry.resolve_recipients(
                    self.session, event
                )

                self.assertEqual(recipients, {self.raiser.user_id})

    async def test_a_withdrawal_reaches_the_reviewer(self):
        event = await self._event(
            "mentorship.approval_decided", self.raiser, decision="withdrawn"
        )

        recipients = await recipient_registry.resolve_recipients(self.session, event)

        self.assertEqual(recipients, {self.reviewer.user_id})

    async def test_an_event_naming_no_request_is_refused(self):
        event = EventEntity(
            subject_type="mentorship_round",
            subject_id=7,
            actor_id=self.raiser.user_id,
            event_type="mentorship.approval_requested",
            details={},
        )
        await self.insert_entities([event])

        with self.assertRaises(ValueError):
            await recipient_registry.resolve_recipients(self.session, event)

    async def test_the_request_email_says_who_asked_for_what_and_why(self):
        event = await self._event("mentorship.approval_requested", self.raiser)

        subject, body = await render_registry.render(self.session, event)

        self.assertEqual(subject, "Mentorship approval requested: Spring 2026")
        self.assertIn(
            "Ada Ng asked you to approve a request to publish the matching result "
            "for Spring 2026.",
            body,
        )
        self.assertIn("Their reason: Reviewed &lt;every&gt; pair", body)
        self.assertIn("Open Mentorship Management in Purrf", body)

    async def test_the_handover_email_says_a_handover_happened(self):
        event = await self._event("mentorship.approval_reassigned", self.raiser)

        subject, body = await render_registry.render(self.session, event)

        self.assertEqual(subject, "Mentorship approval reassigned to you: Spring 2026")
        self.assertIn("Ada Ng moved a request to publish the matching result", body)

    async def test_the_rejection_email_carries_the_reviewer_s_reason(self):
        self.request.status = ApprovalRequestStatus.REJECTED
        self.request.decision_comment = "Mentor 10 is away until May"
        await self.session.flush()
        event = await self._event(
            "mentorship.approval_decided", self.reviewer, decision="rejected"
        )

        subject, body = await render_registry.render(self.session, event)

        self.assertEqual(subject, "Mentorship approval rejected: Spring 2026")
        self.assertIn("Rae Kim rejected your request", body)
        self.assertIn("Their reason: Mentor 10 is away until May", body)

    async def test_the_approval_and_withdrawal_emails(self):
        approved = await self._event(
            "mentorship.approval_decided", self.reviewer, decision="approved"
        )
        withdrawn = await self._event(
            "mentorship.approval_decided", self.raiser, decision="withdrawn"
        )

        approved_subject, approved_body = await render_registry.render(
            self.session, approved
        )
        withdrawn_subject, withdrawn_body = await render_registry.render(
            self.session, withdrawn
        )

        self.assertEqual(approved_subject, "Mentorship approval approved: Spring 2026")
        self.assertIn("Rae Kim approved your request", approved_body)
        self.assertEqual(
            withdrawn_subject, "Mentorship approval withdrawn: Spring 2026"
        )
        self.assertIn("Ada Ng withdrew their request", withdrawn_body)
        self.assertIn("Nothing is waiting on you", withdrawn_body)


if __name__ == "__main__":
    unittest.main()
