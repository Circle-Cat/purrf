"""Reads a round and its history, and says who may go into its matching pool.

The participant search and the start of a matching run both ask here, so the
people listed as eligible are exactly the people a run accepts.
"""

from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import (
    ApprovalStatus,
    PairStatus,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.mentorship.matching_eligibility import (
    Candidate,
    IneligibleReason,
    PastPair,
    PastRound,
    ineligible_reasons,
)

_TAKING_PART = {
    ApprovalStatus.SIGNED_UP,
    ApprovalStatus.MATCHED,
    ApprovalStatus.UN_MATCHED,
}

_ONBOARDING_BY_ROLE = {
    ParticipantRole.MENTOR: TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
    ParticipantRole.MENTEE: TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
}


class MatchingEligibilityService:
    """Decides, for one round, who is eligible for matching and why not."""

    def __init__(
        self,
        participants_repository,
        pairs_repository,
        rounds_repository,
        training_repository,
        logger,
    ):
        """
        Args:
            participants_repository: Registrations, and who quit a round.
            pairs_repository: Pairs and their meeting counts.
            rounds_repository: The round and the ones before it.
            training_repository: Onboarding course status.
            logger: Injected logger.
        """
        self.participants_repository = participants_repository
        self.pairs_repository = pairs_repository
        self.rounds_repository = rounds_repository
        self.training_repository = training_repository
        self.logger = logger

    async def ineligible_by_user(
        self, session: AsyncSession, round_id: int
    ) -> dict[int, list[IneligibleReason]]:
        """Every registration for the round with the reasons it is not
        eligible, an empty list meaning eligible.

        A round has registrations in the hundreds, so all of them are read in
        a fixed number of queries and decided in memory.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round being matched.

        Returns:
            dict[int, list[IneligibleReason]]: user_id -> reasons.

        Raises:
            ValueError: If the round does not exist.
        """
        rounds = await self.rounds_repository.get_all_rounds(session)
        current = next((r for r in rounds if r.round_id == round_id), None)
        if current is None:
            raise ValueError(f"Mentorship round {round_id} does not exist.")

        registrations = await self.participants_repository.list_round_registrations(
            session, round_id
        )
        if not registrations:
            return {}
        user_ids = [user.user_id for user, _ in registrations]

        trainings = (
            await self.training_repository.get_training_by_user_ids_and_categories(
                session, user_ids, categories=list(_ONBOARDING_BY_ROLE.values())
            )
        )
        done = {
            (t.user_id, t.category)
            for t in trainings
            if t.status == TrainingStatus.DONE
        }

        active_pairs = await self.pairs_repository.get_active_pairs_by_round(
            session, round_id
        )
        held = Counter()
        for pair in active_pairs:
            held[(pair.mentor_id, ParticipantRole.MENTOR)] += 1
            held[(pair.mentee_id, ParticipantRole.MENTEE)] += 1

        past_rounds = await self._past_rounds(session, rounds, current, user_ids)

        result: dict[int, list[IneligibleReason]] = {}
        for user, participant in registrations:
            role = participant.participant_role
            cap = (
                participant.max_partners
                if role == ParticipantRole.MENTOR
                and participant.max_partners is not None
                else 1
            )
            candidate = Candidate(
                user_id=user.user_id,
                is_blocked=bool(user.is_blocked),
                is_active=bool(user.is_active),
                is_taking_part=participant.approval_status in _TAKING_PART,
                training_done=(user.user_id, _ONBOARDING_BY_ROLE.get(role)) in done,
                open_slots=cap - held[(user.user_id, role)],
            )
            result[user.user_id] = ineligible_reasons(candidate, past_rounds)
        return result

    async def eligible_user_ids(self, session: AsyncSession, round_id: int) -> set[int]:
        """The people eligible for matching in the round.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round being matched.

        Returns:
            set[int]: Their user_ids.
        """
        reasons = await self.ineligible_by_user(session, round_id)
        return {user_id for user_id, why in reasons.items() if not why}

    async def _past_rounds(
        self, session: AsyncSession, rounds: list, current, user_ids: list[int]
    ) -> list[PastRound]:
        """The rounds before ``current`` as the given people's history,
        latest first.

        A round is earlier when its meetings deadline is; rounds without one
        cannot be placed and are left out. Besides the people's own pairs,
        each round carries every pair of their mentees, so a mentor's mentee
        is judged by her total over a change of mentor.
        """
        deadline = current.meetings_completion_deadline_at
        earlier = [
            r
            for r in rounds
            if r.round_id != current.round_id
            and r.meetings_completion_deadline_at is not None
            and (deadline is None or r.meetings_completion_deadline_at < deadline)
        ]
        if not earlier:
            return []
        round_ids = [r.round_id for r in earlier]

        own = await self.pairs_repository.list_pairs_with_meeting_counts(
            session, round_ids, user_ids
        )
        mentee_ids = sorted({pair.mentee_id for pair, _ in own} - set(user_ids))
        of_mentees = await self.pairs_repository.list_pairs_with_meeting_counts(
            session, round_ids, mentee_ids
        )
        pairs = {pair.pair_id: (pair, count) for pair, count in [*own, *of_mentees]}

        quitters = await self.participants_repository.list_rejected_by_round(
            session, round_ids, user_ids
        )

        by_round: dict[int, list[PastPair]] = {}
        for pair, count in pairs.values():
            by_round.setdefault(pair.round_id, []).append(
                PastPair(
                    mentor_id=pair.mentor_id,
                    mentee_id=pair.mentee_id,
                    is_active=pair.status == PairStatus.ACTIVE,
                    completed_count=count,
                )
            )
        return [
            PastRound(
                required_meetings=r.required_meetings,
                pairs=tuple(by_round.get(r.round_id, ())),
                quitters=frozenset(quitters.get(r.round_id, set())),
            )
            for r in earlier
        ]
