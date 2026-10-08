"""Blocking: the kernel that applies a block, and the read-side pre-flight.

``apply_block_kernel`` is the whole sanction with no application to hang it on.
It came out of ``BoardService.blacklist``, which was the same three consequences
plus one pinned triggering application; drop the anchor and this is what is
left. That recruiting route is gone now, but the kernel stays a module function
rather than a method so that a future caller outside this service costs nothing.

The kernel must never commit. Its callers each own their transaction (the
approval flow applies a block mid-transaction and records the decision after
it), and a commit here would leave a later failure unable to roll the block
back.
"""

from datetime import datetime, timezone

from backend.common.name_utils import display_name_of
from backend.common.permissions import Permission
from backend.common.recruiting_enums import ApplicationStage, RecruitingEvent
from backend.common.user_enums import USER_SUBJECT_TYPE, UserEvent
from backend.dto.block_dto import (
    BlockPreflightDto,
    BlockRequestDto,
    ReviewerOptionDto,
)
from backend.notification_management.event_recorder import record_event

# The approval action a block request is, and the kind of target it names.
BLOCK_USER = "block_user"
BLOCK_TARGET = "user"

# Where a block request can be raised from, and what the raiser must hold
# there. Standing on one domain's page is no standing on another's: a
# mentorship admin can ask for a block from a participant's page but not from
# a recruiting application, and a recruiter not the other way round.
RAISE_PERMISSION_BY_SOURCE: dict[str, Permission] = {
    "recruiting_application": Permission.RECRUITING_APPLICATION_ADVANCE,
    "mentorship_participant": Permission.MENTORSHIP_ADMIN_WRITE,
}


async def apply_block_kernel(
    session,
    *,
    actor_id: int,
    user_id: int,
    reason: str | None,
    users_repository,
    application_repository,
    application_submission_repository,
    application_interview_repository,
    interview_scheduling_service,
) -> None:
    """Block a user org-wide and close out everything the block reaches.

    Three consequences, in order: the block flags on the user, a sweep of every
    application they have, and the cancellation of every interview still ahead
    of them on the applications just swept. The block also locks them out of
    every Purrf page, not just applications, until an admin unblocks them.

    Each application is re-fetched FOR UPDATE so a concurrent stage decision on
    it cannot interleave. In-flight and already-HIRED rows get the full
    close-out (2026-07-22 decision, superseding the 2026-07-15 one that spared
    HIRED); already-rejected rows keep their stage but have the ``blacklisted``
    tag backfilled. Rows already tagged are left untouched so a re-run logs no
    duplicate activity -- which also keeps their meetings from being cancelled
    twice, since only swept rows reach the cancellation pass.

    Does NOT commit. See the module docstring.

    Args:
        session (AsyncSession): Active database async session.
        actor_id (int): The user performing the block, recorded as
            ``blocked_by`` and as every event's actor.
        user_id (int): The user being blocked.
        reason (str | None): Why, if anyone said: a request's reason is
            optional. Recorded on the user and on every event.
        users_repository (UsersRepository): The user row being blocked.
        application_repository (ApplicationRepository): The applications to
            sweep.
        application_submission_repository (ApplicationSubmissionRepository):
            Freezes the current submission of each row that is closed out.
        application_interview_repository (ApplicationInterviewRepository): The
            interviews booked on the swept applications.
        interview_scheduling_service (InterviewSchedulingService): Cancels
            them.

    Raises:
        ValueError: If no user exists with ``user_id``.
    """
    user = await users_repository.get_user_by_user_id(session, user_id)
    if user is None:
        raise ValueError(f"user {user_id} not found")
    user.is_blocked = True
    user.blocked_by = actor_id
    user.blocked_at = datetime.now(timezone.utc)
    user.blocked_reason = reason

    swept_application_ids = []
    rows = await application_repository.list_by_user(session, user_id)
    for candidate, _job in rows:
        locked = await application_repository.get_by_id(
            session, candidate.application_id, for_update=True
        )
        if locked is None or (locked.tags or {}).get("blacklisted"):
            continue
        from_stage = locked.stage
        locked.tags = {**(locked.tags or {}), "blacklisted": True}
        if locked.stage != ApplicationStage.REJECTED:
            # In-flight or HIRED: fully close it out. Already-rejected rows
            # keep their historical stage/round/sub_status and frozen
            # submission -- only the tag is backfilled.
            locked.stage = ApplicationStage.REJECTED
            locked.stage_entered_at = datetime.now(timezone.utc)
            locked.sub_status = None
            locked.current_round = 1
            await _freeze_current_submission(
                session, application_submission_repository, locked.application_id
            )
        await application_repository.update(session, locked)
        await record_event(
            session,
            subject_type="application",
            subject_id=locked.application_id,
            actor_id=actor_id,
            event_type=RecruitingEvent.BLACKLISTED,
            details={"fromStage": from_stage.value, "reason": reason},
        )
        swept_application_ids.append(locked.application_id)

    # Every meeting still ahead of us on the applications just swept is
    # cancelled outright, with no opt-out anywhere in the UI: the candidate is
    # banned org-wide, so none of those interviews is going to happen, and each
    # one left booked would sit live on the interviewer's and the candidate's
    # calendars while being unreachable in Purrf. Rows whose meeting has already
    # started are filtered out by `cancel_for_round` itself.
    interviews = await application_interview_repository.list_by_application_ids(
        session, swept_application_ids
    )
    for interview in interviews:
        await interview_scheduling_service.cancel_for_round(
            session,
            interview.application_id,
            interview.stage,
            interview.round,
            actor_id,
            via="blacklisted",
        )

    # The user-subject counterpart of the per-application events above. It
    # reaches nobody by design (see user_recipient_resolvers) -- it exists so
    # the account's own timeline says when and why this happened, which the
    # application events cannot: they belong to applications.
    await record_event(
        session,
        subject_type=USER_SUBJECT_TYPE,
        subject_id=user_id,
        actor_id=actor_id,
        event_type=UserEvent.BLOCKED,
        details={"reason": reason},
    )


async def _freeze_current_submission(
    session, application_submission_repository, application_id: int
):
    """Mark an application's current submission version as frozen.

    The same four lines as ``BoardService._freeze_current_submission``, which
    stays where it is because ``change_stage`` and ``set_sub_status`` still call
    it. Duplicated rather than given a third home: a shared module for four
    lines would buy an import edge between two packages and nothing else.

    Args:
        session (AsyncSession): Active database async session.
        application_submission_repository (ApplicationSubmissionRepository):
            Submission data access.
        application_id (int): The owning application.
    """
    current_sub = await application_submission_repository.get_current(
        session, application_id
    )
    if current_sub is not None:
        current_sub.is_frozen = True
        await application_submission_repository.update(session, current_sub)


class BlockService:
    """The block action and its pre-flight, for the account console."""

    def __init__(
        self,
        users_repository,
        application_repository,
        application_submission_repository,
        application_interview_repository,
        interview_scheduling_service,
        approval_service,
        user_permissions_repository,
        logger,
    ):
        """
        Args:
            users_repository (UsersRepository): The user being blocked.
            application_repository (ApplicationRepository): The applications a
                block sweeps, and the pre-flight's count.
            application_submission_repository (ApplicationSubmissionRepository):
                Freezes the submissions of closed-out applications.
            application_interview_repository (ApplicationInterviewRepository):
                The interviews a block cancels, and the pre-flight's list.
            interview_scheduling_service (InterviewSchedulingService): Cancels
                them.
            approval_service (ApprovalService): Runs block requests, through
                the ``block_user`` handler.
            user_permissions_repository (UserPermissionsRepository): Lists the
                USER_ADMIN holders a request can be sent to.
            logger (Logger): Injected logger.
        """
        self._users = users_repository
        self._applications = application_repository
        self._submissions = application_submission_repository
        self._interviews = application_interview_repository
        self._interview_scheduling = interview_scheduling_service
        self._approvals = approval_service
        self._permissions = user_permissions_repository
        self._logger = logger

    async def preflight(self, session, user_id: int) -> BlockPreflightDto:
        """What blocking this user is about to do, so it is never a surprise.

        Counts and dates only. Which job someone applied to is content, not
        state, and is not the operator's to see.

        Mirrors the sweep exactly: applications already tagged ``blacklisted``
        are excluded (an earlier block already handled them, and the sweep skips
        them), and interviews that have already started are excluded
        (``cancel_for_round`` leaves those alone). Promising anything else here
        would make the confirm dialog lie.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The user about to be blocked.

        Returns:
            BlockPreflightDto: How many applications will close out, and when
                the interviews that will be cancelled are, soonest first.
        """
        rows = await self._applications.list_by_user(session, user_id)
        live = [
            application
            for application, _job in rows
            if not (application.tags or {}).get("blacklisted")
        ]
        interviews = await self._interviews.list_by_application_ids(
            session, [application.application_id for application in live]
        )
        now = datetime.now(timezone.utc)
        return BlockPreflightDto(
            application_count=len(live),
            interview_times=sorted(
                interview.start_at
                for interview in interviews
                if interview.start_at > now
            ),
        )

    async def apply_block(
        self, session, *, actor_id: int, user_id: int, reason: str | None
    ) -> None:
        """Apply a block. Does NOT commit -- see the module docstring.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): The user performing the block.
            user_id (int): The user being blocked.
            reason (str | None): Why.

        Raises:
            ValueError: If no user exists with ``user_id``.
        """
        await apply_block_kernel(
            session,
            actor_id=actor_id,
            user_id=user_id,
            reason=reason,
            users_repository=self._users,
            application_repository=self._applications,
            application_submission_repository=self._submissions,
            application_interview_repository=self._interviews,
            interview_scheduling_service=self._interview_scheduling,
        )

    # -- the request-and-approval flow --------------------------------------

    async def raise_request(
        self,
        session,
        *,
        actor_id: int,
        user_id: int,
        reason: str | None,
        reviewer_id: int,
        raised_from: str,
    ) -> BlockRequestDto:
        """Ask a named reviewer to block someone. Commits.

        The reviewer is named, not implied: a queue addressed to a permission
        is a queue addressed to nobody. They must be someone other than the
        raiser and the target, and must actively hold
        ``Permission.USER_ADMIN``, or the request would be a dead letter.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): The person raising it.
            user_id (int): The person they want blocked.
            reason (str | None): Why, if they say.
            reviewer_id (int): The USER_ADMIN holder asked to decide.
            raised_from (str): One of ``RAISE_PERMISSION_BY_SOURCE``: the
                domain page it came from, shown to the reviewer.

        Returns:
            BlockRequestDto: The new pending request.

        Raises:
            PermissionError: If the raiser names themselves as the target.
            ValueError: If the target is unknown or already blocked, the
                reviewer is not an eligible USER_ADMIN holder, or
                ``raised_from`` is not a known source.
            ConflictError: If a request against this person is already
                awaiting a decision.
        """
        if user_id == actor_id:
            # Not a guardrail against self-harm -- it is what stops the
            # refusals below from being a probe. Someone who suspects a request
            # names them could otherwise learn it exists by raising one.
            raise PermissionError("You cannot raise a block request about yourself")
        if raised_from not in RAISE_PERMISSION_BY_SOURCE:
            raise ValueError(f"Unknown raised_from: {raised_from!r}")
        self._refuse_target_as_reviewer(reviewer_id, user_id)
        # The approval service checks the reviewer before the target on
        # purpose: answered first, "already blocked" would report any user's
        # block state to any raiser who names a bogus reviewer. The refusal
        # for an open request says nothing about who raised it or why.
        row = await self._approvals.raise_request(
            session,
            action=BLOCK_USER,
            raised_by=actor_id,
            target_id=str(user_id),
            payload={"raised_from": raised_from},
            reason=reason,
            reviewer_id=reviewer_id,
        )
        return await self._to_dto(session, row)

    async def reassign(
        self, session, *, actor_id: int, request_id: int, reviewer_id: int
    ) -> BlockRequestDto:
        """Hand a pending request to a different reviewer. Commits.

        Done by the raiser, not by the reviewer: this is redirecting a question
        you asked, not handing off a duty you were given.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): Must be the request's raiser.
            request_id (int): The request to move.
            reviewer_id (int): The reviewer to move it to.

        Returns:
            BlockRequestDto: The request, now naming the new reviewer.

        Raises:
            ValueError: If the request is unknown or the new reviewer is not
                an eligible USER_ADMIN holder.
            PermissionError: If the caller did not raise the request.
            ConflictError: If it has already been closed.
        """
        row = await self._block_request(session, request_id)
        if row.raised_by == actor_id:
            self._refuse_target_as_reviewer(reviewer_id, int(row.target_id))
        row = await self._approvals.reassign(
            session, request_id=request_id, actor_id=actor_id, reviewer_id=reviewer_id
        )
        return await self._to_dto(session, row)

    async def decide(
        self,
        session,
        *,
        actor_id: int,
        request_id: int,
        approved: bool,
        note: str | None,
    ) -> BlockRequestDto:
        """Approve or reject a pending request. Commits.

        Only the named reviewer may decide. On approval the block is applied
        with the reason from the request, in the same transaction that closes
        it.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): Must be the request's named reviewer.
            request_id (int): The request to decide.
            approved (bool): True to block the target, False to turn it down.
            note (str | None): Why; required to reject.

        Returns:
            BlockRequestDto: The closed request.

        Raises:
            ValueError: If the request is unknown, or a rejection has no note.
            PermissionError: If the caller is not the named reviewer.
            ConflictError: If it has already been closed, or the person has
                been blocked since it was raised.
        """
        await self._block_request(session, request_id)
        row = await self._approvals.decide(
            session,
            request_id=request_id,
            actor_id=actor_id,
            approve=approved,
            comment=note,
        )
        return await self._to_dto(session, row)

    async def withdraw(
        self, session, *, actor_id: int, request_id: int
    ) -> BlockRequestDto:
        """Take back a request nobody has decided yet. Commits.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): Must be the request's raiser.
            request_id (int): The request.

        Returns:
            BlockRequestDto: The withdrawn request.

        Raises:
            ValueError: If the request is unknown.
            PermissionError: If the caller did not raise it.
            ConflictError: If it has already been closed.
        """
        await self._block_request(session, request_id)
        row = await self._approvals.withdraw(
            session, request_id=request_id, actor_id=actor_id
        )
        return await self._to_dto(session, row)

    async def block_directly(
        self, session, *, actor_id: int, user_id: int, reason: str
    ) -> None:
        """Block someone without going through a request. Commits.

        An operator is the end of the accountability chain, so this is one
        person and one click; the two-person property holds for requests raised
        from a domain page, not for this. A request already pending against
        the target is closed as superseded -- its outcome has happened, and
        nobody judged it.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): The operator.
            user_id (int): The person being blocked.
            reason (str): Why. Required and non-blank at the DTO.

        Raises:
            ValueError: If no user exists with ``user_id``.
            PermissionError: If the operator is blocking themselves.
        """
        if user_id == actor_id:
            self._logger.warning("Refused self-block for user_id=%s", actor_id)
            raise PermissionError("You cannot block your own account")
        target = await self._users.get_user_by_user_id(session, user_id)
        if target is not None and target.is_blocked:
            # Re-applying overwrites blocked_by/at/reason, so the record of
            # who imposed the sanction in force is lost. Lift it first if the
            # reason is wrong.
            raise ValueError("This person is already blocked")

        await self.apply_block(
            session, actor_id=actor_id, user_id=user_id, reason=reason
        )
        await self._approvals.supersede_pending(
            session, action=BLOCK_USER, target_id=str(user_id), actor_id=actor_id
        )
        await session.commit()

    async def list_pending_for_reviewer(
        self, session, reviewer_id: int
    ) -> list[BlockRequestDto]:
        """The requests this reviewer still has to decide.

        Args:
            session (AsyncSession): Active database async session.
            reviewer_id (int): The named reviewer.

        Returns:
            list[BlockRequestDto]: Pending requests, oldest first.
        """
        rows = await self._approvals.list_pending_for_reviewer(
            session, reviewer_id, [BLOCK_USER]
        )
        return await self._to_dtos(session, rows)

    async def list_pending_raised_by_actor(
        self, session, actor_id: int
    ) -> list[BlockRequestDto]:
        """The open requests this person raised.

        The mirror of ``list_pending_for_reviewer``, and scoped the same way:
        the caller's own id is the only input. It discloses nothing new -- the
        raiser wrote these requests and may reassign them -- but it is what
        lets their own page show an open one again after a reload, instead of
        offering a button that will be refused.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): The person who raised them.

        Returns:
            list[BlockRequestDto]: Pending requests, oldest first.
        """
        rows = await self._approvals.list_pending_raised_by(
            session, actor_id, [BLOCK_USER]
        )
        return await self._to_dtos(session, rows)

    async def list_user_admins(self, session) -> list[ReviewerOptionDto]:
        """The people who can be named as reviewer on a block request.

        Reads the same holder lookup every other picker uses, which already
        excludes blocked accounts (PUR-632). Do not reimplement the query here:
        naming a reviewer who can never sign in makes the request a dead
        letter, and that exclusion is exactly what stops it.

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[ReviewerOptionDto]: Active, unblocked USER_ADMIN holders,
                by name.
        """
        holders = await self._permissions.get_active_users_with_permission(
            session, Permission.USER_ADMIN.value
        )
        return sorted(
            (
                ReviewerOptionDto(user_id=holder.user_id, name=display_name_of(holder))
                for holder in holders
            ),
            key=lambda option: (option.name, option.user_id),
        )

    # -- helpers ------------------------------------------------------------

    async def _block_request(self, session, request_id: int):
        """Load a request, refusing any id that is not a block request.

        Args:
            session (AsyncSession): Active database async session.
            request_id (int): The request to load.

        Returns:
            ApprovalRequestEntity: The row.

        Raises:
            ValueError: If it is unknown or is another kind of approval.
        """
        try:
            row = await self._approvals.get_request(session, request_id)
        except ValueError:
            row = None
        if row is None or row.action != BLOCK_USER:
            raise ValueError(f"block request {request_id} not found")
        return row

    @staticmethod
    def _refuse_target_as_reviewer(reviewer_id: int, target_id: int) -> None:
        """A request cannot be sent to the person it would block.

        Args:
            reviewer_id (int): The proposed reviewer.
            target_id (int): The person the request is about.

        Raises:
            ValueError: If they are the same person.
        """
        if reviewer_id == target_id:
            raise ValueError("A block request cannot be sent to its own target")

    async def _to_dto(self, session, row) -> BlockRequestDto:
        """One request with its people resolved.

        Args:
            session (AsyncSession): Active database async session.
            row (ApprovalRequestEntity): The request.

        Returns:
            BlockRequestDto: The serializable view.
        """
        return (await self._to_dtos(session, [row]))[0]

    async def _to_dtos(self, session, rows) -> list[BlockRequestDto]:
        """A page of requests with every person on it named.

        One row names up to four people, and rendering any of them as a bare
        integer is the defect this project exists to stop repeating -- so every
        distinct id across the page is resolved in one lookup, never per row.
        An id that resolves to nothing leaves its name empty rather than
        raising: a request can outlive the account it names.

        Args:
            session (AsyncSession): Active database async session.
            rows (list[ApprovalRequestEntity]): The requests to render.

        Returns:
            list[BlockRequestDto]: The serializable views.
        """
        if not rows:
            return []
        ids = {
            person_id
            for row in rows
            for person_id in (
                int(row.target_id),
                row.raised_by,
                row.reviewer_id,
                row.decided_by,
            )
            if person_id is not None
        }
        people = await self._users.get_all_by_ids(session, sorted(ids))
        name_by_id = {person.user_id: display_name_of(person) for person in people}
        return [
            BlockRequestDto(
                id=row.request_id,
                target_user_id=int(row.target_id),
                target_name=name_by_id.get(int(row.target_id), ""),
                raised_by=row.raised_by,
                raised_by_name=name_by_id.get(row.raised_by, ""),
                raised_from=(row.payload or {}).get("raised_from", ""),
                raised_at=row.created_at,
                reason=row.reason,
                reviewer_id=row.reviewer_id,
                reviewer_name=name_by_id.get(row.reviewer_id, ""),
                status=row.status.value,
                decided_by=row.decided_by,
                decided_by_name=(
                    name_by_id.get(row.decided_by)
                    if row.decided_by is not None
                    else None
                ),
                decided_at=row.decided_at,
                decision_note=row.decision_comment,
            )
            for row in rows
        ]
