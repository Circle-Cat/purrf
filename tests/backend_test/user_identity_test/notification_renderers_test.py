import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.user_enums import (
    USER_SUBJECT_TYPE,
    BlockRequestStatus,
    UserEvent,
)
from backend.entity.block_request_entity import BlockRequestEntity
from backend.entity.event_entity import EventEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management import recipient_registry, render_registry
from backend.user_identity import notification_renderers  # noqa: F401 (registers)
from backend.user_identity import user_recipient_resolvers  # noqa: F401 (registers)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_FOOTER = (
    "<p>This is an automated message from Purrf. Please do not reply "
    "directly to this email as this inbox is not monitored.</p>"
)

_MARKUP_REASON = '<a href="http://evil/">click</a>'
_ESCAPED_REASON = "&lt;a href=&quot;http://evil/&quot;&gt;click&lt;/a&gt;"

# An id no row in this transaction can have: as a request id it makes
# _request_of answer None, as a subject id it names nobody.
_MISSING_ID = 999999999


def _make_user(first_name="U", last_name="Ser", preferred_name=None) -> UsersEntity:
    return UsersEntity(
        first_name=first_name,
        last_name=last_name,
        preferred_name=preferred_name,
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        is_blocked=False,
        updated_timestamp=datetime.now(timezone.utc),
    )


class BlockRequestRenderersTest(BaseRepositoryTestLib):
    """The three block-request events, rendered through ``render_registry``.

    DB-backed like the recruiting and mentorship renderer suites: the
    renderers resolve their people and their request row out of the session,
    so a hand-built stub would exercise nothing that runs in production.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.target = _make_user("Ada", "Lovelace")
        self.raiser = _make_user("Grace", "Hopper")
        self.reviewer = _make_user("Alan", "Turing")
        self.other_admin = _make_user("Edsger", "Dijkstra")
        await self.insert_entities([
            self.target,
            self.raiser,
            self.reviewer,
            self.other_admin,
        ])
        self.request = await self._make_request()

    async def _make_request(
        self,
        reason="second no-show",
        reviewer: UsersEntity | None = None,
        status=BlockRequestStatus.PENDING,
        decided_by: UsersEntity | None = None,
        decision_note=None,
    ) -> BlockRequestEntity:
        row = BlockRequestEntity(
            target_user_id=self.target.user_id,
            raised_by=self.raiser.user_id,
            raised_from="recruiting_board",
            reason=reason,
            reviewer_id=(reviewer or self.reviewer).user_id,
            status=status,
            decided_by=None if decided_by is None else decided_by.user_id,
            decision_note=decision_note,
        )
        await self.insert_entities([row])
        return row

    async def _render(self, event_type, details=None):
        event = EventEntity(
            subject_type=USER_SUBJECT_TYPE,
            subject_id=self.target.user_id,
            actor_id=self.raiser.user_id,
            event_type=event_type,
            details=(
                {"requestId": self.request.request_id} if details is None else details
            ),
        )
        await self.insert_entities([event])
        return await render_registry.render(self.session, event)

    # -- requested ----------------------------------------------------------

    async def test_requested_names_the_raiser_the_target_and_the_reason(self):
        subject, body = await self._render(UserEvent.BLOCK_REQUESTED)

        self.assertEqual(subject, "A block request is waiting for your decision")
        self.assertIn(
            "Grace Hopper has asked you to decide whether Ada Lovelace should "
            "be blocked from Purrf.",
            body,
        )
        self.assertIn("Reason given: second no-show", body)
        self.assertIn("Accounts page", body)

    async def test_requested_escapes_a_reason_written_as_markup(self):
        """The reason is free text typed by a colleague and lands in an HTML
        body. Unescaped, a link in it would render as a live link in the
        reviewer's mail client."""
        self.request.reason = _MARKUP_REASON
        await self.session.flush()

        _, body = await self._render(UserEvent.BLOCK_REQUESTED)

        self.assertNotIn(_MARKUP_REASON, body)
        self.assertIn(_ESCAPED_REASON, body)

    async def test_requested_escapes_a_display_name_containing_markup(self):
        """Names are user-editable too, so they get the same treatment."""
        self.raiser.preferred_name = "<script>alert(1)</script>"
        await self.session.flush()

        _, body = await self._render(UserEvent.BLOCK_REQUESTED)

        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)

    # -- reassigned ---------------------------------------------------------

    async def test_reassigned_names_the_target_and_the_new_reviewer(self):
        self.request.reviewer_id = self.other_admin.user_id
        await self.session.flush()

        subject, body = await self._render(
            UserEvent.BLOCK_REQUEST_REASSIGNED,
            {
                "requestId": self.request.request_id,
                "previousReviewerId": self.reviewer.user_id,
            },
        )

        self.assertEqual(subject, "A block request has been reassigned")
        self.assertIn(
            "The block request about Ada Lovelace is now with Edsger Dijkstra.", body
        )

    async def test_reassigned_reads_correctly_for_both_recipients(self):
        """One body goes to the reviewer who gained it and the one who lost
        it -- render_registry renders per event, not per recipient -- so it
        must not address either of them as "you" and must not claim the
        reader still owns the request."""
        self.request.reviewer_id = self.other_admin.user_id
        await self.session.flush()

        _, body = await self._render(
            UserEvent.BLOCK_REQUEST_REASSIGNED,
            {
                "requestId": self.request.request_id,
                "previousReviewerId": self.reviewer.user_id,
            },
        )

        self.assertIn("If that is you", body)
        self.assertIn("If it is not, there is nothing left for you to do.", body)
        # The reviewer it was taken from is a recipient, not a subject: naming
        # them here would read as though they still hold it.
        self.assertNotIn("Alan Turing", body)

    # -- decided ------------------------------------------------------------

    async def test_decided_approved_says_approved_and_states_the_consequence(self):
        self.request.status = BlockRequestStatus.APPROVED
        self.request.decided_by = self.reviewer.user_id
        await self.session.flush()

        subject, body = await self._render(
            UserEvent.BLOCK_REQUEST_DECIDED,
            {"requestId": self.request.request_id, "approved": True},
        )

        self.assertEqual(subject, "Your block request was approved")
        self.assertIn(
            "Alan Turing has approved the block request you raised about Ada Lovelace.",
            body,
        )
        self.assertIn("Ada Lovelace is now blocked from Purrf.", body)
        self.assertNotIn("has not been blocked", body)

    async def test_decided_rejected_says_rejected_and_states_the_consequence(self):
        self.request.status = BlockRequestStatus.REJECTED
        self.request.decided_by = self.reviewer.user_id
        await self.session.flush()

        subject, body = await self._render(
            UserEvent.BLOCK_REQUEST_DECIDED,
            {"requestId": self.request.request_id, "approved": False},
        )

        self.assertEqual(subject, "Your block request was rejected")
        self.assertIn(
            "Alan Turing has rejected the block request you raised about Ada Lovelace.",
            body,
        )
        self.assertIn("Ada Lovelace has not been blocked.", body)
        self.assertNotIn("is now blocked from Purrf", body)

    async def test_decided_carries_the_note_and_escapes_it(self):
        self.request.status = BlockRequestStatus.REJECTED
        self.request.decided_by = self.reviewer.user_id
        self.request.decision_note = f"see {_MARKUP_REASON}"
        await self.session.flush()

        _, body = await self._render(
            UserEvent.BLOCK_REQUEST_DECIDED,
            {"requestId": self.request.request_id, "approved": False},
        )

        self.assertIn(f"Note: see {_ESCAPED_REASON}", body)
        self.assertNotIn(_MARKUP_REASON, body)

    async def test_decided_omits_the_note_line_when_there_is_no_note(self):
        self.request.status = BlockRequestStatus.APPROVED
        self.request.decided_by = self.reviewer.user_id
        await self.session.flush()

        _, body = await self._render(
            UserEvent.BLOCK_REQUEST_DECIDED,
            {"requestId": self.request.request_id, "approved": True},
        )

        self.assertNotIn("Note:", body)

    async def test_decided_falls_back_to_not_approved_without_the_flag(self):
        """The row carries no outcome column -- the event's ``approved`` key is
        the only source. Absent, it must read as "not approved" rather than
        raising or claiming a block that never happened."""
        _, body = await self._render(
            UserEvent.BLOCK_REQUEST_DECIDED, {"requestId": self.request.request_id}
        )

        self.assertIn("has not been blocked", body)

    # -- degraded input -----------------------------------------------------

    async def test_every_renderer_survives_a_request_row_it_cannot_read(self):
        """A request can outlive the row -- an event redelivered after the
        request was purged, or details that never carried an id. Rendering is
        the last step before delivery, so raising here would strand the
        notification permanently.
        """
        for event_type in (
            UserEvent.BLOCK_REQUESTED,
            UserEvent.BLOCK_REQUEST_REASSIGNED,
            UserEvent.BLOCK_REQUEST_DECIDED,
        ):
            for details in ({}, {"requestId": _MISSING_ID}):
                with self.subTest(event_type=event_type, details=details):
                    subject, body = await self._render(event_type, details)

                    self.assertTrue(subject)
                    self.assertIn("Ada Lovelace", body)
                    self.assertTrue(body.endswith(_FOOTER))

    async def test_a_person_who_cannot_be_named_gets_a_fallback_phrase(self):
        """Never a blank gap and never a bare id: each renderer has its own
        wording for the person it could not resolve."""
        missing = {"requestId": _MISSING_ID}

        _, requested = await self._render(UserEvent.BLOCK_REQUESTED, missing)
        _, reassigned = await self._render(UserEvent.BLOCK_REQUEST_REASSIGNED, missing)
        _, decided = await self._render(UserEvent.BLOCK_REQUEST_DECIDED, missing)

        self.assertIn("a colleague has asked you", requested)
        self.assertIn("is now with someone else", reassigned)
        self.assertIn("an administrator has rejected", decided)

    async def test_an_unresolvable_target_is_named_generically(self):
        """The subject id is not a foreign key, and the account it points at
        can be gone by the time this renders."""
        event = EventEntity(
            subject_type=USER_SUBJECT_TYPE,
            subject_id=_MISSING_ID,
            actor_id=self.raiser.user_id,
            event_type=UserEvent.BLOCK_REQUESTED,
            details={"requestId": self.request.request_id},
        )
        await self.insert_entities([event])

        _, orphaned = await render_registry.render(self.session, event)

        self.assertIn("whether a user should be blocked", orphaned)

    # -- shared shape -------------------------------------------------------

    async def test_every_body_ends_with_the_automated_footer(self):
        """Each renderer appends the footer itself; nothing downstream adds
        one, so a renderer that skipped it would send a body without it and
        nothing else would notice."""
        bodies = [
            (await self._render(UserEvent.BLOCK_REQUESTED))[1],
            (await self._render(UserEvent.BLOCK_REQUEST_REASSIGNED))[1],
            (
                await self._render(
                    UserEvent.BLOCK_REQUEST_DECIDED,
                    {"requestId": self.request.request_id, "approved": True},
                )
            )[1],
        ]

        for body in bodies:
            with self.subTest(body=body[:40]):
                self.assertTrue(body.endswith(_FOOTER))


class RegistrationCoverageTest(unittest.TestCase):
    """Every user-subject event that picks recipients must also render.

    A recipient with no renderer is silent non-delivery: the notification row
    is written and published, then delivery fails with a LookupError forever.
    """

    def test_every_notifying_user_event_type_has_a_renderer(self):
        notifying = {
            event_type
            for event_type in recipient_registry._RESOLVERS
            if event_type.startswith("user.")
        }
        self.assertEqual(notifying - set(render_registry._RENDERERS), set())

    def test_no_user_renderer_is_registered_for_an_event_that_notifies_nobody(self):
        """The four state-change events (user.blocked and friends) reach
        nobody by design, so a renderer for one would be dead code."""
        notifying = {
            event_type
            for event_type in recipient_registry._RESOLVERS
            if event_type.startswith("user.")
        }
        registered = {
            event_type
            for event_type in render_registry._RENDERERS
            if event_type.startswith("user.")
        }
        self.assertEqual(registered - notifying, set())


if __name__ == "__main__":
    unittest.main()
