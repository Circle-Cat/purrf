"""Blocking: the kernel that applies a block, and the read-side pre-flight.

``apply_block_kernel`` is the whole sanction with no application to hang it on.
It came out of ``BoardService.blacklist``, which was the same three consequences
plus one pinned triggering application; drop the anchor and this is what is
left. Two callers need it -- the recruiting route that still passes a triggering
application, and the account console, which has none -- and neither can own it.

🔴 The kernel must never commit. Its callers each own their transaction (the
approval flow applies a block mid-transaction and records the decision after
it), and a commit here would leave a later failure unable to roll the block
back.
"""

from datetime import datetime, timezone

from backend.common.recruiting_enums import ApplicationStage, RecruitingEvent
from backend.dto.block_dto import BlockPreflightDto
from backend.notification_management.event_recorder import record_event


async def apply_block_kernel(
    session,
    *,
    actor_id: int,
    user_id: int,
    reason: str,
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
        reason (str): Why. Recorded on the user and on every event.
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
            logger (Logger): Injected logger.
        """
        self._users = users_repository
        self._applications = application_repository
        self._submissions = application_submission_repository
        self._interviews = application_interview_repository
        self._interview_scheduling = interview_scheduling_service
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
        self, session, *, actor_id: int, user_id: int, reason: str
    ) -> None:
        """Apply a block. Does NOT commit -- see the module docstring.

        Args:
            session (AsyncSession): Active database async session.
            actor_id (int): The user performing the block.
            user_id (int): The user being blocked.
            reason (str): Why.

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
