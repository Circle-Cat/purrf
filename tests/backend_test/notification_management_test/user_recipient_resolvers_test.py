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
from backend.notification_management.recipient_registry import resolve_recipients
from backend.user_identity import user_recipient_resolvers  # noqa: F401  (registers)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


def _event(event_type, subject_id, details=None, subject_type=USER_SUBJECT_TYPE):
    return EventEntity(
        subject_type=subject_type,
        subject_id=subject_id,
        actor_id=0,
        event_type=event_type,
        details=details or {},
    )


class TestUserRecipientResolvers(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.target = _make_user()
        self.raiser = _make_user()
        self.reviewer = _make_user()
        self.other_admin = _make_user()
        self.admin = _make_user()
        await self.insert_entities([
            self.target,
            self.raiser,
            self.reviewer,
            self.other_admin,
            self.admin,
        ])

        self.request = BlockRequestEntity(
            target_user_id=self.target.user_id,
            raised_by=self.raiser.user_id,
            raised_from="recruiting_board",
            reason="second no-show",
            reviewer_id=self.reviewer.user_id,
            status=BlockRequestStatus.PENDING,
        )
        await self.insert_entities([self.request])

    async def test_block_requested_reaches_only_the_named_reviewer(self):
        event = _event(
            UserEvent.BLOCK_REQUESTED,
            self.target.user_id,
            {"requestId": self.request.request_id},
        )

        self.assertEqual(
            await resolve_recipients(self.session, event), {self.reviewer.user_id}
        )

    async def test_reassigned_reaches_both_reviewers(self):
        self.request.reviewer_id = self.other_admin.user_id
        await self.session.flush()
        event = _event(
            UserEvent.BLOCK_REQUEST_REASSIGNED,
            self.target.user_id,
            {
                "requestId": self.request.request_id,
                "previousReviewerId": self.reviewer.user_id,
            },
        )

        self.assertEqual(
            await resolve_recipients(self.session, event),
            {self.other_admin.user_id, self.reviewer.user_id},
        )

    async def test_reassigned_without_a_previous_reviewer_reaches_the_new_one(self):
        event = _event(
            UserEvent.BLOCK_REQUEST_REASSIGNED,
            self.target.user_id,
            {"requestId": self.request.request_id},
        )

        self.assertEqual(
            await resolve_recipients(self.session, event), {self.reviewer.user_id}
        )

    async def test_decided_reaches_only_the_raiser(self):
        event = _event(
            UserEvent.BLOCK_REQUEST_DECIDED,
            self.target.user_id,
            {"requestId": self.request.request_id},
        )

        self.assertEqual(
            await resolve_recipients(self.session, event), {self.raiser.user_id}
        )

    async def test_state_change_events_notify_nobody(self):
        """Timeline only. The target is never told: blocking deliberately
        discloses no reason, and deactivation is by definition what the user
        themselves asked for."""
        for event_type in (
            UserEvent.BLOCKED,
            UserEvent.UNBLOCKED,
            UserEvent.DEACTIVATED,
            UserEvent.REACTIVATED,
        ):
            with self.subTest(event_type=event_type):
                event = _event(event_type, self.target.user_id, {})
                self.assertEqual(await resolve_recipients(self.session, event), set())

    async def test_target_is_never_a_recipient(self):
        for event_type in (
            UserEvent.BLOCK_REQUESTED,
            UserEvent.BLOCK_REQUEST_REASSIGNED,
            UserEvent.BLOCK_REQUEST_DECIDED,
        ):
            with self.subTest(event_type=event_type):
                event = _event(
                    event_type,
                    self.target.user_id,
                    {
                        "requestId": self.request.request_id,
                        "previousReviewerId": self.reviewer.user_id,
                    },
                )
                self.assertNotIn(
                    self.target.user_id,
                    await resolve_recipients(self.session, event),
                )

    async def test_wrong_subject_type_raises(self):
        """A user-subject resolver reading an application id would silently
        resolve an unrelated row's owners -- the registry raises instead."""
        event = _event(
            UserEvent.BLOCK_REQUESTED,
            self.request.request_id,
            {"requestId": self.request.request_id},
            subject_type="application",
        )

        with self.assertRaises(ValueError):
            await resolve_recipients(self.session, event)

    async def test_missing_request_id_raises(self):
        """A write site that spells the key differently would otherwise notify
        nobody, with no exception and no log."""
        event = _event(UserEvent.BLOCK_REQUESTED, self.target.user_id, {})

        with self.assertRaises(ValueError):
            await resolve_recipients(self.session, event)

    async def test_unknown_request_id_raises(self):
        event = _event(
            UserEvent.BLOCK_REQUESTED, self.target.user_id, {"requestId": 9_999_999}
        )

        with self.assertRaises(ValueError):
            await resolve_recipients(self.session, event)


if __name__ == "__main__":
    unittest.main()
