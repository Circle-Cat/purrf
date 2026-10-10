"""Marking a person as a no show, or raising a red flag on them, as an
approval.

A request is about one person in one round while the round is in progress.
Approving it writes one tagged note on them, by the approver, and nothing
else changes: the matching eligibility check reads the note and keeps them
out of matching until an exemption granted after it. Nothing undoes a mark.
"""

from datetime import datetime, timezone
from typing import ClassVar

from backend.approval.approval_handler import ApprovalHandler
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import MentorshipEvent, ParticipantNoteTag
from backend.common.name_utils import user_display_name
from backend.common.permissions import Permission
from backend.mentorship.exempt_matching_handler import exemption_target
from backend.mentorship.publish_matching_handler import MENTORSHIP_ROUND_SUBJECT
from backend.mentorship.round_windows import is_in_progress

MARK_NO_SHOW = "mark_no_show"
MARK_RED_FLAG = "mark_red_flag"


class MarkParticipantHandler(ApprovalHandler):
    """What the two marks share. A subclass names its action, its tag, what
    the mark is called and how the note says it, whether it has to be about
    one of the person's pairs, and who may carry it."""

    tag: ClassVar[ParticipantNoteTag]
    noun: ClassVar[str]
    recorded: ClassVar[str]
    pair_required: ClassVar[bool]

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
        rounds_repository,
        note_repository,
        users_repository,
        logger,
    ):
        """
        Args:
            participants_repository: Reads the registration.
            pairs_repository: Reads the person's pairs in the round.
            rounds_repository: Reads the round, to check it is in progress.
            note_repository: Writes the mark.
            users_repository: Names people in notes, refusals and emails.
            logger: Injected logger.
        """
        self.participants_repository = participants_repository
        self.pairs_repository = pairs_repository
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
        """Refuse a mark for a round not in progress, on someone who may not
        carry it, or about a pair that is not theirs.

        Raises:
            ValueError: The payload or target id is malformed.
            ConflictError: Any of the conditions above.
        """
        round_id, user_id = payload.get("round_id"), payload.get("user_id")
        pair_id = payload.get("pair_id")
        if not isinstance(round_id, int) or not isinstance(user_id, int):
            raise ValueError(f"A {self.noun} request names its round and person.")
        if pair_id is not None and not isinstance(pair_id, int):
            raise ValueError(f"A {self.noun} request names its pair by id.")
        if target_id != exemption_target(round_id, user_id):
            raise ValueError(f"A {self.noun} request's target is its round and person.")
        problems = await self._problems(session, round_id, user_id, pair_id)
        if problems:
            raise ConflictError(problems[0])

    async def problems_at_approval(self, session, request) -> list[str]:
        """The round still has to be in progress, the person still
        registered, and the pair named still theirs.

        Returns:
            list[str]: One sentence per problem, empty when it may go ahead.
        """
        pair_id = request.payload.get("pair_id")
        return await self._problems(
            session,
            int(request.payload["round_id"]),
            int(request.payload["user_id"]),
            None if pair_id is None else int(pair_id),
        )

    async def execute(self, session, request, *, actor_id: int) -> None:
        """Write the mark on the person in the round, by the approver. Does
        not commit."""
        round_id = int(request.payload["round_id"])
        user_id = int(request.payload["user_id"])
        pair_id = request.payload.get("pair_id")
        names = await self._names(session, [request.raised_by, actor_id])
        await self.note_repository.create(
            session,
            user_id=user_id,
            round_id=round_id,
            author_user_id=actor_id,
            body=(
                f"{self.recorded}. Raised by "
                f"{names.get(request.raised_by, f'User {request.raised_by}')}, "
                f"reason: {request.reason or 'none given'}; approved by "
                f"{names.get(actor_id, f'User {actor_id}')}."
            ),
            tag=self.tag,
            pair_id=None if pair_id is None else int(pair_id),
            request_id=request.request_id,
        )
        self.logger.info(
            "[%s] round=%s user=%s pair=%s by=%s",
            type(self).__name__,
            round_id,
            user_id,
            pair_id,
            actor_id,
        )

    def _person_problem(self, name: str, pairs: list) -> str | None:
        """Why this person may not carry the mark, beyond being registered."""
        return None

    async def _problems(
        self, session, round_id: int, user_id: int, pair_id: int | None
    ) -> list[str]:
        round_ = await self.rounds_repository.get_by_round_id(session, round_id)
        if round_ is None:
            return [f"Mentorship round {round_id} does not exist."]
        if not is_in_progress(round_, datetime.now(timezone.utc)):
            return ["The round is not in progress."]
        name = (await self._names(session, [user_id])).get(user_id) or f"User {user_id}"
        participant = await self.participants_repository.get_by_user_id_and_round_id(
            session, user_id, round_id
        )
        if participant is None:
            return [f"{name} is not registered for this round."]
        pairs = await self.pairs_repository.get_pairs_by_user_and_round(
            session=session, user_id=user_id, round_id=round_id
        )
        problem = self._person_problem(name, pairs)
        if problem:
            return [problem]
        if pair_id is None:
            if self.pair_required:
                return [f"Say which of {name}'s pairs the {self.noun} is about."]
            return []
        if pair_id not in {pair.pair_id for pair in pairs}:
            return [f"Pair {pair_id} is not one of {name}'s pairs in this round."]
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


class MarkNoShowHandler(MarkParticipantHandler):
    """The ``mark_no_show`` action: someone who had a pair this round, ended
    or not, about one of those pairs."""

    action = MARK_NO_SHOW
    tag = ParticipantNoteTag.NO_SHOW
    noun = "no show"
    recorded = "Marked as a no show"
    pair_required = True

    def _person_problem(self, name: str, pairs: list) -> str | None:
        if not pairs:
            return f"{name} had no pair in this round."
        return None


class MarkRedFlagHandler(MarkParticipantHandler):
    """The ``mark_red_flag`` action: anyone registered for the round, about
    one of their pairs or not."""

    action = MARK_RED_FLAG
    tag = ParticipantNoteTag.RED_FLAG
    noun = "red flag"
    recorded = "Red flag raised"
    pair_required = False
