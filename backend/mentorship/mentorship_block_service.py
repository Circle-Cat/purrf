"""What blocking someone does to their mentorship.

Called from the block kernel inside its transaction. Every pair the person
has in a round under way ends and its meetings that have not started are
cancelled; the person leaves those rounds; a partner left with no active pair
goes from matched to un_matched. Each person gets a note by whoever applied
the block, without the block's reason. Never commits.
"""

from datetime import datetime, timezone

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    PairStatus,
    ParticipantNoteTag,
)
from backend.common.name_utils import user_display_name
from backend.mentorship.pair_endings import unmatch_if_unpaired
from backend.mentorship.round_windows import is_in_progress

CALENDAR_REFUSED = (
    "Some upcoming mentorship meetings could not be cancelled on the calendar, "
    "so nobody was blocked. Some invites may already be cancelled; try again."
)

# The statuses someone is still in the round with.
_WITHDRAWABLE = {
    ApprovalStatus.SIGNED_UP,
    ApprovalStatus.MATCHED,
    ApprovalStatus.UN_MATCHED,
}


class MentorshipBlockService:
    """Ends a blocked person's mentorship in the rounds under way."""

    def __init__(
        self,
        participants_repository,
        pairs_repository,
        meeting_service,
        note_repository,
        users_repository,
        logger,
    ):
        """
        Args:
            participants_repository: The person's rounds and registrations.
            pairs_repository: Their pairs in each round.
            meeting_service: Counts and cancels the pairs' upcoming meetings.
            note_repository: Writes the status change notes.
            users_repository: Names people in the notes.
            logger: Injected logger.
        """
        self.participants_repository = participants_repository
        self.pairs_repository = pairs_repository
        self.meeting_service = meeting_service
        self.note_repository = note_repository
        self.users_repository = users_repository
        self.logger = logger

    async def preflight_counts(self, session, user_id: int) -> tuple[int, int]:
        """How many pairs blocking this person would end, and how many
        upcoming meetings that would cancel. Reads only.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The person about to be blocked.

        Returns:
            tuple[int, int]: (pairs, meetings).
        """
        by_round = await self._active_pairs_by_round(session, user_id)
        pair_ids = [pair.pair_id for pairs in by_round.values() for pair in pairs]
        meetings = await self.meeting_service.count_upcoming_for_pairs(
            session, pair_ids
        )
        return len(pair_ids), meetings

    async def end_for_blocked_user(
        self,
        session,
        *,
        user_id: int,
        actor_id: int,
        request_id: int | None = None,
    ) -> None:
        """End the person's pairs in rounds under way and note it. Does not
        commit.

        Args:
            session (AsyncSession): The block's open session.
            user_id (int): The person being blocked.
            actor_id (int): Who applied the block; the notes' author.
            request_id (int | None): The approval request, when there was one.

        Raises:
            ConflictError: Calendar refused to cancel a meeting (code
                ``calendar_cancel_failed``); the caller rolls back.
        """
        by_round = await self._active_pairs_by_round(session, user_id)
        if not by_round:
            return
        for pairs in by_round.values():
            for pair in pairs:
                pair.status = PairStatus.INACTIVE
        await session.flush()

        cancelled: dict[int, int] = {}
        try:
            for pairs in by_round.values():
                for pair in pairs:
                    cancelled[pair.pair_id] = (
                        await self.meeting_service.cancel_upcoming_for_pairs(
                            session, [pair.pair_id]
                        )
                    )
        except ConflictError as refused:
            raise ConflictError(CALENDAR_REFUSED, code=refused.code) from refused

        partner_of = {
            pair.pair_id: pair.mentee_id if pair.mentor_id == user_id else pair.mentor_id
            for pairs in by_round.values()
            for pair in pairs
        }
        names = await self._names(session, {user_id, *partner_of.values()})

        def name(uid):
            return names.get(uid, f"User {uid}")

        for round_id, pairs in by_round.items():
            participant = await self.participants_repository.get_by_user_id_and_round_id(
                session, user_id, round_id
            )
            before = participant.approval_status if participant is not None else None
            moved = before in _WITHDRAWABLE
            if moved:
                participant.approval_status = ApprovalStatus.WITHDRAWN
            unmatched = await unmatch_if_unpaired(
                session,
                participants_repository=self.participants_repository,
                pairs_repository=self.pairs_repository,
                round_id=round_id,
                user_ids=[partner_of[pair.pair_id] for pair in pairs],
            )
            ended = ", ".join(
                f"{name(partner_of[pair.pair_id])} (pair {pair.pair_id})"
                for pair in pairs
            )
            head = (
                f"{before.value} -> {ApprovalStatus.WITHDRAWN.value}: blocked."
                if moved
                else "Blocked."
            )
            await self.note_repository.create(
                session,
                user_id=user_id,
                round_id=round_id,
                author_user_id=actor_id,
                body=(
                    f"{head} Pairs ended: {ended}. Upcoming meetings cancelled: "
                    f"{sum(cancelled[pair.pair_id] for pair in pairs)}."
                ),
                tag=ParticipantNoteTag.STATUS_CHANGE,
                pair_id=None,
                request_id=request_id,
            )
            for pair in pairs:
                partner_id = partner_of[pair.pair_id]
                change = (
                    f"; {ApprovalStatus.MATCHED.value} -> "
                    f"{ApprovalStatus.UN_MATCHED.value}"
                    if partner_id in unmatched
                    else ""
                )
                await self.note_repository.create(
                    session,
                    user_id=partner_id,
                    round_id=round_id,
                    author_user_id=actor_id,
                    body=(
                        f"Pair ended: {name(user_id)} was blocked{change}. "
                        f"{cancelled[pair.pair_id]} upcoming meetings cancelled."
                    ),
                    tag=ParticipantNoteTag.STATUS_CHANGE,
                    pair_id=pair.pair_id,
                    request_id=request_id,
                )
        self.logger.info(
            "[MentorshipBlockService] user=%s rounds=%s pairs=%s by=%s",
            user_id,
            list(by_round),
            list(partner_of),
            actor_id,
        )

    async def _active_pairs_by_round(self, session, user_id: int) -> dict[int, list]:
        now = datetime.now(timezone.utc)
        rounds = (
            await self.participants_repository.list_registered_rounds_by_user_ids(
                session, [user_id]
            )
        ).get(user_id, [])
        found: dict[int, list] = {}
        for round_ in rounds:
            if not is_in_progress(round_, now):
                continue
            pairs = [
                pair
                for pair in await self.pairs_repository.get_pairs_by_user_and_round(
                    session=session, user_id=user_id, round_id=round_.round_id
                )
                if pair.status == PairStatus.ACTIVE
            ]
            if pairs:
                found[round_.round_id] = pairs
        return found

    async def _names(self, session, user_ids) -> dict[int, str]:
        people = await self.users_repository.get_all_by_ids(session, list(user_ids))
        return {
            person.user_id: user_display_name(
                first_name=person.first_name,
                last_name=person.last_name,
                preferred_name=person.preferred_name,
            )
            for person in people
        }
