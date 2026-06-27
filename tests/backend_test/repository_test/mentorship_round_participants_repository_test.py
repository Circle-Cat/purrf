import unittest
from datetime import datetime, timezone

from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.common.mentorship_enums import (
    ApprovalStatus,
    CommunicationMethod,
    MenteeActionStatus,
    MentorActionStatus,
    PairStatus,
    ParticipantRole,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestMentorshipRoundParticipantsRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = MentorshipRoundParticipantsRepository()

        self.user = UsersEntity(
            first_name="Alice",
            last_name="Admin",
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email="alice@example.com",
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

        await self.insert_entities([self.user])

        self.rounds = [
            MentorshipRoundEntity(
                name="2025-spring",
                mentee_average_score=4.3,
                mentor_average_score=4.5,
                expectations="improving mentee's ability",
                description={
                    "goal": "basic skills",
                    "meetings_completion_deadline_at": "2025-06-30T00:00:00+00:00",
                },
                required_meetings=5,
            ),
            MentorshipRoundEntity(
                name="2025-fall",
                mentee_average_score=4.8,
                mentor_average_score=4.6,
                expectations="guiding career development paths",
                description={
                    "goal": "career planning",
                    "meetings_completion_deadline_at": "2025-12-31T00:00:00+00:00",
                },
                required_meetings=5,
            ),
        ]

        await self.insert_entities(self.rounds)

    def _make_user(
        self, *, first_name="Test", last_name="User", email, preferred_name=None
    ):
        return UsersEntity(
            first_name=first_name,
            last_name=last_name,
            preferred_name=preferred_name,
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email=email,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

    async def test_get_by_user_id_and_round_id(self):
        """Test retrieve a mentorship round participants entity."""
        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[1].round_id,
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[0].round_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, self.user.user_id)
        self.assertEqual(result.round_id, self.rounds[0].round_id)

    async def test_get_by_user_id_and_round_id_empty(self):
        """Test retrieve none when the participants table is empty."""
        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[0].round_id
        )

        self.assertIsNone(result)

    async def test_get_by_user_id_and_round_id_not_found(self):
        """Test retrieve none when participants exist but none match the given IDs."""
        participant = MentorshipRoundParticipantsEntity(
            user_id=self.user.user_id,
            round_id=self.rounds[0].round_id,
        )
        await self.insert_entities([participant])

        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[1].round_id
        )

        self.assertIsNone(result)

    async def test_get_recent_participant_by_user_id(self):
        """Ensure the participant in the round with the latest meetings_completion_deadline_at is returned."""
        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[1].round_id,
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_recent_participant_by_user_id(
            self.session, user_id=self.user.user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.round_id, self.rounds[1].round_id)

    async def test_get_recent_participant_by_user_id_empty(self):
        """Should return None if the user has no participant records."""
        result = await self.repo.get_recent_participant_by_user_id(
            self.session, user_id=self.user.user_id
        )

        self.assertIsNone(result)

    async def test_upsert_participant_insert(self):
        """Test insert a new participant entity correctly."""
        participant = MentorshipRoundParticipantsEntity(
            user_id=self.user.user_id,
            round_id=self.rounds[1].round_id,
        )

        result = await self.repo.upsert_participant(self.session, participant)

        self.assertIsNotNone(result.participant_id)
        self.assertEqual(result.user_id, self.user.user_id)
        self.assertEqual(result.round_id, self.rounds[1].round_id)

    async def test_get_average_program_rating_by_round_and_role(self):
        """Returns the average program_rating across all matching participants."""
        user2 = self._make_user(
            first_name="Bob", last_name="Builder", email="bob@example.com"
        )
        await self.insert_entities([user2])

        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"program_rating": 4},
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"program_rating": 2},
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_average_program_rating_by_round_and_role(
            self.session,
            round_id=self.rounds[0].round_id,
            role=ParticipantRole.MENTEE,
        )

        self.assertAlmostEqual(result, 3.0)

    async def test_get_average_program_rating_excludes_other_role(self):
        """Does not include participants with a different role in the average."""
        user2 = self._make_user(
            first_name="Carol", last_name="Coach", email="carol@example.com"
        )
        await self.insert_entities([user2])

        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"program_rating": 5},
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
                program_feedback={"program_rating": 1},
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_average_program_rating_by_round_and_role(
            self.session,
            round_id=self.rounds[0].round_id,
            role=ParticipantRole.MENTEE,
        )

        self.assertAlmostEqual(result, 5.0)

    async def test_get_average_program_rating_excludes_null_ratings(self):
        """Skips participants whose program_feedback has no program_rating key."""
        user2 = self._make_user(
            first_name="Dave", last_name="Doe", email="dave@example.com"
        )
        await self.insert_entities([user2])

        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"program_rating": 4},
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                program_feedback={"most_valuable_aspects": "networking"},
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_average_program_rating_by_round_and_role(
            self.session,
            round_id=self.rounds[0].round_id,
            role=ParticipantRole.MENTEE,
        )

        self.assertAlmostEqual(result, 4.0)

    async def test_get_average_program_rating_returns_none_when_no_ratings(self):
        """Returns None when no participants in the round/role have submitted a rating."""
        result = await self.repo.get_average_program_rating_by_round_and_role(
            self.session,
            round_id=self.rounds[0].round_id,
            role=ParticipantRole.MENTEE,
        )

        self.assertIsNone(result)

    async def test_upsert_participant_update(self):
        """Test update an existing participant entity correctly."""
        old_participant = MentorshipRoundParticipantsEntity(
            user_id=self.user.user_id,
            round_id=self.rounds[0].round_id,
            match_email_sent=False,
            expected_partner_user_id=[],
            goal="",
        )
        await self.insert_entities([old_participant])

        participant = MentorshipRoundParticipantsEntity(
            participant_id=old_participant.participant_id,
            user_id=self.user.user_id,
            round_id=self.rounds[0].round_id,
            match_email_sent=True,
            expected_partner_user_id=[456],
            goal="New goal",
        )

        result = await self.repo.upsert_participant(self.session, participant)

        self.assertEqual(result.participant_id, old_participant.participant_id)
        self.assertTrue(result.match_email_sent)
        self.assertEqual(
            result.expected_partner_user_id, participant.expected_partner_user_id
        )
        self.assertEqual(result.goal, participant.goal)

    async def test_search_no_filters_returns_all_users(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])

        rows, total = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=50, offset=0
        )

        self.assertEqual(total, 2)
        user_ids = {r.user_id for r in rows}
        self.assertIn(self.user.user_id, user_ids)
        self.assertIn(user2.user_id, user_ids)

    async def test_search_filter_by_user_id(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_name(self):
        alice = self.user
        bob_jones = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        rosalie_wu = self._make_user(
            first_name="Tina",
            last_name="Wu",
            email="tina@example.com",
            preferred_name="Rosalie Wu",
        )
        await self.insert_entities([bob_jones, rosalie_wu])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(name="ali"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 2)
        user_ids = {r.user_id for r in rows}
        self.assertIn(alice.user_id, user_ids)
        self.assertIn(rosalie_wu.user_id, user_ids)
        self.assertNotIn(bob_jones.user_id, user_ids)

    async def test_search_filter_by_email(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="alice@work.com",
                otp_confirmed=True,
                is_primary=True,
            )
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(email="alice@work"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_round_id(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[1].round_id,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(round_id=self.rounds[0].round_id),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_participant_role(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(participant_role=ParticipantRole.MENTOR),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_approval_status(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                approval_status=ApprovalStatus.MATCHED,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                approval_status=ApprovalStatus.SIGNED_UP,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(approval_status=ApprovalStatus.MATCHED),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_participation_status_participant(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(participation_status="participant"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_filter_by_participation_status_non_participant(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(participation_status="non_participant"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, user2.user_id)

    async def test_search_filter_by_matched_user(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
                approval_status=ApprovalStatus.MATCHED,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.MATCHED,
            ),
        ])
        await self.insert_entities([
            MentorshipPairsEntity(
                round_id=self.rounds[0].round_id,
                mentor_id=self.user.user_id,
                mentee_id=user2.user_id,
                completed_count=0,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="test",
            )
        ])

        rows, total = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(matched_user="jones"),
            limit=50,
            offset=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(rows[0].user_id, self.user.user_id)

    async def test_search_pagination(self):
        extra_users = [
            self._make_user(
                first_name=f"User{i}", last_name="Test", email=f"user{i}@example.com"
            )
            for i in range(3)
        ]
        await self.insert_entities(extra_users)

        rows_p1, total = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=2, offset=0
        )
        rows_p2, _ = await self.repo.search_participants_for_admin(
            self.session, ParticipantSearchFilterDto(), limit=2, offset=2
        )

        self.assertEqual(total, 4)
        self.assertEqual(len(rows_p1), 2)
        self.assertEqual(len(rows_p2), 2)
        self.assertEqual(
            len({r.user_id for r in rows_p1} & {r.user_id for r in rows_p2}), 0
        )

    async def test_search_row_fields_for_paired_participant(self):
        user2 = self._make_user(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        await self.insert_entities([user2])
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTOR,
                approval_status=ApprovalStatus.MATCHED,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user2.user_id,
                round_id=self.rounds[0].round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=ApprovalStatus.MATCHED,
            ),
        ])
        pair = MentorshipPairsEntity(
            round_id=self.rounds[0].round_id,
            mentor_id=self.user.user_id,
            mentee_id=user2.user_id,
            completed_count=2,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.CONFIRMED,
            mentee_action_status=MenteeActionStatus.CONFIRMED,
            recommendation_reason="test",
        )
        await self.insert_entities([pair])

        rows, _ = await self.repo.search_participants_for_admin(
            self.session,
            ParticipantSearchFilterDto(user_id=self.user.user_id),
            limit=50,
            offset=0,
        )

        row = rows[0]
        self.assertEqual(row.round_id, self.rounds[0].round_id)
        self.assertEqual(row.pair_id, pair.pair_id)
        self.assertEqual(row.participant_role, ParticipantRole.MENTOR)
        self.assertEqual(row.approval_status, ApprovalStatus.MATCHED)
        self.assertEqual(row.completed_count, 2)
        self.assertEqual(row.mentor_id, self.user.user_id)
        self.assertEqual(row.mentee_id, user2.user_id)


if __name__ == "__main__":
    unittest.main()
