"""Publishing a matching result, as an approval.

A request names the round's current run. Raising it needs a finished,
successful run that nobody is editing and whose result has no problems.
Approving re-checks that, checks every person being paired against the
database as it stands now, eligibility included, then writes the pairs and the new statuses in the
approval's transaction. Once that is committed, the round's pointer to the run
is cleared, so the results page goes back to "no run".
"""

from backend.approval.approval_handler import ApprovalHandler
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    MenteeActionStatus,
    MentorActionStatus,
    MentorshipEvent,
    PairStatus,
    ParticipantNoteTag,
)
from backend.common.name_utils import user_display_name
from backend.common.permissions import Permission
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.mentorship.matching_draft import apply_draft, problems
from backend.mentorship.matching_eligibility import IneligibleReason

PUBLISH_MATCHING = "publish_matching"
MENTORSHIP_ROUND_SUBJECT = "mentorship_round"

# The statuses a person may be paired from. REJECTED is someone who left the
# round; pairing them would hand a mentee to somebody who is gone.
_PAIRABLE = {
    ApprovalStatus.SIGNED_UP,
    ApprovalStatus.MATCHED,
    ApprovalStatus.UN_MATCHED,
}

# What the eligibility check holds against someone, as the end of a sentence
# about them. Blocked, deactivated, gone and over capacity are said above in
# words of their own.
_FINDING_WORDING = {
    IneligibleReason.QUIT_AFTER_MATCH: "quit after being matched in {where}",
    IneligibleReason.MEETINGS_SHORT: "was short of meetings in {where}",
    IneligibleReason.NO_SHOW: "was marked a no show in {where}",
    IneligibleReason.RED_FLAG: "has a red flag in {where}",
}


class PublishMatchingHandler(ApprovalHandler):
    """The ``publish_matching`` action. Its target is a run id; its payload
    carries the round."""

    action = PUBLISH_MATCHING
    target_type = "matching_run"
    subject_type = MENTORSHIP_ROUND_SUBJECT
    raised_event = MentorshipEvent.APPROVAL_REQUESTED
    reassigned_event = MentorshipEvent.APPROVAL_REASSIGNED
    decided_event = MentorshipEvent.APPROVAL_DECIDED
    review_permission = Permission.MENTORSHIP_APPROVE

    def __init__(
        self,
        matching_storage,
        pairs_repository,
        participants_repository,
        note_repository,
        users_repository,
        rounds_repository,
        logger,
        matching_eligibility_service,
    ):
        """
        Args:
            matching_storage: Where the run, its draft and its lock live.
            pairs_repository: Reads the round's pairs and writes the new ones.
            participants_repository: Reads and updates registrations.
            note_repository: Writes a status_change note per status changed.
            users_repository: Names people in notes and refusals.
            rounds_repository: Names the round in notifications.
            logger: Injected logger.
            matching_eligibility_service: Says what keeps each person out of matching now.
        """
        self.matching_storage = matching_storage
        self.pairs_repository = pairs_repository
        self.participants_repository = participants_repository
        self.note_repository = note_repository
        self.users_repository = users_repository
        self.rounds_repository = rounds_repository
        self.logger = logger
        self.matching_eligibility_service = matching_eligibility_service

    def subject_id(self, request) -> int:
        return int(request.payload["round_id"])

    async def event_details(self, session, request) -> dict:
        round_ = await self.rounds_repository.get_by_round_id(
            session, self.subject_id(request)
        )
        return {"roundName": round_.name if round_ is not None else None}

    async def check_raise(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> None:
        """Refuse publishing anything but the round's current, finished,
        successful run while nobody edits it and its result has no problems.

        Raises:
            ValueError: The payload names no round.
            ConflictError: Any of the conditions above does not hold.
        """
        round_id = payload.get("round_id")
        if not isinstance(round_id, int):
            raise ValueError("A publish request names its round.")
        refusal = self._run_refusal(round_id, target_id)
        if refusal:
            raise ConflictError(refusal)
        if self.matching_storage.edit_lock(target_id) is not None:
            raise ConflictError(
                "The result is being edited. Save or discard the changes first."
            )
        rows, slots = self._effective(target_id)
        if problems(rows, slots):
            raise ConflictError("Fix the problems listed before publishing.")

    async def problems_at_approval(self, session, request) -> list[str]:
        """Everything that has to still hold for the result to be published.

        Returns:
            list[str]: One sentence per problem, empty when it may go ahead.
        """
        round_id = self.subject_id(request)
        run_id = request.target_id
        refusal = self._run_refusal(round_id, run_id)
        if refusal:
            return [refusal]

        rows, slots = self._effective(run_id)
        if problems(rows, slots):
            return ["The result has problems to fix before it can be published."]

        pairs = _pairs_of(rows)
        paired_ids = {user_id for pair in pairs for user_id in pair}
        registrations = await self._registrations(session, round_id)
        names = await self._names(session, paired_ids)
        found: list[str] = []
        for user_id in sorted(paired_ids):
            registration = registrations.get(user_id)
            name = names.get(user_id, f"User {user_id}")
            if registration is None:
                found.append(f"{name} is not registered for this round.")
                continue
            user, participant = registration
            if user.is_blocked:
                found.append(f"{name} is blocked.")
            elif not user.is_active:
                found.append(f"{name}'s account is deactivated.")
            elif participant.approval_status not in _PAIRABLE:
                found.append(f"{name} has left this round.")

        existing = await self.pairs_repository.list_pairs_by_round(session, round_id)
        active = [p for p in existing if p.status == PairStatus.ACTIVE]
        taken = {p.mentee_id for p in active}
        held = {}
        for pair in active:
            held[pair.mentor_id] = held.get(pair.mentor_id, 0) + 1
        ever = {(p.mentor_id, p.mentee_id) for p in existing}
        adding = {}
        for mentor_id, mentee_id in pairs:
            adding[mentor_id] = adding.get(mentor_id, 0) + 1
            mentee = names.get(mentee_id, f"User {mentee_id}")
            mentor = names.get(mentor_id, f"User {mentor_id}")
            if mentee_id in taken:
                found.append(f"{mentee} already has a pair in this round.")
            elif (mentor_id, mentee_id) in ever:
                found.append(f"{mentee} and {mentor} were already paired this round.")
        for mentor_id, count in sorted(adding.items()):
            registration = registrations.get(mentor_id)
            if registration is None:
                continue
            cap = registration[1].max_partners or 1
            if held.get(mentor_id, 0) + count > cap:
                found.append(
                    f"{names.get(mentor_id, f'User {mentor_id}')} would have "
                    f"{held.get(mentor_id, 0) + count} mentees but takes {cap}."
                )
        found.extend(
            await self._eligibility_problems(session, round_id, paired_ids, names)
        )
        return found

    async def execute(self, session, request, *, actor_id: int) -> None:
        """Write the pairs and the statuses the published result implies.

        Every matched mentee gets an active pair with no meetings, both sides
        to confirm. The people paired become matched; everyone else the run
        was given who has no active pair afterwards becomes un_matched; anyone
        already in an active pair keeps their status. Each change of status
        is noted, written by the approver.
        """
        round_id = self.subject_id(request)
        rows, _ = self._effective(request.target_id)
        pairs = _pairs_of(rows)

        existing = await self.pairs_repository.get_active_pairs_by_round(
            session, round_id
        )
        already_paired = {
            user_id for p in existing for user_id in (p.mentor_id, p.mentee_id)
        }
        reasons = {
            int(mentee_id): row.recommendation_reason
            for mentee_id, row in rows.items()
            if row.mentor_id is not None
        }
        created = await self.pairs_repository.upsert_pairs_batch(
            session,
            [
                MentorshipPairsEntity(
                    round_id=round_id,
                    mentor_id=mentor_id,
                    mentee_id=mentee_id,
                    completed_count=0,
                    status=PairStatus.ACTIVE,
                    mentor_action_status=MentorActionStatus.PENDING,
                    mentee_action_status=MenteeActionStatus.PENDING,
                    recommendation_reason=reasons[mentee_id],
                )
                for mentor_id, mentee_id in pairs
            ],
        )
        pair_of_mentee = {pair.mentee_id: pair.pair_id for pair in created}

        paired = {user_id for pair in pairs for user_id in pair}
        in_run = {int(mentee_id) for mentee_id in rows} | {
            int(mentor_id)
            for mentor_id in self.matching_storage.read_all_people(
                request.target_id, "mentor"
            )
        }
        registrations = await self._registrations(session, round_id)
        names = await self._names(session, {request.raised_by, actor_id})
        by = (
            f"Raised by {names.get(request.raised_by, f'User {request.raised_by}')}"
            f", reason: {request.reason or 'none given'}; approved by "
            f"{names.get(actor_id, f'User {actor_id}')}."
        )
        for user_id in sorted(in_run):
            if user_id in paired:
                to = ApprovalStatus.MATCHED
            elif user_id in already_paired:
                continue
            else:
                to = ApprovalStatus.UN_MATCHED
            registration = registrations.get(user_id)
            if registration is None:
                continue
            participant = registration[1]
            before = participant.approval_status
            # Someone who left the round stays left; only a pairable status
            # moves, and only when it changes.
            if before not in _PAIRABLE or before == to:
                continue
            participant.approval_status = to
            await self.note_repository.create(
                session,
                user_id=user_id,
                round_id=round_id,
                author_user_id=actor_id,
                body=(
                    f"{before.value} -> {to.value} when the "
                    f"matching result was published. {by}"
                ),
                tag=ParticipantNoteTag.STATUS_CHANGE,
                pair_id=pair_of_mentee.get(user_id),
                request_id=request.request_id,
            )
        await session.flush()
        self.logger.info(
            "[PublishMatchingHandler] round=%s run=%s pairs=%d by=%s",
            round_id,
            request.target_id,
            len(pairs),
            actor_id,
        )

    async def after_commit(self, request) -> None:
        self.matching_storage.clear_round_pointer(
            self.subject_id(request), request.target_id
        )

    def _run_refusal(self, round_id: int, run_id: str) -> str | None:
        """Why this run cannot be published, or None if it is the round's
        current run and finished successfully."""
        if self.matching_storage.current_run_id(round_id) != run_id:
            return "This is no longer the round's latest matching run."
        try:
            reported = self.matching_storage.read_run_result(run_id)
        except ValueError:
            reported = None
        if reported is None or reported.status != "succeeded":
            return "Only a finished, successful matching run can be published."
        return None

    def _effective(self, run_id: str) -> tuple[dict, dict[str, int]]:
        """The run's result with the saved draft laid over it, and each
        mentor's slots as the run was given them."""
        rows = apply_draft(
            self.matching_storage.read_all_results(run_id),
            self.matching_storage.read_draft(run_id),
        )
        mentors = self.matching_storage.read_all_people(run_id, "mentor")
        slots = {
            mentor_id: record.max_partners or 1 for mentor_id, record in mentors.items()
        }
        return rows, slots

    async def _registrations(self, session, round_id: int) -> dict[int, tuple]:
        return {
            user.user_id: (user, participant)
            for user, participant in await self.participants_repository.list_round_registrations(
                session, round_id
            )
        }

    async def _eligibility_problems(
        self, session, round_id: int, paired_ids: set[int], names: dict[int, str]
    ) -> list[str]:
        """What the matching eligibility check holds now against the people
        this result pairs, such as a mark given since the run. Only the new
        pairs' people are checked: existing pairs are not this publish's."""
        assessed = await self.matching_eligibility_service.assess(session, round_id)
        round_names = {
            r.round_id: r.name
            for r in await self.rounds_repository.get_all_rounds(session)
        }
        found: list[str] = []
        for user_id in sorted(paired_ids):
            standing = assessed.get(user_id)
            if standing is None:
                continue
            name = names.get(user_id, f"User {user_id}")
            for finding in standing.findings:
                where = (
                    "this round"
                    if finding.round_id == round_id
                    else round_names.get(finding.round_id) or "an earlier round"
                )
                wording = _FINDING_WORDING[finding.reason].format(where=where)
                found.append(f"{name} {wording}.")
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


def _pairs_of(rows: dict) -> list[tuple[int, int]]:
    """(mentor_id, mentee_id) for every mentee the result gives a mentor."""
    return [
        (int(row.mentor_id), int(mentee_id))
        for mentee_id, row in sorted(rows.items(), key=lambda item: int(item[0]))
        if row.mentor_id is not None
    ]
