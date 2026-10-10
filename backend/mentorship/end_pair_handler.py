"""Ending one pair in a round, as an approval.

A request is about one active pair while its round is in progress, raised
from either person's page. Approving it, in the approval's transaction, ends
the pair, cancels its meetings that have not started, moves whoever is left
with no active pair from matched to un_matched, and notes it on both people.
Nothing undoes it, and the same two cannot be paired again in the round.
"""

from datetime import datetime, timezone

from backend.approval.approval_handler import ApprovalHandler
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    MentorshipEvent,
    PairStatus,
    ParticipantNoteTag,
)
from backend.common.name_utils import user_display_name
from backend.common.permissions import Permission
from backend.mentorship.pair_endings import unmatch_if_unpaired
from backend.mentorship.publish_matching_handler import MENTORSHIP_ROUND_SUBJECT
from backend.mentorship.round_windows import is_in_progress

END_PAIR = "end_pair"
PAIR_TARGET = "mentorship_pair"
ALREADY_ENDED = "This pair has already ended."

_PAYLOAD_KEYS = ("round_id", "pair_id", "mentor_id", "mentee_id")


def pair_target(pair_id: int) -> str:
    """The target id of a request about one pair."""
    return str(pair_id)


class EndPairHandler(ApprovalHandler):
    """The ``end_pair`` action. Its payload carries the round, the pair and
    the two people in it; its target id is the pair."""

    action = END_PAIR
    target_type = PAIR_TARGET
    subject_type = MENTORSHIP_ROUND_SUBJECT
    raised_event = MentorshipEvent.APPROVAL_REQUESTED
    reassigned_event = MentorshipEvent.APPROVAL_REASSIGNED
    decided_event = MentorshipEvent.APPROVAL_DECIDED
    review_permission = Permission.MENTORSHIP_APPROVE

    def __init__(
        self,
        participants_repository,
        pairs_repository,
        meeting_service,
        rounds_repository,
        note_repository,
        users_repository,
        logger,
    ):
        """
        Args:
            participants_repository: Reads and changes the registrations.
            pairs_repository: Reads and ends the pair.
            meeting_service: Cancels the pair's upcoming meetings.
            rounds_repository: Reads the round, to check it is in progress.
            note_repository: Writes the two notes.
            users_repository: Names people in notes and emails.
            logger: Injected logger.
        """
        self.participants_repository = participants_repository
        self.pairs_repository = pairs_repository
        self.meeting_service = meeting_service
        self.rounds_repository = rounds_repository
        self.note_repository = note_repository
        self.users_repository = users_repository
        self.logger = logger

    def subject_id(self, request) -> int:
        return int(request.payload["round_id"])

    async def event_details(self, session, request) -> dict:
        round_ = await self.rounds_repository.get_by_round_id(
            session, self.subject_id(request)
        )
        mentor_id = int(request.payload["mentor_id"])
        mentee_id = int(request.payload["mentee_id"])
        names = await self._names(session, [mentor_id, mentee_id])
        mentor, mentee = names.get(mentor_id), names.get(mentee_id)
        return {
            "roundName": round_.name if round_ is not None else None,
            "mentorName": mentor,
            "menteeName": mentee,
            "personName": (
                f"mentor {mentor or f'User {mentor_id}'} and mentee "
                f"{mentee or f'User {mentee_id}'}"
            ),
        }

    async def check_raise(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> None:
        """Refuse ending a pair that is not active in a round in progress.

        Raises:
            ValueError: The payload or target id is malformed.
            ConflictError: The round is not in progress, or the pair is not
                that pair or has ended.
        """
        if not all(isinstance(payload.get(key), int) for key in _PAYLOAD_KEYS):
            raise ValueError(
                "A request to end a pair names its round, pair, mentor and mentee."
            )
        if target_id != pair_target(payload["pair_id"]):
            raise ValueError("A request to end a pair has the pair as its target.")
        problems = await self._problems(session, payload)
        if problems:
            raise ConflictError(problems[0])

    async def problems_at_approval(self, session, request) -> list[str]:
        """The round still has to be in progress and the pair still active.

        Returns:
            list[str]: One sentence per problem, empty when it may go ahead.
        """
        return await self._problems(
            session, {key: int(request.payload[key]) for key in _PAYLOAD_KEYS}
        )

    async def execute(self, session, request, *, actor_id: int) -> None:
        """End the pair, cancel its upcoming meetings, unmatch whoever is left
        with no pair and note it on both people, by the approver. Does not
        commit."""
        round_id = int(request.payload["round_id"])
        pair_id = int(request.payload["pair_id"])
        mentor_id = int(request.payload["mentor_id"])
        mentee_id = int(request.payload["mentee_id"])

        pair = await self.pairs_repository.get_pair_by_id(
            session, pair_id, with_lock=True
        )
        pair.status = PairStatus.INACTIVE
        await session.flush()

        cancelled = await self.meeting_service.cancel_upcoming_for_pairs(
            session, [pair_id]
        )
        unmatched = await unmatch_if_unpaired(
            session,
            participants_repository=self.participants_repository,
            pairs_repository=self.pairs_repository,
            round_id=round_id,
            user_ids=[mentor_id, mentee_id],
        )

        names = await self._names(session, {request.raised_by, actor_id})
        tail = (
            f"Raised by {names.get(request.raised_by, f'User {request.raised_by}')}"
            f", reason: {request.reason or 'none given'}; approved by "
            f"{names.get(actor_id, f'User {actor_id}')}. {cancelled} upcoming "
            f"meetings cancelled."
        )
        moved = f"; {ApprovalStatus.MATCHED.value} -> {ApprovalStatus.UN_MATCHED.value}"
        for user_id in (mentor_id, mentee_id):
            await self.note_repository.create(
                session,
                user_id=user_id,
                round_id=round_id,
                author_user_id=actor_id,
                body=f"Pair ended{moved if user_id in unmatched else ''}. {tail}",
                tag=ParticipantNoteTag.STATUS_CHANGE,
                pair_id=pair_id,
                request_id=request.request_id,
            )
        self.logger.info(
            "[EndPairHandler] round=%s pair=%s unmatched=%s meetings=%d by=%s",
            round_id,
            pair_id,
            sorted(unmatched),
            cancelled,
            actor_id,
        )

    async def _problems(self, session, payload: dict) -> list[str]:
        round_id = payload["round_id"]
        round_ = await self.rounds_repository.get_by_round_id(session, round_id)
        if round_ is None:
            return [f"Mentorship round {round_id} does not exist."]
        if not is_in_progress(round_, datetime.now(timezone.utc)):
            return ["The round is not in progress."]
        pair = await self.pairs_repository.get_pair_by_id(session, payload["pair_id"])
        if (
            pair is None
            or pair.round_id != round_id
            or pair.mentor_id != payload["mentor_id"]
            or pair.mentee_id != payload["mentee_id"]
        ):
            return [f"Pair {payload['pair_id']} is not that pair in this round."]
        if pair.status != PairStatus.ACTIVE:
            return [ALREADY_ENDED]
        return []

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
