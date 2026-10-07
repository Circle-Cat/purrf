"""A job posting review, as an approval.

Four kinds of review share the gate, told apart by ``payload["kind"]``:
INITIAL publishes a draft, REVISION applies a published posting's staged
edit, CLOSE closes it and REOPEN publishes a closed one again. While a review
waits the posting sits in a pending status, which is what keeps it from
being edited; approving moves it on, and rejecting or withdrawing puts it
back where it was.

The two rules a review is judged by -- the config that would go live must
still hold, and approving a revision overwrites the live fields with the
staged ones -- live here as functions, because JobService checks the first
before it opens a review too.
"""

from backend.approval.approval_handler import ApprovalHandler
from backend.common.permissions import Permission
from backend.common.recruiting_enums import JobReviewKind, JobStatus, RecruitingEvent
from backend.recruiting.job_blockers import effective_pipeline_config, submit_blockers
from backend.recruiting.pipeline_owners import normalized_owner_ids

JOB_REVIEW = "job_review"
JOB_SUBJECT = "job"

# Where a posting has to be to open each kind of review, and where it waits.
_FROM = {
    JobReviewKind.INITIAL: JobStatus.DRAFT,
    JobReviewKind.REVISION: JobStatus.PUBLISHED,
    JobReviewKind.CLOSE: JobStatus.PUBLISHED,
    JobReviewKind.REOPEN: JobStatus.CLOSED,
}
_WAITING = {
    JobReviewKind.INITIAL: JobStatus.PENDING_REVIEW,
    JobReviewKind.REVISION: JobStatus.PUBLISHED_PENDING_REVISION,
    JobReviewKind.CLOSE: JobStatus.PENDING_CLOSE,
    JobReviewKind.REOPEN: JobStatus.PENDING_REOPEN,
}


async def revalidate_job_config(session, job, user_permissions_repository) -> None:
    """Re-check the pipeline that would go live before a review opens or passes.

    Validates the effective config -- the staged ``pending_payload``'s
    ``pipelineConfig`` when an edit is staged, else the live
    ``pipeline_config`` -- so a REVISION is judged on what approval would
    actually publish. Requires at least one pipeline stage (a human fallback
    so no submission can land outside every board lane) and at least one
    owner (someone the applications are visible to), then re-checks that
    stored assignees/owners still hold their permissions.

    Args:
        session (AsyncSession): Active database async session.
        job (JobEntity): The posting under review.
        user_permissions_repository: Finds who holds each permission now.

    Raises:
        ValueError: If the effective config has no stage or no owner, or a
            stored assignee/owner no longer holds its permission.
    """
    blockers = submit_blockers(job)
    if blockers:
        raise ValueError(blockers[0])
    cfg = effective_pipeline_config(job)
    assignee_ids = {
        s.get("defaultAssigneeId")
        for s in cfg.get("stages", [])
        if s.get("defaultAssigneeId") is not None
    }
    if assignee_ids:
        pool = await user_permissions_repository.get_active_users_with_permission(
            session, Permission.RECRUITING_INTERVIEW_EVALUATE.value
        )
        missing = assignee_ids - {u.user_id for u in pool}
        if missing:
            raise ValueError(f"assignees {sorted(missing)} no longer qualify")
    owner_ids = normalized_owner_ids(cfg)
    if owner_ids:
        pool = await user_permissions_repository.get_active_users_with_permission(
            session, Permission.RECRUITING_APPLICATION_ADVANCE.value
        )
        valid = {u.user_id for u in pool}
        missing_owners = [o for o in owner_ids if o not in valid]
        if missing_owners:
            raise ValueError(f"owners {sorted(missing_owners)} no longer qualify")


def apply_pending_payload(job) -> None:
    """Overwrite a posting's live fields with its pending_payload, then clear it.

    Reads each field via ``dict.get`` rather than indexing, so a payload
    missing a key degrades to clearing that field to None instead of raising
    KeyError.

    Args:
        job (JobEntity): The posting; job.pending_payload must not be None.
    """
    payload = job.pending_payload
    job.title = payload.get("title")
    job.description = payload.get("description")
    job.cooldown_days = payload.get("cooldownDays")
    job.screen_rules = payload.get("screenRules")
    job.form_schema = payload.get("formSchema")
    job.pipeline_config = payload.get("pipelineConfig")
    job.profile_config = payload.get("profileConfig")
    job.pending_payload = None


def review_kind(request) -> JobReviewKind:
    """The kind of a job review request."""
    return JobReviewKind(request.payload["kind"])


class JobReviewHandler(ApprovalHandler):
    """The ``job_review`` action. Its target is the posting; its payload
    carries the review's kind."""

    action = JOB_REVIEW
    target_type = JOB_SUBJECT
    subject_type = JOB_SUBJECT
    raised_event = RecruitingEvent.REVIEW_OPENED
    reassigned_event = RecruitingEvent.REVIEW_REASSIGNED
    decided_event = RecruitingEvent.REVIEW_DECIDED
    review_permission = Permission.RECRUITING_JOB_APPROVE

    def __init__(self, job_repository, user_permissions_repository):
        """
        Args:
            job_repository: Reads and writes the posting.
            user_permissions_repository: Re-checks the config's people.
        """
        self.job_repository = job_repository
        self.user_permissions_repository = user_permissions_repository

    def subject_id(self, request) -> int:
        return int(request.target_id)

    async def event_details(self, session, request) -> dict:
        # The names the recruiting timeline, bell and resolvers read.
        return {
            "kind": request.payload["kind"],
            "reviewId": request.request_id,
            "message": request.reason,
        }

    async def check_raise(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> None:
        """Refuse a review the posting is not in a state to open.

        Raises:
            ValueError: An unknown kind, a missing posting, or a posting not
                in the status the kind opens from (a REVISION also needs a
                staged edit).
        """
        try:
            kind = JobReviewKind(payload.get("kind"))
        except ValueError as exc:
            raise ValueError("A job review names its kind.") from exc
        job = await self._job(session, int(target_id))
        if job.status != _FROM[kind] or (
            kind == JobReviewKind.REVISION and job.pending_payload is None
        ):
            raise ValueError(
                f"Job {job.job_id} cannot open a {kind} review from {job.status}"
            )

    async def on_raised(self, session, request) -> None:
        job = await self._job(session, self.subject_id(request))
        job.status = _WAITING[review_kind(request)]
        await self.job_repository.update_job(session, job)

    async def problems_at_approval(self, session, request) -> list[str]:
        # A close publishes nothing, and a blocked owner must not trap a
        # posting open.
        if review_kind(request) == JobReviewKind.CLOSE:
            return []
        job = await self._job(session, self.subject_id(request))
        try:
            await revalidate_job_config(session, job, self.user_permissions_repository)
        except ValueError as problem:
            return [str(problem)]
        return []

    async def execute(self, session, request, *, actor_id: int) -> None:
        """Move the posting on: INITIAL and REOPEN publish it (REOPEN applying
        a staged edit if there is one), REVISION applies the staged edit and
        keeps it published, CLOSE closes it."""
        kind = review_kind(request)
        job = await self._job(session, self.subject_id(request))
        if kind == JobReviewKind.CLOSE:
            job.status = JobStatus.CLOSED
        else:
            if kind == JobReviewKind.REOPEN and job.pending_payload is not None:
                apply_pending_payload(job)
            if (
                kind == JobReviewKind.REVISION
                and job.status == JobStatus.PUBLISHED_PENDING_REVISION
            ):
                apply_pending_payload(job)
            job.status = JobStatus.PUBLISHED
            job.was_published = True
        await self.job_repository.update_job(session, job)

    async def revert(self, session, request) -> None:
        """Put the posting back: INITIAL returns to DRAFT, REVISION and CLOSE
        to PUBLISHED (a revision keeps its staged edit, so it can be fixed and
        sent again), REOPEN to CLOSED."""
        job = await self._job(session, self.subject_id(request))
        job.status = _FROM[review_kind(request)]
        await self.job_repository.update_job(session, job)

    async def _job(self, session, job_id: int):
        job = await self.job_repository.get_by_job_id(session, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        return job
