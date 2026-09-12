import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.common.mentorship_enums import (
    CommunicationMethod,
    MeetingSource,
    MenteeActionStatus,
    MentorActionStatus,
    PairStatus,
    ParticipantRole,
)
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship.matching_payload_service import MatchingPayloadService
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class MatchingPayloadServiceTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.service = MatchingPayloadService(
            mentorship_round_participants_repository=MentorshipRoundParticipantsRepository(),
            mentorship_pairs_repository=MentorshipPairsRepository(),
            logger=MagicMock(),
        )

    async def _round(self, name="2026 Autumn"):
        entity = MentorshipRoundEntity(name=name, required_meetings=5, description={})
        await self.insert_entities([entity])
        return entity

    async def _user(self, first="Ada", last="Lovelace", preferred=None):
        user = UsersEntity(
            first_name=first,
            last_name=last,
            preferred_name=preferred,
            timezone="America/New_York",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )
        await self.insert_entities([user])
        return user

    async def _participant(self, user, round_entity, role, **fields):
        participant = MentorshipRoundParticipantsEntity(
            user_id=user.user_id,
            round_id=round_entity.round_id,
            participant_role=role,
            **fields,
        )
        await self.insert_entities([participant])
        return participant

    async def _preference(self, user, **fields):
        preference = PreferenceEntity(user_id=user.user_id, **fields)
        await self.insert_entities([preference])
        return preference

    async def _pair_with_meetings(self, round_entity, mentor, mentee, *, completed):
        """Pair the two, and record one meeting that either happened or did not."""
        pair = MentorshipPairsEntity(
            round_id=round_entity.round_id,
            mentor_id=mentor.user_id,
            mentee_id=mentee.user_id,
            completed_count=0,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.PENDING,
            mentee_action_status=MenteeActionStatus.PENDING,
            recommendation_reason="",
        )
        await self.insert_entities([pair])
        await self.insert_entities([
            MentorshipMeetingEntity(
                meeting_id=f"m-{pair.pair_id}",
                pair_id=pair.pair_id,
                source=MeetingSource.MANUAL,
                is_completed=completed,
                start_datetime=datetime(2025, 6, 1, 10, tzinfo=timezone.utc),
                end_datetime=datetime(2025, 6, 1, 11, tzinfo=timezone.utc),
                created_datetime=datetime.now(timezone.utc),
            )
        ])
        return pair

    async def _minimal_round(self):
        """One round with one mentor and one mentee, both registered."""
        round_entity = await self._round()
        mentor = await self._user(first="Grace", last="Hopper")
        mentee = await self._user(first="Alan", last="Turing")
        await self._participant(mentor, round_entity, ParticipantRole.MENTOR)
        await self._participant(mentee, round_entity, ParticipantRole.MENTEE)
        return round_entity, mentor, mentee

    async def test_splits_by_role_and_keeps_industry_off_the_mentor(self):
        round_entity, mentor, mentee = await self._minimal_round()
        await self._preference(
            mentee, specific_industry={"swe": True}, resume_guidance=True
        )

        payload = await self.service.build_matching_payload(
            self.session, round_entity.round_id, [mentor.user_id, mentee.user_id]
        )

        self.assertEqual([p.user_id for p in payload.mentors], [str(mentor.user_id)])
        self.assertIsNone(payload.mentors[0].specific_industry)
        self.assertEqual(payload.mentees[0].specific_industry["swe"], True)
        self.assertEqual(payload.mentees[0].specific_industry["pm"], False)
        self.assertEqual(payload.mentees[0].skills["resume_guidance"], True)
        self.assertEqual(payload.mentees[0].skills["networking"], False)

    async def test_preferred_name_wins_and_ids_are_strings(self):
        round_entity = await self._round()
        mentor = await self._user(first="Grace", last="Hopper", preferred="Amazing G")
        mentee = await self._user(first="Alan", last="Turing")
        await self._participant(mentor, round_entity, ParticipantRole.MENTOR)
        await self._participant(mentee, round_entity, ParticipantRole.MENTEE)

        payload = await self.service.build_matching_payload(
            self.session, round_entity.round_id, [mentor.user_id, mentee.user_id]
        )

        self.assertEqual(payload.mentors[0].display_name, "Amazing G")
        self.assertEqual(payload.mentees[0].display_name, "Alan Turing")
        self.assertIsInstance(payload.mentors[0].user_id, str)

    async def test_translates_survey_answers_into_contract_codes(self):
        round_entity = await self._round()
        mentor = await self._user(first="Grace", last="Hopper")
        mentee = await self._user(first="Alan", last="Turing")
        await self._participant(mentor, round_entity, ParticipantRole.MENTOR)
        await self._participant(
            mentee,
            round_entity,
            ParticipantRole.MENTEE,
            current_stage="employed_growing",
            time_urgency="within_3_months",
        )
        await self._preference(
            mentee,
            specific_industry={},
            profile_survey={"current_background": "non_cs_cs_master"},
        )

        payload = await self.service.build_matching_payload(
            self.session, round_entity.round_id, [mentor.user_id, mentee.user_id]
        )

        record = payload.mentees[0]
        self.assertEqual(record.mentee_stage, "employed_growth")
        self.assertEqual(record.urgency, "3m")
        self.assertEqual(record.transition_type, "path_a")

    async def test_other_answer_travels_beside_the_enum(self):
        round_entity, mentor, mentee = await self._minimal_round()
        await self._preference(
            mentor,
            profile_survey={
                "career_transition": "other",
                "career_transition_other": "Came over from bioinformatics",
            },
        )
        await self._preference(mentee, specific_industry={})

        payload = await self.service.build_matching_payload(
            self.session, round_entity.round_id, [mentor.user_id, mentee.user_id]
        )

        record = payload.mentors[0]
        self.assertIsNone(record.career_transition)
        self.assertEqual(
            record.career_transition_other, "Came over from bioinformatics"
        )

    async def test_external_experience_keeps_its_bucket(self):
        round_entity, mentor, mentee = await self._minimal_round()
        await self._preference(
            mentor, profile_survey={"external_mentoring_exp": "3_plus"}
        )
        await self._preference(mentee, specific_industry={})

        payload = await self.service.build_matching_payload(
            self.session, round_entity.round_id, [mentor.user_id, mentee.user_id]
        )

        # Not the midpoint integer 4 the old export produced, which rationales
        # then printed as a precise count.
        self.assertEqual(payload.mentors[0].external_mentoring_exp, "3_plus")

    async def test_counts_rounds_paired_apart_from_rounds_that_happened(self):
        round_entity, mentor, mentee = await self._minimal_round()
        await self._preference(mentee, specific_industry={})

        past_a = await self._round(name="2025 Spring")
        past_b = await self._round(name="2025 Autumn")
        quiet_mentee = await self._user(first="Quiet", last="Mentee")
        busy_mentee = await self._user(first="Busy", last="Mentee")
        # One round went somewhere; in the other the mentee never turned up.
        await self._pair_with_meetings(past_a, mentor, busy_mentee, completed=True)
        await self._pair_with_meetings(past_b, mentor, quiet_mentee, completed=False)

        payload = await self.service.build_matching_payload(
            self.session, round_entity.round_id, [mentor.user_id, mentee.user_id]
        )

        record = payload.mentors[0]
        self.assertEqual(record.mentorship_rounds_participated, 2)
        self.assertEqual(record.mentorship_rounds_completed, 1)

    async def test_the_round_being_matched_is_not_counted_as_experience(self):
        round_entity, mentor, mentee = await self._minimal_round()
        await self._preference(mentee, specific_industry={})
        await self._pair_with_meetings(round_entity, mentor, mentee, completed=True)

        payload = await self.service.build_matching_payload(
            self.session, round_entity.round_id, [mentor.user_id, mentee.user_id]
        )

        self.assertEqual(payload.mentors[0].mentorship_rounds_participated, 0)
        self.assertEqual(payload.mentors[0].mentorship_rounds_completed, 0)

    async def test_rejects_a_user_who_is_not_in_this_round(self):
        round_entity, mentor, mentee = await self._minimal_round()
        await self._preference(mentee, specific_industry={})
        stranger = await self._user(first="Not", last="Registered")

        with self.assertRaises(ValueError) as caught:
            await self.service.build_matching_payload(
                self.session,
                round_entity.round_id,
                [mentor.user_id, mentee.user_id, stranger.user_id],
            )
        self.assertIn(str(stranger.user_id), str(caught.exception))

    async def test_rejects_a_selection_missing_a_whole_side(self):
        round_entity, mentor, _ = await self._minimal_round()

        with self.assertRaises(ValueError):
            await self.service.build_matching_payload(
                self.session, round_entity.round_id, [mentor.user_id]
            )

    async def test_run_id_names_the_round(self):
        round_entity, mentor, mentee = await self._minimal_round()
        await self._preference(mentee, specific_industry={})

        payload = await self.service.build_matching_payload(
            self.session, round_entity.round_id, [mentor.user_id, mentee.user_id]
        )

        self.assertTrue(payload.run_id.startswith(f"r{round_entity.round_id}-"))
        self.assertEqual(payload.contract_version, 1)


if __name__ == "__main__":
    unittest.main()
