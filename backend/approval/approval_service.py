"""The approval flow every kind of approval shares.

Raising, reassigning, deciding and withdrawing all go through here; what a
request is about and what approving it does come from the handler registered
for its action (see approval_handler). Every public method that changes a
request commits, because each is the whole of what its endpoint does.
``supersede_pending`` is the exception: it closes requests inside a caller's
transaction and leaves the commit to that caller.
"""

from collections.abc import Collection, Iterable

from sqlalchemy.exc import IntegrityError

from backend.approval.approval_handler import ApprovalHandler
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.notification_management.event_recorder import record_event

# Sent with the 409 that refuses an approval whose checks no longer hold, so
# a page can tell it apart from "somebody else already decided this".
APPROVAL_CHECKS_FAILED = "approval_checks_failed"


class ApprovalService:
    def __init__(
        self,
        approval_request_repository,
        user_permissions_repository,
        users_repository,
        logger,
        handlers: Iterable[ApprovalHandler] = (),
    ):
        """
        Args:
            approval_request_repository (ApprovalRequestRepository): Reads and
                writes the requests.
            user_permissions_repository (UserPermissionsRepository): Finds who
                holds a handler's review permission.
            users_repository (UsersRepository): Checks that an assigned
                reviewer is still an active account.
            logger: Injected logger.
            handlers (Iterable[ApprovalHandler]): One per action.

        Raises:
            ValueError: When two handlers claim the same action.
        """
        self._requests = approval_request_repository
        self._permissions = user_permissions_repository
        self._users = users_repository
        self._logger = logger
        self._handlers: dict[str, ApprovalHandler] = {}
        for handler in handlers:
            if handler.action in self._handlers:
                raise ValueError(f"Two approval handlers for {handler.action!r}")
            self._handlers[handler.action] = handler

    def handler_for(self, action: str) -> ApprovalHandler:
        """The handler registered for an action.

        Args:
            action (str): The action.

        Returns:
            ApprovalHandler: Its handler.

        Raises:
            ValueError: When no handler is registered for it.
        """
        handler = self._handlers.get(action)
        if handler is None:
            raise ValueError(f"Unknown approval action {action!r}")
        return handler

    async def list_reviewers(self, session, action: str, *, exclude_user_id: int):
        """The people a request of this action can be sent to: active
        holders of its review permission, except the person asking.

        Args:
            session (AsyncSession): Active database async session.
            action (str): The action.
            exclude_user_id (int): The would-be raiser, who cannot review
                their own request.

        Returns:
            list[UsersEntity]: The candidates.

        Raises:
            ValueError: When the action's reviewer is assigned, not chosen.
        """
        handler = self.handler_for(action)
        if handler.review_permission is None:
            raise ValueError(f"The reviewer of {action!r} is assigned, not chosen")
        holders = await self._permissions.get_active_users_with_permission(
            session, handler.review_permission.value
        )
        return [u for u in holders if u.user_id != exclude_user_id]

    async def raise_request(
        self,
        session,
        *,
        action: str,
        raised_by: int,
        target_id: str,
        payload: dict | None,
        reason: str | None,
        reviewer_id: int | None,
    ) -> ApprovalRequestEntity:
        """Ask a reviewer to approve something. Commits.

        The reviewer is checked before the handler looks at the target, so a
        refusal about the target is only ever given to someone who has named
        a real reviewer: answered first, it would let anyone probe the state
        of targets by naming nobody in particular.

        Args:
            session (AsyncSession): Active database async session.
            action (str): What is being asked for.
            raised_by (int): Who is asking.
            target_id (str): What it is about.
            payload (dict | None): Whatever else the action needs.
            reason (str | None): Why, if the raiser says.
            reviewer_id (int | None): Who should decide it, for an action
                whose reviewer is chosen; None for one whose reviewer is
                assigned.

        Returns:
            ApprovalRequestEntity: The new pending request.

        Raises:
            ValueError: Unknown action, or a reviewer who cannot review it.
            ConflictError: The target already has a pending request.
        """
        handler = self.handler_for(action)
        payload = dict(payload or {})
        # Optional for every action: the reviewer reads it if there is one.
        reason = (reason or "").strip() or None

        if handler.review_permission is None:
            if reviewer_id is not None:
                raise ValueError("This request's reviewer is assigned, not chosen.")
            reviewer_id = await handler.assign_reviewer(
                session, raised_by=raised_by, target_id=target_id, payload=payload
            )
            await self._check_assigned_reviewer(session, reviewer_id, raised_by)
        else:
            await self._check_chosen_reviewer(
                session, handler, reviewer_id, raised_by=raised_by
            )

        await handler.check_raise(
            session, raised_by=raised_by, target_id=target_id, payload=payload
        )
        if await self._requests.get_pending_for_target(
            session, action, handler.target_type, target_id
        ):
            raise ConflictError("This is already waiting for approval.")
        try:
            row = await self._requests.create(
                session,
                action=action,
                target_type=handler.target_type,
                target_id=target_id,
                payload=payload,
                reason=reason,
                raised_by=raised_by,
                reviewer_id=reviewer_id,
            )
        except IntegrityError as exc:
            # A concurrent raise on the same target got there between our
            # check and this write; the partial unique index refused ours.
            raise ConflictError("This is already waiting for approval.") from exc

        await record_event(
            session,
            subject_type=handler.subject_type,
            subject_id=handler.subject_id(row),
            actor_id=raised_by,
            event_type=handler.raised_event,
            details={
                **await handler.event_details(session, row),
                "requestId": row.request_id,
                "action": action,
            },
        )
        await session.commit()
        return await self._requests.get(session, row.request_id)

    async def reassign(
        self, session, *, request_id: int, actor_id: int, reviewer_id: int
    ) -> ApprovalRequestEntity:
        """Hand a pending request to a different reviewer. Commits.

        Args:
            session (AsyncSession): Active database async session.
            request_id (int): The request.
            actor_id (int): Must be the raiser.
            reviewer_id (int): The new reviewer.

        Returns:
            ApprovalRequestEntity: The request, now naming the new reviewer.

        Raises:
            ValueError: Unknown request, or a reviewer who cannot review it.
            PermissionError: The caller is not the raiser, or this action's
                reviewer cannot be changed.
            ConflictError: The request is no longer pending.
        """
        row = await self._load(session, request_id)
        handler = self.handler_for(row.action)
        action, subject_id = row.action, handler.subject_id(row)
        extra = await handler.event_details(session, row)
        if row.raised_by != actor_id:
            raise PermissionError("Only the person who raised this can reassign it.")
        if not handler.raiser_may_reassign:
            raise PermissionError("This request's reviewer cannot be changed.")
        self._require_pending(row)
        if reviewer_id == row.reviewer_id:
            raise ValueError("That person is already the reviewer.")
        await self._check_chosen_reviewer(
            session, handler, reviewer_id, raised_by=row.raised_by
        )

        previous_reviewer_id = row.reviewer_id
        if not await self._requests.set_reviewer(session, request_id, reviewer_id):
            raise ConflictError("This request has already been closed.")
        await record_event(
            session,
            subject_type=handler.subject_type,
            subject_id=subject_id,
            actor_id=actor_id,
            event_type=handler.reassigned_event,
            details={
                **extra,
                "requestId": request_id,
                "action": action,
                "previousReviewerId": previous_reviewer_id,
            },
        )
        await session.commit()
        return await self._requests.get(session, request_id)

    async def decide(
        self,
        session,
        *,
        request_id: int,
        actor_id: int,
        approve: bool,
        comment: str | None,
    ) -> ApprovalRequestEntity:
        """Approve or reject a pending request. Commits.

        Only the named reviewer may decide, whatever else they hold: the
        check is on who they are, so a super admin is refused like anyone
        else. Approving re-checks with the handler and acts in the same
        transaction that closes the request.

        Args:
            session (AsyncSession): Active database async session.
            request_id (int): The request.
            actor_id (int): Must be the named reviewer.
            approve (bool): True to approve, False to reject.
            comment (str | None): Why. Required to reject.

        Returns:
            ApprovalRequestEntity: The closed request.

        Raises:
            ValueError: Unknown request, or a rejection with no reason.
            PermissionError: The caller is not the named reviewer.
            ConflictError: The request is no longer pending, or the
                handler's checks no longer hold (code
                APPROVAL_CHECKS_FAILED); the request stays pending.
        """
        row = await self._load(session, request_id)
        handler = self.handler_for(row.action)
        action, subject_id = row.action, handler.subject_id(row)
        extra = await handler.event_details(session, row)
        if row.reviewer_id != actor_id:
            self._logger.warning(
                "Refused decision on approval request_id=%s by non-reviewer user_id=%s",
                request_id,
                actor_id,
            )
            raise PermissionError("Only the named reviewer may decide this request.")
        self._require_pending(row)
        comment = (comment or "").strip() or None

        if approve:
            problems = await handler.problems_at_approval(session, row)
            if problems:
                raise ConflictError(" ".join(problems), code=APPROVAL_CHECKS_FAILED)
            await handler.execute(session, row, actor_id=actor_id)
            status = ApprovalRequestStatus.APPROVED
        else:
            if comment is None:
                raise ValueError("Give a reason for rejecting the request.")
            await handler.revert(session, row)
            status = ApprovalRequestStatus.REJECTED

        await self._close(session, row, status, actor_id, comment)
        await record_event(
            session,
            subject_type=handler.subject_type,
            subject_id=subject_id,
            actor_id=actor_id,
            event_type=handler.decided_event,
            details={
                **extra,
                "requestId": request_id,
                "action": action,
                "decision": status.value,
            },
        )
        await session.commit()
        closed = await self._requests.get(session, request_id)
        if approve:
            try:
                await handler.after_commit(closed)
            except Exception:
                self._logger.exception(
                    "After-commit step failed for approved request_id=%s",
                    request_id,
                )
        return closed

    async def withdraw(
        self, session, *, request_id: int, actor_id: int
    ) -> ApprovalRequestEntity:
        """Take back a request nobody has decided yet. Commits.

        Args:
            session (AsyncSession): Active database async session.
            request_id (int): The request.
            actor_id (int): Must be the raiser.

        Returns:
            ApprovalRequestEntity: The withdrawn request.

        Raises:
            ValueError: Unknown request.
            PermissionError: The caller is not the raiser.
            ConflictError: The request is no longer pending.
        """
        row = await self._load(session, request_id)
        handler = self.handler_for(row.action)
        action, subject_id = row.action, handler.subject_id(row)
        extra = await handler.event_details(session, row)
        if row.raised_by != actor_id:
            raise PermissionError("Only the person who raised this can withdraw it.")
        self._require_pending(row)

        await handler.revert(session, row)
        await self._close(session, row, ApprovalRequestStatus.WITHDRAWN, actor_id, None)
        await record_event(
            session,
            subject_type=handler.subject_type,
            subject_id=subject_id,
            actor_id=actor_id,
            event_type=handler.decided_event,
            details={
                **extra,
                "requestId": request_id,
                "action": action,
                "decision": ApprovalRequestStatus.WITHDRAWN.value,
            },
        )
        await session.commit()
        return await self._requests.get(session, request_id)

    async def supersede_pending(
        self, session, *, action: str, target_id: str, actor_id: int
    ) -> int:
        """Close the pending request on a target because its outcome was
        brought about directly. Does NOT commit: the caller does that once
        the direct action and this land together.

        Args:
            session (AsyncSession): Active database async session.
            action (str): The action.
            target_id (str): The target.
            actor_id (int): Who acted directly.

        Returns:
            int: How many requests were closed, 0 or 1.
        """
        handler = self.handler_for(action)
        row = await self._requests.get_pending_for_target(
            session, action, handler.target_type, target_id
        )
        if row is None:
            return 0
        closed = await self._requests.close(
            session,
            row.request_id,
            status=ApprovalRequestStatus.SUPERSEDED,
            decided_by=actor_id,
            decision_comment=None,
        )
        return 1 if closed else 0

    async def get_request(self, session, request_id: int) -> ApprovalRequestEntity:
        """One request by id, whatever its status.

        Args:
            session (AsyncSession): Active database async session.
            request_id (int): The request.

        Returns:
            ApprovalRequestEntity: The request.

        Raises:
            ValueError: No such request.
        """
        row = await self._requests.get(session, request_id)
        if row is None:
            raise ValueError(f"No approval request {request_id}")
        return row

    async def get_pending_for_target(
        self, session, action: str, target_id: str
    ) -> ApprovalRequestEntity | None:
        """The request a target is waiting on, so its page can lock it.

        Args:
            session (AsyncSession): Active database async session.
            action (str): The action.
            target_id (str): The target.

        Returns:
            ApprovalRequestEntity | None: The pending request, or None.
        """
        handler = self.handler_for(action)
        return await self._requests.get_pending_for_target(
            session, action, handler.target_type, target_id
        )

    async def get_latest_closed_for_target(
        self, session, action: str, target_id: str
    ) -> ApprovalRequestEntity | None:
        """The last closed request on a target, so its page can show why it
        was turned down.

        Args:
            session (AsyncSession): Active database async session.
            action (str): The action.
            target_id (str): The target.

        Returns:
            ApprovalRequestEntity | None: The newest closed request, or None.
        """
        handler = self.handler_for(action)
        return await self._requests.get_latest_closed_for_target(
            session, action, handler.target_type, target_id
        )

    async def list_pending_for_reviewer(
        self, session, reviewer_id: int, actions: Collection[str]
    ) -> list[ApprovalRequestEntity]:
        """The requests of these actions waiting on this reviewer.

        Args:
            session (AsyncSession): Active database async session.
            reviewer_id (int): The reviewer.
            actions (Collection[str]): Which actions to include.

        Returns:
            list[ApprovalRequestEntity]: Oldest first.
        """
        return await self._requests.list_pending_for_reviewer(
            session, reviewer_id, actions
        )

    async def list_pending_raised_by(
        self, session, raised_by: int, actions: Collection[str]
    ) -> list[ApprovalRequestEntity]:
        """The open requests of these actions this person raised.

        Args:
            session (AsyncSession): Active database async session.
            raised_by (int): The raiser.
            actions (Collection[str]): Which actions to include.

        Returns:
            list[ApprovalRequestEntity]: Oldest first.
        """
        return await self._requests.list_pending_raised_by(session, raised_by, actions)

    async def _load(self, session, request_id: int) -> ApprovalRequestEntity:
        row = await self._requests.get(session, request_id, for_update=True)
        if row is None:
            raise ValueError(f"No approval request {request_id}")
        return row

    @staticmethod
    def _require_pending(row: ApprovalRequestEntity) -> None:
        if row.status != ApprovalRequestStatus.PENDING:
            raise ConflictError("This request has already been closed.")

    async def _close(self, session, row, status, actor_id, comment) -> None:
        # The row is locked, so this only fails if something outside this
        # service changed it; refuse rather than act on a stale read.
        if not await self._requests.close(
            session,
            row.request_id,
            status=status,
            decided_by=actor_id,
            decision_comment=comment,
        ):
            raise ConflictError("This request has already been closed.")

    async def _check_chosen_reviewer(
        self, session, handler: ApprovalHandler, reviewer_id, *, raised_by: int
    ) -> None:
        if reviewer_id is None:
            raise ValueError("Name a reviewer for the request.")
        if reviewer_id == raised_by:
            raise ValueError("You cannot review your own request.")
        holders = await self._permissions.get_active_users_with_permission(
            session, handler.review_permission.value
        )
        if reviewer_id not in {u.user_id for u in holders}:
            raise ValueError("The reviewer named cannot review this request.")

    async def _check_assigned_reviewer(
        self, session, reviewer_id: int, raised_by: int
    ) -> None:
        if reviewer_id == raised_by:
            raise ValueError("You cannot review your own request.")
        reviewer = await self._users.get_user_by_user_id(session, reviewer_id)
        if reviewer is None or not reviewer.is_active or reviewer.is_blocked:
            raise ValueError("The reviewer for this request is not available.")
