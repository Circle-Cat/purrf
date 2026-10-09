"""A matching exemption, as an approval.

A request is about one person in one round, while the round is in progress
and only their history keeps them out of its matching pool. Approving it
writes a matching_exemption note on them in that round, which the
eligibility check reads: the history check is lifted in that round, and in
later rounds nothing before it counts.
"""

from datetime import datetime, timezone

from backend.approval.approval_handler import ApprovalHandler
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    MentorshipEvent,
    ParticipantNoteTag,
)
from backend.common.name_utils import user_display_name
from backend.common.permissions import Permission
from backend.mentorship.publish_matching_handler import MENTORSHIP_ROUND_SUBJECT
from backend.mentorship.round_windows import is_in_progress

EXEMPT_MATCHING = "exempt_matching"


def exemption_target(round_id: int, user_id: int) -> str:
    """The target id of an exemption: the person in the round."""
    return f"{round_id}:{user_id}"


class ExemptMatchingHandler(ApprovalHandler):
    """The ``exempt_matching`` action. Its payload carries the round and the
    person; its target id is the two together."""

    action = EXEMPT_MATCHING
    target_type = "round_participant"
    subject_type = MENTORSHIP_ROUND_SUBJECT
    raised_event = MentorshipEvent.APPROVAL_REQUESTED
    reassigned_event = MentorshipEvent.APPROVAL_REASSIGNED
    decided_event = MentorshipEvent.APPROVAL_DECIDED
    review_permission = Permission.MENTORSHIP_APPROVE

    def __init__(
        self,
        matching_eligibility_service,
        rounds_repository,
        note_repository,
        users_repository,
        logger,
        participants_repository,
    ):
        """
        Args:
            matching_eligibility_service: Says who needs an exemption.
            rounds_repository: Reads the round, to check it is in progress.
            note_repository: Writes the exemption.
            users_repository: Names people in notes, refusals and emails.
            logger: Injected logger.
            participants_repository: Reads the person's registration, to refuse
                someone who has left.
        """
        self.matching_eligibility_service = matching_eligibility_service
        self.rounds_repository = rounds_repository
        self.note_repository = note_repository
        self.users_repository = users_repository
        self.logger = logger
        self.participants_repository = participants_repository

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
        """Refuse an exemption for a round not in progress, or for someone
        whose history is not the only thing keeping them out.

        Raises:
            ValueError: The payload or target id is malformed.
            ConflictError: The round is not in progress, the person has left
                it, or does not need an exemption in it.
        """
        round_id, user_id = payload.get("round_id"), payload.get("user_id")
        if not isinstance(round_id, int) or not isinstance(user_id, int):
            raise ValueError("An exemption request names its round and person.")
        if target_id != exemption_target(round_id, user_id):
            raise ValueError("An exemption request's target is its round and person.")
        problems = await self._problems(session, round_id, user_id)
        if problems:
            raise ConflictError(problems[0])

    async def problems_at_approval(self, session, request) -> list[str]:
        """The round still has to be in progress and the person still has to
        be in it and need the exemption.

        Returns:
            list[str]: One sentence per problem, empty when it may go ahead.
        """
        return await self._problems(
            session, int(request.payload["round_id"]), int(request.payload["user_id"])
        )

    async def execute(self, session, request, *, actor_id: int) -> None:
        """Write the exemption on the person in the round, by the approver."""
        round_id = int(request.payload["round_id"])
        user_id = int(request.payload["user_id"])
        names = await self._names(session, [request.raised_by, actor_id])
        await self.note_repository.create(
            session,
            user_id=user_id,
            round_id=round_id,
            author_user_id=actor_id,
            body=(
                "Exempted from the matching history check. Raised by "
                f"{names.get(request.raised_by, f'User {request.raised_by}')}, "
                f"reason: {request.reason or 'none given'}; approved by "
                f"{names.get(actor_id, f'User {actor_id}')}."
            ),
            tag=ParticipantNoteTag.MATCHING_EXEMPTION,
            request_id=request.request_id,
        )
        self.logger.info(
            "[ExemptMatchingHandler] round=%s user=%s by=%s",
            round_id,
            user_id,
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
        if (
            participant is not None
            and participant.approval_status == ApprovalStatus.WITHDRAWN
        ):
            name = (await self._names(session, [user_id])).get(user_id)
            return [f"{name or f'User {user_id}'} has left this round."]
        needing = await self.matching_eligibility_service.needs_exemption(
            session, round_id
        )
        if user_id not in needing:
            name = (await self._names(session, [user_id])).get(user_id)
            return [
                f"{name or f'User {user_id}'} does not need an exemption in this "
                "round: only someone kept out by their history alone does."
            ]
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
