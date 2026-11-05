"""Marking people notified by hand, against a real database.

Mia, Ann and Bo are registered for the round in progress; Kit already sent
Bo the match result. Cy is not registered. Every id and name differs, so a
read from the wrong person or stage shows up."""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from sqlalchemy import select

from backend.common.mentorship_email_enums import (
    MentorshipEmailRecipientResult as R,
    MentorshipEmailSendStatus as S,
    MentorshipEmailStage as Stage,
)
from backend.common.mentorship_enums import (
    ApprovalStatus,
    CommunicationMethod,
    ParticipantNoteTag,
    ParticipantRole,
)
from backend.entity.approval_request_entity import ApprovalRequestEntity  # noqa: F401
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity  # noqa: F401
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.training_course_entity import TrainingCourseEntity  # noqa: F401
from backend.entity.users_entity import UsersEntity
from backend.mentorship.mentorship_email_service import MentorshipEmailService
from backend.mentorship.notification_mark_service import NotificationMarkService
from backend.repository.mentorship_email_repository import MentorshipEmailRepository
from backend.repository.mentorship_participant_note_repository import (
    MentorshipParticipantNoteRepository,
)
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.users_repository import UsersRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

BODY = "Sent on Teams, 10-10."


def _user(first):
    return UsersEntity(
        first_name=first,
        last_name=uuid.uuid4().hex[:8],
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class NotificationMarkFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        now = datetime.now(timezone.utc)
        self.admin = _user("Ada")
        self.mia = _user("Mia")
        self.ann = _user("Ann")
        self.bo = _user("Bo")
        self.cy = _user("Cy")
        await self.insert_entities([self.admin, self.mia, self.ann, self.bo, self.cy])
        self.round = MentorshipRoundEntity(
            name="Spring 2026",
            required_meetings=4,
            promotion_start_at=now - timedelta(days=10),
            onboarding_deadline_at=now + timedelta(days=10),
            meetings_completion_deadline_at=now + timedelta(days=80),
            feedback_deadline_at=now + timedelta(days=100),
        )
        await self.insert_entities([self.round])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=user.user_id,
                round_id=self.round.round_id,
                participant_role=role,
                approval_status=ApprovalStatus.MATCHED,
                max_partners=1,
            )
            for user, role in (
                (self.mia, ParticipantRole.MENTOR),
                (self.ann, ParticipantRole.MENTEE),
                (self.bo, ParticipantRole.MENTEE),
            )
        ])
        self.email_repo = MentorshipEmailRepository()
        send = await self.email_repo.create_send(
            self.session,
            round_id=self.round.round_id,
            stage="match_result",
            kit_draft_id=11,
            kit_draft_subject="Your match",
            created_by=self.admin.user_id,
            sender_address="notification-test@circlecat.org",
            kit_tag_name="purrf · Spring 2026 · Match result",
            kit_tag_id=7,
            kit_broadcast_id=9,
            recipients=[(self.bo.user_id, "bo@x.org")],
        )
        send.status = S.SENT
        for row in await self.email_repo.list_recipients(self.session, send.send_id):
            row.result = R.HANDED_TO_KIT
        await self.session.flush()
        self.notes = MentorshipParticipantNoteRepository()
        rounds = MentorshipRoundRepository()
        self.marker = NotificationMarkService(
            note_repository=self.notes,
            participants_repository=MentorshipRoundParticipantsRepository(),
            rounds_repository=rounds,
            users_repository=UsersRepository(),
            mentorship_email_repository=self.email_repo,
            logger=MagicMock(),
        )
        self.email = MentorshipEmailService(
            mentorship_email_repository=self.email_repo,
            user_emails_repository=MagicMock(),
            mentorship_round_repository=rounds,
            kit_client=MagicMock(),
            sender_address=None,
            logger=MagicMock(),
        )

    async def _mark(self, people, stage=Stage.MATCH_RESULT):
        return await self.marker.mark(
            self.session,
            round_id=self.round.round_id,
            user_ids=[p.user_id for p in people],
            stage=stage,
            body=BODY,
            actor_id=self.admin.user_id,
        )

    async def _notes_on(self, person):
        return await self.notes.list_for_user_round(
            self.session, person.user_id, self.round.round_id
        )

    async def _ids(self, stage, **flags):
        query = await self.email.notified_user_ids(
            self.session, self.round.round_id, stage, **flags
        )
        rows = await self.session.execute(
            select(UsersEntity.user_id)
            .where(UsersEntity.user_id.in_(query))
            .order_by(UsersEntity.user_id)
        )
        return list(rows.scalars())

    async def test_marking_a_mixed_batch_notes_only_the_rest(self):
        result = await self._mark([self.mia, self.ann, self.bo, self.cy])

        self.assertEqual(result.marked, [self.mia.user_id, self.ann.user_id])
        self.assertEqual(
            [(s.user_id, s.reason) for s in result.skipped],
            [(self.bo.user_id, "already_notified"), (self.cy.user_id, "not_offered")],
        )
        for person in (self.mia, self.ann):
            self.assertEqual(
                [
                    (n.tag, n.notification_stage, n.body, n.author_user_id)
                    for n in await self._notes_on(person)
                ],
                [
                    (
                        ParticipantNoteTag.NOTIFIED,
                        "match_result",
                        BODY,
                        self.admin.user_id,
                    )
                ],
            )
        self.assertEqual(await self._notes_on(self.bo), [])
        self.assertEqual(await self._notes_on(self.cy), [])

        again = await self._mark([self.mia, self.ann])
        self.assertEqual(again.marked, [])
        self.assertEqual(
            [s.reason for s in again.skipped], ["already_notified", "already_notified"]
        )

    async def test_marked_people_count_as_notified_in_the_list_and_the_filter(self):
        await self._mark([self.ann])

        notified, _ = await self.email.list_notified(self.session, self.round.round_id)
        self.assertEqual(
            {n.user_id: (n.stages, n.manual) for n in notified},
            {
                self.ann.user_id: ([], ["match_result"]),
                self.bo.user_id: (["match_result"], []),
            },
        )
        self.assertEqual(
            await self._ids(Stage.MATCH_RESULT, sent=True, scheduled=False),
            sorted([self.ann.user_id, self.bo.user_id]),
        )
        self.assertEqual(
            await self._ids(Stage.MATCH_RESULT, sent=False, scheduled=True), []
        )
        reached = await self._ids(Stage.MATCH_RESULT, sent=True, scheduled=True)
        self.assertEqual(
            [p.user_id for p in (self.mia, self.cy) if p.user_id not in reached],
            [self.mia.user_id, self.cy.user_id],
        )
        self.assertEqual(
            await self._ids(Stage.MIDTERM_REMINDER, sent=True, scheduled=False), []
        )


if __name__ == "__main__":
    unittest.main()
