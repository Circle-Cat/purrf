"""The mentorship side of approvals: what the admin console asks of them.

The shared approval service runs the flow; this service scopes it to the
mentorship actions, so a request id from another part of Purrf cannot be
decided through a mentorship endpoint, and turns requests into what the
console shows: who raised it, who reviews it, which round it is about.
"""

from backend.common.name_utils import user_display_name
from backend.mentorship.publish_matching_handler import PUBLISH_MATCHING

# Every action whose requests the mentorship console raises and decides. All
# of them are reviewed by holders of mentorship.approve.
MENTORSHIP_ACTIONS = (PUBLISH_MATCHING,)


class MentorshipApprovalService:
    def __init__(
        self,
        approval_service,
        matching_storage,
        users_repository,
        rounds_repository,
        logger,
    ):
        """
        Args:
            approval_service (ApprovalService): Runs the approval flow.
            matching_storage: Finds a round's current run.
            users_repository: Names the people on a request.
            rounds_repository: Names the round a request is about.
            logger: Injected logger.
        """
        self.approval_service = approval_service
        self.matching_storage = matching_storage
        self.users_repository = users_repository
        self.rounds_repository = rounds_repository
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

    async def reassign(
        self, session, *, request_id: int, actor_id: int, reviewer_id: int
    ) -> dict:
        """Hand a mentorship request to another reviewer. Commits.

        Raises:
            ValueError: Not a mentorship request, or a refused reviewer.
            PermissionError: The caller did not raise it.
            ConflictError: It is no longer pending.
        """
        await self._mentorship_request(session, request_id)
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
        user_ids = {u for row in rows for u in (row.raised_by, row.reviewer_id)}
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
