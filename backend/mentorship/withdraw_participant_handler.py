"""Withdrawing a person from a round, as an approval.

A request is about one person in one round while the round is in progress
and they are still in it. Approving it, in the approval's transaction, marks
them withdrawn, ends every active pair they have in the round, cancels those
pairs' meetings that have not started, and notes it all on them. A partner
left with no active pair goes from matched to un_matched. Nothing undoes it.
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
from backend.mentorship.exempt_matching_handler import exemption_target
from backend.mentorship.pair_endings import unmatch_if_unpaired
from backend.mentorship.publish_matching_handler import MENTORSHIP_ROUND_SUBJECT
from backend.mentorship.round_windows import is_in_progress

WITHDRAW_PARTICIPANT = "withdraw_participant"

# The statuses someone is still in the round with.
_WITHDRAWABLE = {
    ApprovalStatus.SIGNED_UP,
    ApprovalStatus.MATCHED,
    ApprovalStatus.UN_MATCHED,
}


class WithdrawParticipantHandler(ApprovalHandler):
    """The ``withdraw_participant`` action. Its payload carries the round and
    the person; its target id is the two together."""

    action = WITHDRAW_PARTICIPANT
    target_type = "round_participant"
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
            participants_repository: Reads and changes the registration.
            pairs_repository: Finds the person's pairs in the round.
            meeting_service: Cancels those pairs' upcoming meetings.
            rounds_repository: Reads the round, to check it is in progress.
            note_repository: Writes the status change note.
            users_repository: Names people in notes, refusals and emails.
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
        user_id = int(request.payload["user_id"])
        names = await self._names(session, [user_id])
        return {
            "roundName": round_.name if round_ is not None else None,
            "personName": names.get(user_id),
        }

    async def check_raise(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> None:
        """Refuse a withdrawal for a round not in progress, or for someone
        not still in it.

        Raises:
            ValueError: The payload or target id is malformed.
            ConflictError: The round is not in progress, or the person is not
                registered or has already left.
        """
        round_id, user_id = payload.get("round_id"), payload.get("user_id")
        if not isinstance(round_id, int) or not isinstance(user_id, int):
            raise ValueError("A withdrawal request names its round and person.")
        if target_id != exemption_target(round_id, user_id):
            raise ValueError("A withdrawal request's target is its round and person.")
        problems = await self._problems(session, round_id, user_id)
        if problems:
            raise ConflictError(problems[0])

    async def problems_at_approval(self, session, request) -> list[str]:
        """The round still has to be in progress and the person still in it.

        Returns:
            list[str]: One sentence per problem, empty when it may go ahead.
        """
        return await self._problems(
            session, int(request.payload["round_id"]), int(request.payload["user_id"])
        )

    async def execute(self, session, request, *, actor_id: int) -> None:
        """Withdraw the person, end their active pairs, cancel those pairs'
        upcoming meetings and note it, by the approver. Does not commit."""
        round_id = int(request.payload["round_id"])
        user_id = int(request.payload["user_id"])
        participant = await self.participants_repository.get_by_user_id_and_round_id(
            session, user_id, round_id
        )
        before = participant.approval_status
        participant.approval_status = ApprovalStatus.WITHDRAWN

        pairs = [
            pair
            for pair in await self.pairs_repository.get_pairs_by_user_and_round(
                session=session, user_id=user_id, round_id=round_id
            )
            if pair.status == PairStatus.ACTIVE
        ]
        for pair in pairs:
            pair.status = PairStatus.INACTIVE
        await session.flush()

        cancelled = await self.meeting_service.cancel_upcoming_for_pairs(
            session, [pair.pair_id for pair in pairs]
        )

        partner_of = {
            pair.pair_id: pair.mentee_id
            if pair.mentor_id == user_id
            else pair.mentor_id
            for pair in pairs
        }
        unmatched = await unmatch_if_unpaired(
            session,
            participants_repository=self.participants_repository,
            pairs_repository=self.pairs_repository,
            round_id=round_id,
            user_ids=partner_of.values(),
        )
        names = await self._names(
            session, {user_id, request.raised_by, actor_id, *partner_of.values()}
        )
        ended = (
            ", ".join(
                f"{names.get(partner_id, f'User {partner_id}')} (pair {pair_id})"
                for pair_id, partner_id in partner_of.items()
            )
            or "none"
        )
        await self.note_repository.create(
            session,
            user_id=user_id,
            round_id=round_id,
            author_user_id=actor_id,
            body=(
                f"{before.value} -> {ApprovalStatus.WITHDRAWN.value}: withdrawn "
                f"from this round. Pairs ended: {ended}. Upcoming meetings "
                f"cancelled: {cancelled}. Raised by "
                f"{names.get(request.raised_by, f'User {request.raised_by}')}, "
                f"reason: {request.reason or 'none given'}; approved by "
                f"{names.get(actor_id, f'User {actor_id}')}."
            ),
            tag=ParticipantNoteTag.STATUS_CHANGE,
            request_id=request.request_id,
        )
        person = names.get(user_id, f"User {user_id}")
        by = (
            f"Raised by {names.get(request.raised_by, f'User {request.raised_by}')}"
            f", reason: {request.reason or 'none given'}; approved by "
            f"{names.get(actor_id, f'User {actor_id}')}."
        )
        for pair_id, partner_id in partner_of.items():
            if partner_id not in unmatched:
                continue
            await self.note_repository.create(
                session,
                user_id=partner_id,
                round_id=round_id,
                author_user_id=actor_id,
                body=(
                    f"{ApprovalStatus.MATCHED.value} -> "
                    f"{ApprovalStatus.UN_MATCHED.value}: their partner {person} "
                    f"left this round. {by}"
                ),
                tag=ParticipantNoteTag.STATUS_CHANGE,
                pair_id=pair_id,
                request_id=request.request_id,
            )
        self.logger.info(
            "[WithdrawParticipantHandler] round=%s user=%s pairs=%s meetings=%d by=%s",
            round_id,
            user_id,
            list(partner_of),
            cancelled,
            actor_id,
        )

    async def _problems(self, session, round_id: int, user_id: int) -> list[str]:
        round_ = await self.rounds_repository.get_by_round_id(session, round_id)
        if round_ is None:
            return [f"Mentorship round {round_id} does not exist."]
        if not is_in_progress(round_, datetime.now(timezone.utc)):
            return ["The round is not in progress."]
        participant = await self.participants_repository.get_by_user_id_and_round_id(
            session, user_id, round_id
        )
        if participant is not None and participant.approval_status in _WITHDRAWABLE:
            return []
        name = (await self._names(session, [user_id])).get(user_id) or f"User {user_id}"
        if participant is None:
            return [f"{name} is not registered for this round."]
        if participant.approval_status == ApprovalStatus.WITHDRAWN:
            return [f"{name} has already left this round."]
        status = (
            participant.approval_status.value if participant.approval_status else "none"
        )
        return [
            f"{name} cannot be withdrawn from this round: their status is {status}."
        ]

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
