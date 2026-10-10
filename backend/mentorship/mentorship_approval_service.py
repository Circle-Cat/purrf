"""The mentorship side of approvals: what the admin console asks of them.

The shared approval service runs the flow; this service scopes it to the
mentorship actions, so a request id from another part of Purrf cannot be
decided through a mentorship endpoint, and turns requests into what the
console shows: who raised it, who reviews it, which round it is about.
"""

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import ParticipantNoteTag
from backend.common.name_utils import user_display_name
from backend.mentorship.end_pair_handler import END_PAIR, pair_target
from backend.mentorship.exempt_matching_handler import (
    EXEMPT_MATCHING,
    exemption_target,
)
from backend.mentorship.mark_participant_handler import MARK_NO_SHOW, MARK_RED_FLAG
from backend.mentorship.publish_matching_handler import PUBLISH_MATCHING
from backend.mentorship.withdraw_participant_handler import WITHDRAW_PARTICIPANT

# Every action whose requests the mentorship console raises and decides. All
# of them are reviewed by holders of mentorship.approve.
MENTORSHIP_ACTIONS = (
    PUBLISH_MATCHING,
    EXEMPT_MATCHING,
    WITHDRAW_PARTICIPANT,
    MARK_NO_SHOW,
    MARK_RED_FLAG,
    END_PAIR,
)

# The actions raised about one person in one round from their detail page,
# listed there while they wait.
PARTICIPANT_ACTIONS = (WITHDRAW_PARTICIPANT, MARK_NO_SHOW, MARK_RED_FLAG)

_MARK_ACTIONS = {
    ParticipantNoteTag.NO_SHOW: MARK_NO_SHOW,
    ParticipantNoteTag.RED_FLAG: MARK_RED_FLAG,
}

_OWN_WITHDRAWAL = "The person being withdrawn cannot review their own withdrawal."
_OWN_MARK = "The person being marked cannot review a mark on themselves."
_IN_PAIR = "Neither person in the pair can review a request to end it."

# The requests whose subject may not be their reviewer, with the refusal.
_SUBJECT_MAY_NOT_REVIEW = {
    WITHDRAW_PARTICIPANT: _OWN_WITHDRAWAL,
    MARK_NO_SHOW: _OWN_MARK,
    MARK_RED_FLAG: _OWN_MARK,
}


class MentorshipApprovalService:
    def __init__(
        self,
        approval_service,
        matching_storage,
        users_repository,
        rounds_repository,
        pairs_repository,
        logger,
    ):
        """
        Args:
            approval_service (ApprovalService): Runs the approval flow.
            matching_storage: Finds a round's current run.
            users_repository: Names the people on a request.
            rounds_repository: Names the round a request is about.
            pairs_repository: Reads the pair a request to end it names.
            logger: Injected logger.
        """
        self.approval_service = approval_service
        self.matching_storage = matching_storage
        self.users_repository = users_repository
        self.rounds_repository = rounds_repository
        self.pairs_repository = pairs_repository
        self.logger = logger

    async def list_reviewers(self, session, actor_id: int) -> list[dict]:
        """Who a mentorship request can be sent to, the asker excepted.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): The would-be raiser.

        Returns:
            list[dict]: ``user_id`` and ``name``, by name.
        """
        people = await self.approval_service.list_reviewers(
            session, PUBLISH_MATCHING, exclude_user_id=actor_id
        )
        reviewers = [{"user_id": p.user_id, "name": _name(p)} for p in people]
        return sorted(reviewers, key=lambda r: (r["name"].lower(), r["user_id"]))

    async def list_mine(self, session, actor_id: int) -> list[dict]:
        """The mentorship requests waiting on this reviewer, oldest first.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): The reviewer.

        Returns:
            list[dict]: One per pending request.
        """
        rows = await self.approval_service.list_pending_for_reviewer(
            session, actor_id, MENTORSHIP_ACTIONS
        )
        return await self._describe(session, rows)

    async def request_publish(
        self,
        session,
        *,
        round_id: int,
        actor_id: int,
        reviewer_id: int,
        reason: str,
    ) -> dict:
        """Ask a reviewer to approve publishing the round's current run. Commits.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round.
            actor_id (int): Who is asking.
            reviewer_id (int): Who should decide.
            reason (str): Why.

        Returns:
            dict: The new request.

        Raises:
            ValueError: The round has no run, or the reviewer or reason is
                refused.
            ConflictError: The run cannot be published now, or is already
                waiting for approval.
        """
        run_id = self.matching_storage.current_run_id(round_id)
        if run_id is None:
            raise ValueError(f"Round {round_id} has no matching result to publish.")
        row = await self.approval_service.raise_request(
            session,
            action=PUBLISH_MATCHING,
            raised_by=actor_id,
            target_id=run_id,
            payload={"round_id": round_id},
            reason=reason,
            reviewer_id=reviewer_id,
        )
        return (await self._describe(session, [row]))[0]

    async def request_exemption(
        self,
        session,
        *,
        round_id: int,
        user_id: int,
        actor_id: int,
        reviewer_id: int,
        reason: str,
    ) -> dict:
        """Ask a reviewer to exempt a person from the history check in a
        round. Commits.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round.
            user_id (int): The person.
            actor_id (int): Who is asking.
            reviewer_id (int): Who should decide.
            reason (str): Why.

        Returns:
            dict: The new request.

        Raises:
            ValueError: The reviewer or reason is refused.
            ConflictError: The round is not in progress, the person does not
                need an exemption, or one is already waiting for approval.
        """
        row = await self.approval_service.raise_request(
            session,
            action=EXEMPT_MATCHING,
            raised_by=actor_id,
            target_id=exemption_target(round_id, user_id),
            payload={"round_id": round_id, "user_id": user_id},
            reason=reason,
            reviewer_id=reviewer_id,
        )
        return (await self._describe(session, [row]))[0]

    async def request_withdrawal(
        self,
        session,
        *,
        round_id: int,
        user_id: int,
        actor_id: int,
        reviewer_id: int,
        reason: str,
    ) -> dict:
        """Ask a reviewer to approve withdrawing a person from a round.
        Commits.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round.
            user_id (int): The person.
            actor_id (int): Who is asking.
            reviewer_id (int): Who should decide; not the person.
            reason (str): Why, possibly empty.

        Returns:
            dict: The new request.

        Raises:
            ValueError: The reviewer is the person, or is refused.
            ConflictError: The round is not in progress, the person is not
                still in it, or a withdrawal is already waiting.
        """
        if reviewer_id == user_id:
            raise ValueError(_OWN_WITHDRAWAL)
        row = await self.approval_service.raise_request(
            session,
            action=WITHDRAW_PARTICIPANT,
            raised_by=actor_id,
            target_id=exemption_target(round_id, user_id),
            payload={"round_id": round_id, "user_id": user_id},
            reason=reason,
            reviewer_id=reviewer_id,
        )
        return (await self._describe(session, [row]))[0]

    async def request_mark(
        self,
        session,
        *,
        round_id: int,
        user_id: int,
        tag: str,
        pair_id: int | None,
        actor_id: int,
        reviewer_id: int,
        reason: str,
    ) -> dict:
        """Ask a reviewer to approve marking a person in a round as a no
        show, or raising a red flag on them. Commits.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round.
            user_id (int): The person.
            tag (str): ``no_show`` or ``red_flag``.
            pair_id (int | None): The pair it is about, if any.
            actor_id (int): Who is asking.
            reviewer_id (int): Who should decide; not the person.
            reason (str): Why, possibly empty.

        Returns:
            dict: The new request.

        Raises:
            ValueError: Not a mark, the reviewer is the person, or the
                reviewer is refused.
            ConflictError: The person may not carry the mark, the pair is
                missing or not theirs, or the same mark already waits.
        """
        action = _MARK_ACTIONS.get(tag)
        if action is None:
            raise ValueError(f"{tag} is not a mark.")
        if reviewer_id == user_id:
            raise ValueError(_OWN_MARK)
        payload = {"round_id": round_id, "user_id": user_id}
        if pair_id is not None:
            payload["pair_id"] = pair_id
        row = await self.approval_service.raise_request(
            session,
            action=action,
            raised_by=actor_id,
            target_id=exemption_target(round_id, user_id),
            payload=payload,
            reason=reason,
            reviewer_id=reviewer_id,
        )
        return (await self._describe(session, [row]))[0]

    async def request_end_pair(
        self,
        session,
        *,
        round_id: int,
        user_id: int,
        pair_id: int,
        actor_id: int,
        reviewer_id: int,
        reason: str,
    ) -> dict:
        """Ask a reviewer to approve ending one of a person's pairs in a
        round. Commits.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round.
            user_id (int): Whose page it is raised from; one of the pair.
            pair_id (int): The pair.
            actor_id (int): Who is asking.
            reviewer_id (int): Who should decide; neither of the pair.
            reason (str): Why, possibly empty.

        Returns:
            dict: The new request.

        Raises:
            ValueError: The reviewer is one of the pair, or is refused.
            ConflictError: The pair is not this person's in the round, has
                ended, the round is not in progress, or a request to end it
                already waits.
        """
        pair = await self.pairs_repository.get_pair_by_id(session, pair_id)
        if (
            pair is None
            or pair.round_id != round_id
            or user_id not in (pair.mentor_id, pair.mentee_id)
        ):
            raise ConflictError(
                f"Pair {pair_id} is not one of this person's pairs in this round."
            )
        if reviewer_id in (pair.mentor_id, pair.mentee_id):
            raise ValueError(_IN_PAIR)
        row = await self.approval_service.raise_request(
            session,
            action=END_PAIR,
            raised_by=actor_id,
            target_id=pair_target(pair_id),
            payload={
                "round_id": round_id,
                "pair_id": pair_id,
                "mentor_id": pair.mentor_id,
                "mentee_id": pair.mentee_id,
            },
            reason=reason,
            reviewer_id=reviewer_id,
        )
        return (await self._describe(session, [row]))[0]

    async def pending_for_participant(
        self, session, round_id: int, user_id: int, pair_ids=()
    ) -> list[dict]:
        """The requests about this person in this round waiting on a
        reviewer, for their detail page: those about them, then those about
        one of their pairs.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round.
            user_id (int): The person.
            pair_ids (Iterable[int]): Their pairs in the round.

        Returns:
            list[dict]: One per pending request, described like list_mine.
        """
        rows = []
        for action in PARTICIPANT_ACTIONS:
            row = await self.approval_service.get_pending_for_target(
                session, action, exemption_target(round_id, user_id)
            )
            if row is not None:
                rows.append(row)
        targets = [pair_target(pair_id) for pair_id in pair_ids]
        if targets:
            pending = await self.approval_service.list_pending_for_targets(
                session, END_PAIR, targets
            )
            rows.extend(pending[t] for t in targets if t in pending)
        return await self._describe(session, rows)

    async def pending_exemptions(
        self, session, round_id: int, user_ids
    ) -> dict[int, dict]:
        """The exemption request waiting on each of these people in the
        round, for the rows of the Needs exemption list.

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The round.
            user_ids (Iterable[int]): The people.

        Returns:
            dict[int, dict]: user_id -> request, for those with one.
        """
        pending = await self.approval_service.list_pending_for_targets(
            session,
            EXEMPT_MATCHING,
            [exemption_target(round_id, user_id) for user_id in user_ids],
        )
        described = await self._describe(session, list(pending.values()))
        return {d["person"]["user_id"]: d for d in described}

    async def reassign(
        self, session, *, request_id: int, actor_id: int, reviewer_id: int
    ) -> dict:
        """Hand a mentorship request to another reviewer. Commits.

        Raises:
            ValueError: Not a mentorship request, a refused reviewer, or the
                person a withdrawal or mark is about, or either person in a pair
                being ended.
            PermissionError: The caller did not raise it.
            ConflictError: It is no longer pending.
        """
        row = await self._mentorship_request(session, request_id)
        refusal = _SUBJECT_MAY_NOT_REVIEW.get(row.action)
        if refusal and reviewer_id == int(row.payload["user_id"]):
            raise ValueError(refusal)
        if row.action == END_PAIR and reviewer_id in (
            int(row.payload["mentor_id"]),
            int(row.payload["mentee_id"]),
        ):
            raise ValueError(_IN_PAIR)
        row = await self.approval_service.reassign(
            session, request_id=request_id, actor_id=actor_id, reviewer_id=reviewer_id
        )
        return (await self._describe(session, [row]))[0]

    async def decide(
        self,
        session,
        *,
        request_id: int,
        actor_id: int,
        approve: bool,
        comment: str | None,
    ) -> dict:
        """Approve or reject a mentorship request. Commits.

        Raises:
            ValueError: Not a mentorship request, or a rejection with no
                reason.
            PermissionError: The caller is not its named reviewer.
            ConflictError: It is no longer pending, or what it asks for can
                no longer be done.
        """
        await self._mentorship_request(session, request_id)
        row = await self.approval_service.decide(
            session,
            request_id=request_id,
            actor_id=actor_id,
            approve=approve,
            comment=comment,
        )
        return (await self._describe(session, [row]))[0]

    async def withdraw(self, session, *, request_id: int, actor_id: int) -> dict:
        """Take back a mentorship request nobody has decided. Commits.

        Raises:
            ValueError: Not a mentorship request.
            PermissionError: The caller did not raise it.
            ConflictError: It is no longer pending.
        """
        await self._mentorship_request(session, request_id)
        row = await self.approval_service.withdraw(
            session, request_id=request_id, actor_id=actor_id
        )
        return (await self._describe(session, [row]))[0]

    async def _mentorship_request(self, session, request_id: int):
        row = await self.approval_service.get_request(session, request_id)
        if row.action not in MENTORSHIP_ACTIONS:
            # Said the same way as a missing id: this endpoint has no business
            # confirming that another part of Purrf has a request by this id.
            raise ValueError(f"No approval request {request_id}")
        return row

    async def _describe(self, session, rows) -> list[dict]:
        user_ids = (
            {u for row in rows for u in (row.raised_by, row.reviewer_id)}
            | {int(row.payload["user_id"]) for row in rows if "user_id" in row.payload}
            | {
                int(row.payload[key])
                for row in rows
                for key in ("mentor_id", "mentee_id")
                if key in row.payload
            }
        )
        people = await self.users_repository.get_all_by_ids(session, list(user_ids))
        names = {p.user_id: _name(p) for p in people}
        round_names: dict[int, str | None] = {}
        for row in rows:
            round_id = int(row.payload["round_id"])
            if round_id not in round_names:
                round_ = await self.rounds_repository.get_by_round_id(session, round_id)
                round_names[round_id] = round_.name if round_ is not None else None

        def person(user_id):
            return {"user_id": user_id, "name": names.get(user_id)}

        return [
            {
                "request_id": row.request_id,
                "action": row.action,
                "status": row.status,
                "round": {
                    "round_id": int(row.payload["round_id"]),
                    "name": round_names[int(row.payload["round_id"])],
                },
                "target_id": row.target_id,
                "pair_id": row.payload.get("pair_id"),
                "pair": {
                    "pair_id": int(row.payload["pair_id"]),
                    "mentor": person(int(row.payload["mentor_id"])),
                    "mentee": person(int(row.payload["mentee_id"])),
                }
                if "mentor_id" in row.payload
                else None,
                "person": person(int(row.payload["user_id"]))
                if "user_id" in row.payload
                else None,
                "raised_by": person(row.raised_by),
                "reviewer": person(row.reviewer_id),
                "reason": row.reason,
                "decision_comment": row.decision_comment,
                "created_at": row.created_at,
                "decided_at": row.decided_at,
            }
            for row in rows
        ]


def _name(user) -> str:
    return user_display_name(
        first_name=user.first_name,
        last_name=user.last_name,
        preferred_name=user.preferred_name,
    )
