"""A request to block someone, as an approval.

A colleague on a domain page asks a named USER_ADMIN holder to block a
person; approving applies the same block an operator applies directly
(``apply_block_kernel``). Nothing is marked on the person while the request
waits, so rejecting or withdrawing it has nothing to undo.
"""

from backend.admin.block_service import BLOCK_TARGET, BLOCK_USER, apply_block_kernel
from backend.approval.approval_handler import ApprovalHandler
from backend.common.permissions import Permission
from backend.common.user_enums import USER_SUBJECT_TYPE, UserEvent


class BlockUserHandler(ApprovalHandler):
    action = BLOCK_USER
    target_type = BLOCK_TARGET
    subject_type = USER_SUBJECT_TYPE
    raised_event = UserEvent.BLOCK_REQUESTED
    reassigned_event = UserEvent.BLOCK_REQUEST_REASSIGNED
    decided_event = UserEvent.BLOCK_REQUEST_DECIDED
    review_permission = Permission.USER_ADMIN

    def __init__(
        self,
        users_repository,
        application_repository,
        application_submission_repository,
        application_interview_repository,
        interview_scheduling_service,
        mentorship_block_service,
    ):
        """
        Args:
            users_repository (UsersRepository): The person to block.
            application_repository (ApplicationRepository): The applications
                a block sweeps.
            application_submission_repository (ApplicationSubmissionRepository):
                Freezes the submissions of closed-out applications.
            application_interview_repository (ApplicationInterviewRepository):
                The interviews a block cancels.
            interview_scheduling_service (InterviewSchedulingService): Cancels
                them.
            mentorship_block_service (MentorshipBlockService): Ends the
                person's mentorship pairs.
        """
        self._users = users_repository
        self._applications = application_repository
        self._submissions = application_submission_repository
        self._interviews = application_interview_repository
        self._interview_scheduling = interview_scheduling_service
        self._mentorship = mentorship_block_service

    def subject_id(self, request) -> int:
        return int(request.target_id)

    async def check_raise(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> None:
        target = await self._users.get_user_by_user_id(session, int(target_id))
        if target is None:
            raise ValueError(f"user {target_id} not found")
        if target.is_blocked:
            # Approving it later would overwrite blocked_by/at/reason and
            # erase who imposed the sanction in force and why.
            raise ValueError("This person is already blocked")

    async def problems_at_approval(self, session, request) -> list[str]:
        if int(request.target_id) == request.reviewer_id:
            raise PermissionError("You cannot block your own account")
        target = await self._users.get_user_by_user_id(session, int(request.target_id))
        if target is not None and target.is_blocked:
            # An operator blocked them directly while this waited.
            return ["This person is already blocked."]
        return []

    async def execute(self, session, request, *, actor_id: int) -> None:
        await apply_block_kernel(
            session,
            actor_id=actor_id,
            user_id=int(request.target_id),
            reason=request.reason,
            users_repository=self._users,
            application_repository=self._applications,
            application_submission_repository=self._submissions,
            application_interview_repository=self._interviews,
            interview_scheduling_service=self._interview_scheduling,
            mentorship_block_service=self._mentorship,
            request_id=request.request_id,
        )
