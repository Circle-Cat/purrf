import uuid
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from backend.mentorship.participation_service import ParticipationService
from backend.common.exceptions import ConflictError
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_dto import RoundPreferencesDto
from backend.dto.feedback_create_dto import FeedbackCreateDto
from backend.dto.feedback_dto import FeedbackDto
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.common.mentorship_enums import (
    ParticipantRole,
    ApprovalStatus,
    MatchStatus,
    PairStatus,
)
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity


class TestParticipationService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_all_by_ids = AsyncMock()

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_all_partner_ids = AsyncMock()
        self.mock_pairs_repo.get_pairs_with_partner_info = AsyncMock()

        self.mock_round_participants_repo = MagicMock()
        self.mock_round_participants_repo.get_recent_participant_by_user_id = (
            AsyncMock()
        )
        self.mock_round_participants_repo.get_recent_participant_by_user_id_and_role = (
            AsyncMock()
        )
        self.mock_round_participants_repo.get_by_user_id_and_round_id = AsyncMock()
        self.mock_round_participants_repo.upsert_participant = AsyncMock()
        self.mock_round_participants_repo.get_average_program_rating_by_round_and_role = AsyncMock(
            return_value=4.0
        )

        self.mock_round_repo = MagicMock()
        self.mock_round_repo.update_mentee_average_score = AsyncMock()
        self.mock_round_repo.update_mentor_average_score = AsyncMock()
        # A round with no configured deadlines leaves feedback open.
        self.mock_round_repo.get_by_round_id = AsyncMock(
            return_value=MentorshipRoundEntity(
                round_id=1,
                name="round",
                onboarding_deadline_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )

        self.mock_session = AsyncMock()
        self.mock_mapper = MagicMock()
        self.logger = MagicMock()

        self.mock_user_emails_repo = MagicMock()
        # Partner emails come from user_emails, not the legacy column.
        self.mock_user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={456: "partner@example.com"}
        )

        self.participation_service = ParticipationService(
            logger=self.logger,
            users_repository=self.mock_users_repo,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_round_participants_repo=self.mock_round_participants_repo,
            mentorship_round_repository=self.mock_round_repo,
            mentorship_mapper=self.mock_mapper,
            user_emails_repository=self.mock_user_emails_repo,
        )

        self.mock_users_entities = [
            MagicMock(
                spec=UsersEntity,
                user_id=456,
                first_name="Bob",
                last_name="Smith",
                preferred_name="Bob Smith",
            ),
            MagicMock(
                spec=UsersEntity,
                user_id=789,
                first_name="Carol",
                last_name="Jones",
                preferred_name="Carol Jones",
            ),
        ]

        self.mock_all_round_partner_ids = [456, 789]

        self.mock_specific_partner_user = MagicMock(
            spec=UsersEntity,
            user_id=456,
            first_name="Alice",
            last_name="Smith",
            preferred_name="Alice Smith",
        )

        self.user_context = MagicMock(
            spec=UserContextDto,
            sub=str(uuid.uuid4()),
            identity_type="internal",
            user_id=123,
        )

    async def test_get_partners_for_user_full(self):
        """Test retrieve and map partners for a user with user context and round id."""
        mock_round_id = 1

        mock_pair = MagicMock(spec=MentorshipPairsEntity, status=PairStatus.ACTIVE)
        self.mock_pairs_repo.get_pairs_with_partner_info.return_value = [
            (mock_pair, self.mock_specific_partner_user)
        ]
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            MagicMock(
                spec=MentorshipRoundParticipantsEntity,
                approval_status=ApprovalStatus.MATCHED,
            )
        )

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(result[0].primary_email, "partner@example.com")
        self.mock_pairs_repo.get_pairs_with_partner_info.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
        )
        self.mock_pairs_repo.get_all_partner_ids.assert_not_awaited()
        self.mock_session.commit.assert_not_awaited()

    async def test_get_partners_for_user_reads_contact_email_for_live_pairs_only(self):
        """A partner whose pair has ended is listed without a contact email.

        Both counterparts come back -- an ended pairing is still the user's
        participation -- but only the live one is looked up in user_emails, so
        the ended partner's contact row is never read.
        """
        mock_round_id = 1

        live_pair = MagicMock(spec=MentorshipPairsEntity, status=PairStatus.ACTIVE)
        ended_pair = MagicMock(spec=MentorshipPairsEntity, status=PairStatus.INACTIVE)
        ended_partner = MagicMock(
            spec=UsersEntity,
            user_id=789,
            first_name="Carol",
            last_name="Jones",
            preferred_name=None,
        )
        self.mock_pairs_repo.get_pairs_with_partner_info.return_value = [
            (live_pair, self.mock_specific_partner_user),
            (ended_pair, ended_partner),
        ]
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            MagicMock(
                spec=MentorshipRoundParticipantsEntity,
                approval_status=ApprovalStatus.MATCHED,
            )
        )

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.mock_user_emails_repo.get_contact_emails_by_user_ids.assert_awaited_once_with(
            self.mock_session, [self.mock_specific_partner_user.user_id]
        )
        self.assertEqual(result[0].primary_email, "partner@example.com")
        self.assertTrue(result[0].is_active)
        self.assertIsNone(result[1].primary_email)
        self.assertFalse(result[1].is_active)

    async def test_get_partners_for_user_keeps_the_partner_of_an_ended_pair(self):
        """A pairing that ended is still this user's participation in the round.

        Pair status says whether the counterpart is the current one, not
        whether the user took part, so the ended pairing comes back marked
        rather than dropped -- dropping it leaves a user whose partner quit
        with an empty partner list and no way to tell they participated at
        all. Their contact email is not offered: the pairing is over.
        """
        mock_round_id = 1

        ended_pair = MagicMock(spec=MentorshipPairsEntity, status=PairStatus.INACTIVE)
        self.mock_pairs_repo.get_pairs_with_partner_info.return_value = [
            (ended_pair, self.mock_specific_partner_user)
        ]
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            MagicMock(
                spec=MentorshipRoundParticipantsEntity,
                approval_status=ApprovalStatus.MATCHED,
            )
        )

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, self.mock_specific_partner_user.user_id)
        self.assertFalse(result[0].is_active)
        self.assertIsNone(result[0].primary_email)
        self.mock_user_emails_repo.get_contact_emails_by_user_ids.assert_not_awaited()
        # The round's pairs are asked for whole: narrowing the query to the
        # live ones is what made an ended pairing vanish.
        self.mock_pairs_repo.get_pairs_with_partner_info.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
        )

    async def test_get_partners_for_user_excludes_partner_email_without_participant(
        self,
    ):
        """Test that primary_email is None when participant record does not exist."""
        mock_round_id = 1

        mock_pair = MagicMock(spec=MentorshipPairsEntity, status=PairStatus.ACTIVE)
        self.mock_pairs_repo.get_pairs_with_partner_info.return_value = [
            (mock_pair, self.mock_specific_partner_user)
        ]
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertIsNone(result[0].primary_email)

    async def test_get_partners_for_user_without_round_id(self):
        """Test retrieve and map partners for a user without round id."""
        self.mock_pairs_repo.get_all_partner_ids.return_value = (
            self.mock_all_round_partner_ids
        )
        self.mock_users_repo.get_all_by_ids.return_value = self.mock_users_entities

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session, user_context=self.user_context
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, self.mock_users_entities[0].user_id)
        self.assertEqual(result[1].id, self.mock_users_entities[1].user_id)
        self.assertIsNone(result[0].primary_email)
        self.assertIsNone(result[1].primary_email)

        self.mock_pairs_repo.get_all_partner_ids.assert_awaited_once_with(
            session=self.mock_session, user_id=self.user_context.user_id
        )
        self.mock_pairs_repo.get_pairs_with_partner_info.assert_not_awaited()

        self.mock_users_repo.get_all_by_ids.assert_awaited_once_with(
            session=self.mock_session, user_ids=self.mock_all_round_partner_ids
        )

        self.mock_session.commit.assert_not_awaited()

    async def test_get_partners_for_user_no_partners_found(self):
        """Test returns empty list when user exists but has no partners."""
        self.mock_pairs_repo.get_all_partner_ids.return_value = []

        result = await self.participation_service.get_partners_for_user(
            session=self.mock_session, user_context=self.user_context
        )

        self.assertEqual(result, [])
        self.mock_session.commit.assert_not_awaited()
        self.mock_users_repo.get_all_by_ids.assert_not_awaited()

    async def test_get_user_round_preferences_found_current(self):
        """Returns preferences from the current round if record exists."""
        mock_round_id = 1
        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.participant_role = ParticipantRole.MENTOR
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )

        expected_dto = RoundPreferencesDto(
            participant_role=ParticipantRole.MENTOR,
            expected_partner_ids=[456],
            unexpected_partner_ids=[],
            max_partners=1,
            goal="I want to share my project management skills",
        )

        self.mock_mapper.map_to_round_preference_dto.return_value = expected_dto

        (
            result,
            is_registered,
        ) = await self.participation_service.get_user_round_preferences(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
            participant_role=ParticipantRole.MENTOR,
        )

        self.assertEqual(result, expected_dto)
        self.assertEqual(is_registered, True)
        self.assertEqual(result.participant_role, ParticipantRole.MENTOR)

        self.mock_round_participants_repo.get_by_user_id_and_round_id.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
        )
        # An already-registered round short-circuits: no same-role carry-over lookup.
        self.mock_round_participants_repo.get_recent_participant_by_user_id_and_role.assert_not_awaited()
        self.mock_mapper.map_to_round_preference_dto.assert_called_once_with(
            participants_entity=mock_participant
        )

    async def test_get_user_round_preferences_carries_over_same_role_round(self):
        """When not registered, pre-fills from the most recent prior round in
        the SAME role supplied by the caller."""
        mock_round_id = 1
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )
        mock_recent = MagicMock(spec=MentorshipRoundParticipantsEntity)
        self.mock_round_participants_repo.get_recent_participant_by_user_id_and_role.return_value = mock_recent

        historical_dto = RoundPreferencesDto(
            participant_role=ParticipantRole.MENTOR,
            expected_partner_ids=[],
            unexpected_partner_ids=[],
            max_partners=1,
            goal="Historical Goal",
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = historical_dto

        (
            result,
            is_registered,
        ) = await self.participation_service.get_user_round_preferences(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
            participant_role=ParticipantRole.MENTOR,
        )

        self.assertEqual(result, historical_dto)
        self.assertEqual(is_registered, False)
        self.mock_round_participants_repo.get_by_user_id_and_round_id.assert_awaited_once()
        self.mock_round_participants_repo.get_recent_participant_by_user_id_and_role.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            participant_role=ParticipantRole.MENTOR,
        )
        self.mock_mapper.map_to_round_preference_dto.assert_called_once_with(
            participants_entity=mock_recent
        )

    async def test_get_user_round_preferences_for_new_user(self):
        """Returns empty defaults carrying the supplied role for a user with
        no registration and no prior same-role round."""
        mock_round_id = 1
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )
        self.mock_round_participants_repo.get_recent_participant_by_user_id_and_role.return_value = None

        (
            result,
            is_registered,
        ) = await self.participation_service.get_user_round_preferences(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
            participant_role=ParticipantRole.MENTEE,
        )

        self.assertIsInstance(result, RoundPreferencesDto)
        self.assertEqual(is_registered, False)
        self.assertEqual(result.participant_role, ParticipantRole.MENTEE)
        self.assertEqual(result.expected_partner_ids, [])
        self.assertEqual(result.goal, "")
        self.assertEqual(result.max_partners, 1)

    async def test_registered_row_wins_when_no_role_is_requested(self):
        """The most-trafficked GET case: a registered user asking only "am I
        registered, and as what" (no role named). The row still short-
        circuits and answers with the saved role's preferences, even though
        participant_role is None — this is the case an ordering mutation
        (checking participant_role is None before the row lookup) would
        silently break, since every other row-present test in this file
        supplies a role."""
        mock_round_id = 1
        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.participant_role = ParticipantRole.MENTEE
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )
        expected_dto = RoundPreferencesDto(
            participant_role=ParticipantRole.MENTEE,
            expected_partner_ids=[],
            unexpected_partner_ids=[],
            max_partners=1,
            goal="",
        )
        self.mock_mapper.map_to_round_preference_dto.return_value = expected_dto

        (
            result,
            is_registered,
        ) = await self.participation_service.get_user_round_preferences(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
            participant_role=None,
        )

        self.assertTrue(is_registered)
        self.assertEqual(expected_dto, result)
        self.mock_round_participants_repo.get_recent_participant_by_user_id_and_role.assert_not_awaited()

    async def test_registered_row_conflicts_with_a_different_requested_role(self):
        """A saved registration under a different role than requested is a
        conflict, not a silent correction."""
        mock_round_id = 1
        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.participant_role = ParticipantRole.MENTEE
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )

        with self.assertRaises(ConflictError) as ctx:
            await self.participation_service.get_user_round_preferences(
                session=self.mock_session,
                user_id=self.user_context.user_id,
                round_id=mock_round_id,
                participant_role=ParticipantRole.MENTOR,
            )

        self.assertIn("mentee", str(ctx.exception))

    async def test_no_row_and_no_role_yields_no_preferences(self):
        """With no registration and no role supplied, there is nothing to
        prefill: return None."""
        mock_round_id = 1
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )

        (
            result,
            is_registered,
        ) = await self.participation_service.get_user_round_preferences(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
            participant_role=None,
        )

        self.assertIsNone(result)
        self.assertFalse(is_registered)
        self.mock_round_participants_repo.get_recent_participant_by_user_id_and_role.assert_not_awaited()

    async def test_get_my_match_result_unregistered(self):
        """Test result when user has not registered for the round."""
        mock_round_id = 1
        # Mock participant as None
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )

        result = await self.participation_service.get_my_match_result_by_round_id(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(result.round_id, mock_round_id)
        self.assertEqual(result.current_status, MatchStatus.UNREGISTERED)
        self.assertEqual(len(result.partners), 0)

    async def test_get_my_match_result_not_matched_status(self):
        """A status that cannot have produced a pairing is answered without
        touching the pairs table."""
        mock_round_id = 1

        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.approval_status = ApprovalStatus.UN_MATCHED
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )

        result = await self.participation_service.get_my_match_result_by_round_id(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(result.current_status, MatchStatus.UNMATCHED)
        self.assertEqual(len(result.partners), 0)
        self.mock_pairs_repo.get_pairs_with_partner_info.assert_not_awaited()

    async def test_get_my_match_result_reports_a_pairing_the_user_left(self):
        """Someone who left the round was matched first, and is told so.

        `rejected` is also the status of an application that was turned down,
        and the two read identically without the pairing. Reporting it is what
        lets the answer say which one this is.
        """
        mock_round_id = 1

        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.approval_status = ApprovalStatus.REJECTED
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )
        ended_pair = MagicMock(
            spec=MentorshipPairsEntity,
            status=PairStatus.INACTIVE,
            mentor_id=789,
            mentee_id=123,
            recommendation_reason="Guidance",
        )
        partner = MagicMock(
            spec=UsersEntity,
            user_id=789,
            first_name="Alice",
            last_name="W",
            preferred_name=None,
        )
        self.mock_pairs_repo.get_pairs_with_partner_info.return_value = [
            (ended_pair, partner)
        ]

        result = await self.participation_service.get_my_match_result_by_round_id(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(result.current_status, MatchStatus.REJECTED)
        self.assertEqual(len(result.partners), 1)
        self.assertEqual(result.partners[0].id, 789)
        self.assertFalse(result.partners[0].is_active)
        self.assertIsNone(result.partners[0].primary_email)

    async def test_get_my_match_result_for_an_application_never_accepted(self):
        """No pairing behind a `rejected` status means the application was
        turned down, and the answer stays empty."""
        mock_round_id = 1

        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.approval_status = ApprovalStatus.REJECTED
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )
        self.mock_pairs_repo.get_pairs_with_partner_info.return_value = []

        result = await self.participation_service.get_my_match_result_by_round_id(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(result.current_status, MatchStatus.REJECTED)
        self.assertEqual(len(result.partners), 0)

    async def test_get_my_match_result_success(self):
        """Test successful match result including partner DTO construction."""
        mock_round_id = 1

        # Mock participant status as MATCHED
        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.approval_status = ApprovalStatus.MATCHED
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )

        # Mock pairs data (PairEntity, PartnerUserEntity)
        # Case A: Current user (123) is Mentor, Partner (456) is Mentee
        mock_pair_a = MagicMock(
            spec=MentorshipPairsEntity,
            status=PairStatus.ACTIVE,
            mentor_id=123,
            mentee_id=456,
            recommendation_reason="Expertise",
        )
        mock_partner_a = MagicMock(
            spec=UsersEntity,
            user_id=456,
            first_name="Bob",
            last_name="S",
            preferred_name="Bob",
        )

        # Case B: Current user (123) is Mentee, Partner (789) is Mentor
        mock_pair_b = MagicMock(
            spec=MentorshipPairsEntity,
            status=PairStatus.ACTIVE,
            mentor_id=789,
            mentee_id=123,
            recommendation_reason="Guidance",
        )
        mock_partner_b = MagicMock(
            spec=UsersEntity,
            user_id=789,
            first_name="Alice",
            last_name="W",
            preferred_name="Alice",
        )

        self.mock_pairs_repo.get_pairs_with_partner_info.return_value = [
            (mock_pair_a, mock_partner_a),
            (mock_pair_b, mock_partner_b),
        ]

        result = await self.participation_service.get_my_match_result_by_round_id(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(result.current_status, MatchStatus.MATCHED)
        self.assertEqual(len(result.partners), 2)
        self.assertTrue(all(p.is_active for p in result.partners))

        self.mock_pairs_repo.get_pairs_with_partner_info.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
        )

        # Check Partner A (Mentee)
        partner_a = next(p for p in result.partners if p.id == 456)
        self.assertEqual(partner_a.participant_role, ParticipantRole.MENTEE)
        self.assertEqual(partner_a.recommendation_reason, "Expertise")

        # Check Partner B (Mentor)
        partner_b = next(p for p in result.partners if p.id == 789)
        self.assertEqual(partner_b.participant_role, ParticipantRole.MENTOR)
        self.assertEqual(partner_b.recommendation_reason, "Guidance")

    async def test_get_my_match_result_marks_an_ended_pairing(self):
        """The match result records who this user was matched with.

        A pairing that has since ended is still that record, so it is
        reported and marked rather than left out -- otherwise a matched user
        whose partner quit is told "here is your partner" over an empty list.
        The ended counterpart's contact email is withheld.
        """
        mock_round_id = 1

        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            MagicMock(
                spec=MentorshipRoundParticipantsEntity,
                approval_status=ApprovalStatus.MATCHED,
            )
        )
        ended_pair = MagicMock(
            spec=MentorshipPairsEntity,
            status=PairStatus.INACTIVE,
            mentor_id=789,
            mentee_id=123,
            recommendation_reason="Guidance",
        )
        partner = MagicMock(
            spec=UsersEntity,
            user_id=789,
            first_name="Alice",
            last_name="W",
            preferred_name="Alice",
        )
        self.mock_pairs_repo.get_pairs_with_partner_info.return_value = [
            (ended_pair, partner)
        ]

        result = await self.participation_service.get_my_match_result_by_round_id(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertEqual(result.current_status, MatchStatus.MATCHED)
        self.assertEqual(len(result.partners), 1)
        self.assertEqual(result.partners[0].id, 789)
        self.assertFalse(result.partners[0].is_active)
        self.assertIsNone(result.partners[0].primary_email)
        self.mock_pairs_repo.get_pairs_with_partner_info.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_context.user_id,
            round_id=mock_round_id,
        )

    async def test_get_program_feedback_with_existing_submission(self):
        """Returns has_submitted=True and populates fields when feedback dict exists."""
        mock_round_id = 1

        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.participant_role = ParticipantRole.MENTEE
        mock_participant.program_feedback = {
            "most_valuable_aspects": "networking",
            "challenges": None,
            "program_rating": 5,
        }
        mock_participant.pair_feedback = [
            {"partner_id": 10, "rating": 5, "feedback": "Great mentor"}
        ]
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )

        result = await self.participation_service.get_program_feedback(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertIsInstance(result, FeedbackDto)
        self.assertTrue(result.has_submitted)
        self.assertEqual(result.most_valuable_aspects, "networking")
        self.assertEqual(result.program_rating, 5)
        self.assertEqual(result.participant_role, ParticipantRole.MENTEE)
        self.assertEqual(len(result.partner_feedback), 1)
        self.assertEqual(result.partner_feedback[0].partner_id, 10)
        self.assertEqual(result.partner_feedback[0].rating, 5)
        self.assertEqual(result.partner_feedback[0].feedback, "Great mentor")
        self.logger.debug.assert_called()

    async def test_get_program_feedback_without_submission(self):
        """Returns has_submitted=False and None fields when program_feedback is not a dict."""
        mock_round_id = 1

        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.participant_role = ParticipantRole.MENTOR
        mock_participant.program_feedback = None
        mock_participant.pair_feedback = None
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )

        result = await self.participation_service.get_program_feedback(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
        )

        self.assertFalse(result.has_submitted)
        self.assertIsNone(result.program_rating)
        self.assertEqual(result.partner_feedback, [])

    async def test_get_program_feedback_raises_when_no_participant(self):
        """Raises ValueError and logs error when participant record does not exist."""
        mock_round_id = 1
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )

        with self.assertRaises(ValueError):
            await self.participation_service.get_program_feedback(
                session=self.mock_session,
                user_context=self.user_context,
                round_id=mock_round_id,
            )

        self.logger.error.assert_called_once_with(
            "[ParticipationService] no participant record for user_id=%s, round_id=%s",
            self.user_context.user_id,
            mock_round_id,
        )

    async def test_upsert_program_feedback_saves_and_returns_dto(self):
        """Persists feedback and returns FeedbackDto with has_submitted=True."""
        mock_round_id = 1

        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.participant_role = ParticipantRole.MENTEE
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )

        feedback_data = FeedbackCreateDto(
            most_valuable_aspects="guidance",
            challenges="time zones",
            program_rating=4,
        )

        result = await self.participation_service.upsert_program_feedback(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
            feedback_data=feedback_data,
        )

        self.assertIsInstance(result, FeedbackDto)
        self.assertTrue(result.has_submitted)
        self.assertEqual(result.most_valuable_aspects, "guidance")
        self.assertEqual(result.program_rating, 4)
        self.assertFalse(hasattr(result, "sessions_completed"))
        self.mock_round_participants_repo.upsert_participant.assert_awaited_once_with(
            session=self.mock_session, entity=mock_participant
        )
        self.mock_round_participants_repo.get_average_program_rating_by_round_and_role.assert_awaited_once_with(
            session=self.mock_session,
            round_id=mock_round_id,
            role=ParticipantRole.MENTEE,
        )
        self.mock_round_repo.update_mentee_average_score.assert_awaited_once_with(
            session=self.mock_session, round_id=mock_round_id, value=4.0
        )
        self.mock_round_repo.update_mentor_average_score.assert_not_awaited()
        self.mock_session.commit.assert_awaited_once()
        self.logger.info.assert_called_once_with(
            "[ParticipationService] program_feedback saved for user_id=%s, round_id=%s",
            self.user_context.user_id,
            mock_round_id,
        )

    REMINDER = datetime(2026, 4, 15, 6, 59, 59, tzinfo=timezone.utc)
    MEETINGS = datetime(2026, 5, 31, 6, 59, 59, tzinfo=timezone.utc)
    FEEDBACK_START = datetime(2026, 6, 5, 6, 59, 59, tzinfo=timezone.utc)
    FEEDBACK_DEADLINE = datetime(2026, 6, 20, 6, 59, 59, tzinfo=timezone.utc)
    MICRO = timedelta(microseconds=1)

    def _with_timeline(self, **columns):
        """Point the round repository at a round carrying the given timeline columns."""
        self.mock_round_repo.get_by_round_id.return_value = MentorshipRoundEntity(
            round_id=1,
            name="round",
            onboarding_deadline_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            **columns,
        )

    def _with_full_timeline(self, **overrides):
        columns = dict(
            meeting_log_reminder_at=self.REMINDER,
            meetings_completion_deadline_at=self.MEETINGS,
            feedback_start_at=self.FEEDBACK_START,
            feedback_deadline_at=self.FEEDBACK_DEADLINE,
        )
        columns.update(overrides)
        self._with_timeline(**columns)

    async def _submit_at(self, now):
        """Submit program feedback as a mentee with the service's clock at now."""
        participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        participant.participant_role = ParticipantRole.MENTEE
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            participant
        )
        with patch("backend.mentorship.participation_service.datetime") as mock_dt:
            mock_dt.now.return_value = now
            return await self.participation_service.upsert_program_feedback(
                session=self.mock_session,
                user_context=self.user_context,
                round_id=1,
                feedback_data=FeedbackCreateDto(program_rating=4),
            )

    def _assert_nothing_written(self):
        self.mock_round_participants_repo.upsert_participant.assert_not_awaited()
        self.mock_session.commit.assert_not_awaited()

    async def test_submission_rejected_just_before_the_window_opens(self):
        self._with_full_timeline()

        with self.assertRaisesRegex(
            ValueError, "^Feedback for this round has not opened yet.$"
        ):
            await self._submit_at(self.REMINDER - self.MICRO)

        self._assert_nothing_written()

    async def test_submission_accepted_at_the_opening(self):
        """The window opens at the reminder, before the feedback email goes out."""
        self._with_full_timeline()

        result = await self._submit_at(self.REMINDER)

        self.assertTrue(result.has_submitted)
        self.mock_session.commit.assert_awaited_once()

    async def test_submission_accepted_at_the_close(self):
        self._with_full_timeline()

        result = await self._submit_at(self.FEEDBACK_DEADLINE)

        self.assertTrue(result.has_submitted)

    async def test_submission_rejected_just_after_the_close(self):
        self._with_full_timeline()

        with self.assertRaisesRegex(
            ValueError, "^The feedback deadline for this round has passed.$"
        ):
            await self._submit_at(self.FEEDBACK_DEADLINE + self.MICRO)

        self._assert_nothing_written()

    async def test_derived_bounds_are_enforced(self):
        """Without the reminder and feedback deadline, the window is a month
        either side of the meetings deadline."""
        self._with_full_timeline(
            meeting_log_reminder_at=None, feedback_deadline_at=None
        )
        month_before = datetime(2026, 4, 30, 6, 59, 59, tzinfo=timezone.utc)
        month_after = datetime(2026, 6, 30, 6, 59, 59, tzinfo=timezone.utc)

        with self.assertRaisesRegex(ValueError, "has not opened yet"):
            await self._submit_at(month_before - self.MICRO)
        await self._submit_at(month_before)
        await self._submit_at(month_after)
        with self.assertRaisesRegex(ValueError, "deadline for this round has passed"):
            await self._submit_at(month_after + self.MICRO)

    async def test_no_restriction_without_dates(self):
        """An unconfigured timeline must not lock participants out entirely."""
        self._with_timeline()

        for now in (
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2030, 1, 1, tzinfo=timezone.utc),
        ):
            with self.subTest(now=now):
                result = await self._submit_at(now)

                self.assertTrue(result.has_submitted)

    async def test_missing_round_does_not_raise(self):
        self.mock_round_repo.get_by_round_id.return_value = None

        result = await self._submit_at(datetime(2030, 1, 1, tzinfo=timezone.utc))

        self.assertTrue(result.has_submitted)
        self.mock_round_repo.get_by_round_id.assert_awaited_once_with(
            self.mock_session, 1
        )

    async def test_upsert_program_feedback_raises_when_no_participant(self):
        """Raises ValueError and logs error when participant record does not exist."""
        mock_round_id = 1
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            None
        )

        feedback_data = FeedbackCreateDto()

        with self.assertRaises(ValueError):
            await self.participation_service.upsert_program_feedback(
                session=self.mock_session,
                user_context=self.user_context,
                round_id=mock_round_id,
                feedback_data=feedback_data,
            )

        self.mock_round_participants_repo.upsert_participant.assert_not_awaited()
        self.mock_session.commit.assert_not_awaited()
        self.logger.error.assert_called_once_with(
            "[ParticipationService] no participant record for user_id=%s, round_id=%s",
            self.user_context.user_id,
            mock_round_id,
        )

    async def test_upsert_program_feedback_updates_mentor_average_score(self):
        """Calls update_mentor_average_score when participant role is MENTOR."""
        mock_round_id = 1

        mock_participant = MagicMock(spec=MentorshipRoundParticipantsEntity)
        mock_participant.participant_role = ParticipantRole.MENTOR
        self.mock_round_participants_repo.get_by_user_id_and_round_id.return_value = (
            mock_participant
        )
        self.mock_round_participants_repo.get_average_program_rating_by_round_and_role.return_value = 3.5

        await self.participation_service.upsert_program_feedback(
            session=self.mock_session,
            user_context=self.user_context,
            round_id=mock_round_id,
            feedback_data=FeedbackCreateDto(program_rating=3),
        )

        self.mock_round_participants_repo.get_average_program_rating_by_round_and_role.assert_awaited_once_with(
            session=self.mock_session,
            round_id=mock_round_id,
            role=ParticipantRole.MENTOR,
        )
        self.mock_round_repo.update_mentor_average_score.assert_awaited_once_with(
            session=self.mock_session, round_id=mock_round_id, value=3.5
        )
        self.mock_round_repo.update_mentee_average_score.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
