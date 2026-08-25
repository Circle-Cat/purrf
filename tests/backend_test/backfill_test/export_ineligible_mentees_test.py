import unittest
from datetime import datetime, timezone

from backend.backfill.export_mentorship_records import compute_ineligible_mentee_ids
from backend.common.mentorship_enums import (
    ApprovalStatus,
    CommunicationMethod,
    MenteeActionStatus,
    MentorActionStatus,
    PairStatus,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.training_entity import TrainingEntity
from backend.entity.users_entity import UsersEntity
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

REQUIRED_MEETINGS = 5


class TestComputeIneligibleMenteeIds(BaseRepositoryTestLib):
    """Rule 2 of the export's eligibility check, which reads the previous
    round's completed meetings.

    A mentee can hold more than one pair in a round -- changing mentor
    mid-round leaves the abandoned pair behind -- so these cover what the
    total is taken to be.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.now = datetime.now(timezone.utc)

        self.prev_round = MentorshipRoundEntity(
            name="prev-round", required_meetings=REQUIRED_MEETINGS
        )
        self.current_round = MentorshipRoundEntity(
            name="current-round", required_meetings=REQUIRED_MEETINGS
        )
        await self.insert_entities([self.prev_round, self.current_round])

        self.mentor = await self._make_user("Mentor")

    async def _make_user(self, first_name):
        user = UsersEntity(
            first_name=first_name,
            last_name="Tester",
            timezone="Asia/Shanghai",
            timezone_updated_at=self.now,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=self.now,
        )
        await self.insert_entities([user])
        return user

    async def _make_mentee(
        self,
        first_name,
        *,
        trained=True,
        approval_status=ApprovalStatus.MATCHED,
    ):
        """A mentee registered for the round being exported.

        `trained` controls rule 1 so rule 2 can be observed on its own: an
        untrained mentee is ineligible before rule 2 is ever consulted.
        """
        mentee = await self._make_user(first_name)
        await self.insert_entities([
            MentorshipRoundParticipantsEntity(
                user_id=mentee.user_id,
                round_id=self.current_round.round_id,
                participant_role=ParticipantRole.MENTEE,
                approval_status=approval_status,
            ),
            TrainingEntity(
                user_id=mentee.user_id,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE if trained else TrainingStatus.TO_DO,
                completed_timestamp=self.now if trained else None,
                deadline=self.now,
            ),
        ])
        return mentee

    async def _add_prev_pairs(self, mentee, completed_counts):
        """Give the mentee one pair per entry in `completed_counts` in the
        previous round, each under a different mentor."""
        pairs = []
        for completed in completed_counts:
            mentor = await self._make_user("Mentor")
            pairs.append(
                MentorshipPairsEntity(
                    round_id=self.prev_round.round_id,
                    mentor_id=mentor.user_id,
                    mentee_id=mentee.user_id,
                    completed_count=completed,
                    status=PairStatus.ACTIVE,
                    mentor_action_status=MentorActionStatus.CONFIRMED,
                    mentee_action_status=MenteeActionStatus.CONFIRMED,
                    recommendation_reason="",
                )
            )
        await self.insert_entities(pairs)

    async def _compute(self, exemptions=frozenset()):
        return await compute_ineligible_mentee_ids(
            self.session,
            self.current_round.round_id,
            self.prev_round,
            set(exemptions),
        )

    async def test_meetings_are_summed_across_a_mentor_change(self):
        """Neither pair clears the bar alone, but together they do.

        This is the case a per-pair reading rejects: the mentee left one
        mentor after one meeting and completed four with the next, so they
        held the required five.
        """
        mentee = await self._make_mentee("Switcher")
        await self._add_prev_pairs(mentee, [1, 4])

        self.assertEqual(await self._compute(), [])

    async def test_a_mentee_short_overall_is_listed_exactly_once(self):
        """Two pairs that fall short together still name the mentee once.

        The count of this list is what the operator is asked to approve
        before any rejection is written, so a mentee appearing twice would
        overstate how many people are about to be rejected.
        """
        mentee = await self._make_mentee("Short")
        await self._add_prev_pairs(mentee, [1, 1])

        self.assertEqual(await self._compute(), [mentee.user_id])

    async def test_single_pair_below_the_bar_is_ineligible(self):
        mentee = await self._make_mentee("Lagging")
        await self._add_prev_pairs(mentee, [REQUIRED_MEETINGS - 1])

        self.assertEqual(await self._compute(), [mentee.user_id])

    async def test_single_pair_meeting_the_bar_is_eligible(self):
        mentee = await self._make_mentee("Diligent")
        await self._add_prev_pairs(mentee, [REQUIRED_MEETINGS])

        self.assertEqual(await self._compute(), [])

    async def test_mentee_absent_from_the_previous_round_is_not_judged(self):
        """Rule 2 only speaks about people who took part in the previous
        round; a newcomer has no count to fall short of."""
        await self._make_mentee("Newcomer")

        self.assertEqual(await self._compute(), [])

    async def test_exemption_spares_a_mentee_who_fell_short(self):
        mentee = await self._make_mentee("Excused")
        await self._add_prev_pairs(mentee, [1, 1])

        self.assertEqual(await self._compute(exemptions={mentee.user_id}), [])

    async def test_untrained_mentee_is_ineligible_despite_enough_meetings(self):
        mentee = await self._make_mentee("Untrained", trained=False)
        await self._add_prev_pairs(mentee, [REQUIRED_MEETINGS])

        self.assertEqual(await self._compute(), [mentee.user_id])

    async def test_untrained_mentee_short_overall_is_still_listed_once(self):
        """Failing both rules must not name the mentee twice either."""
        mentee = await self._make_mentee("Untrained", trained=False)
        await self._add_prev_pairs(mentee, [1, 1])

        self.assertEqual(await self._compute(), [mentee.user_id])

    async def test_already_rejected_mentee_is_not_evaluated(self):
        mentee = await self._make_mentee(
            "Rejected", trained=False, approval_status=ApprovalStatus.REJECTED
        )
        await self._add_prev_pairs(mentee, [1])

        self.assertEqual(await self._compute(), [])

    async def test_without_a_previous_round_rule_two_is_skipped(self):
        mentee = await self._make_mentee("Pioneer")
        await self._add_prev_pairs(mentee, [1])

        result = await compute_ineligible_mentee_ids(
            self.session, self.current_round.round_id, None, set()
        )

        self.assertEqual(result, [])
        self.assertIsNotNone(mentee.user_id)


if __name__ == "__main__":
    unittest.main()
