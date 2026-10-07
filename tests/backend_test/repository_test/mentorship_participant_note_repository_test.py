import unittest
import uuid
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod, ParticipantNoteTag
from backend.entity.mentorship_round_entity import MentorshipRoundEntity

# Imported for their side effect only: a note's pair_id and request_id point
# at these tables, and SQLAlchemy cannot configure the note mapper until they
# are in the registry. Production imports every entity at startup.
from backend.entity.approval_request_entity import ApprovalRequestEntity  # noqa: F401
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity  # noqa: F401
from backend.entity.users_entity import UsersEntity
from backend.repository.mentorship_participant_note_repository import (
    MentorshipParticipantNoteRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestMentorshipParticipantNoteRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = MentorshipParticipantNoteRepository()
        self.person = self._make_user()
        self.other_person = self._make_user()
        self.author = self._make_user()
        await self.insert_entities([self.person, self.other_person, self.author])
        self.round = MentorshipRoundEntity(
            name="2026-spring",
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        self.other_round = MentorshipRoundEntity(
            name="2026-fall",
            required_meetings=6,
            onboarding_deadline_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        )
        await self.insert_entities([self.round, self.other_round])

    def _make_user(self):
        return UsersEntity(
            first_name="T",
            last_name=uuid.uuid4().hex[:10],
            timezone="UTC",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

    async def test_create_a_plain_remark(self):
        row = await self.repo.create(
            self.session,
            user_id=self.person.user_id,
            round_id=self.round.round_id,
            author_user_id=self.author.user_id,
            body="Asked to be paired with someone in data science.",
        )

        self.assertIsNotNone(row.note_id)
        self.assertIsNone(row.tag)
        self.assertIsNone(row.pair_id)
        self.assertIsNone(row.request_id)
        self.assertIsNotNone(row.created_at)

    async def test_create_a_tagged_mark(self):
        row = await self.repo.create(
            self.session,
            user_id=self.person.user_id,
            round_id=self.round.round_id,
            author_user_id=self.author.user_id,
            body="signed_up -> matched",
            tag=ParticipantNoteTag.STATUS_CHANGE,
        )

        self.assertIs(row.tag, ParticipantNoteTag.STATUS_CHANGE)

    async def test_list_for_user_round_is_scoped_and_oldest_first(self):
        first = await self.repo.create(
            self.session,
            user_id=self.person.user_id,
            round_id=self.round.round_id,
            author_user_id=self.author.user_id,
            body="first",
        )
        second = await self.repo.create(
            self.session,
            user_id=self.person.user_id,
            round_id=self.round.round_id,
            author_user_id=self.author.user_id,
            body="second",
            tag=ParticipantNoteTag.MATCHING_EXEMPTION,
        )
        await self.repo.create(
            self.session,
            user_id=self.person.user_id,
            round_id=self.other_round.round_id,
            author_user_id=self.author.user_id,
            body="other round",
        )
        await self.repo.create(
            self.session,
            user_id=self.other_person.user_id,
            round_id=self.round.round_id,
            author_user_id=self.author.user_id,
            body="other person",
        )

        rows = await self.repo.list_for_user_round(
            self.session, self.person.user_id, self.round.round_id
        )

        self.assertEqual([r.note_id for r in rows], [first.note_id, second.note_id])


if __name__ == "__main__":
    unittest.main()
