"""Unit tests for recruiting review enums and the job-approve permission."""

from backend.common.recruiting_enums import (
    JobReviewKind,
    JobReviewStatus,
    JobStatus,
)
from backend.common.permissions import Permission


def test_job_status_has_review_states():
    """JobStatus carries the two review-gate states added for publishing."""
    assert JobStatus.PENDING_REVIEW.value == "pending_review"
    assert JobStatus.PUBLISHED_PENDING_REVISION.value == "published_pending_revision"


def test_job_review_enums():
    """JobReviewStatus and JobReviewKind expose exactly their MVP members."""
    assert {s.value for s in JobReviewStatus} == {"pending", "approved", "rejected"}
    assert {k.value for k in JobReviewKind} == {
        "initial",
        "revision",
        "close",
        "reopen",
    }


def test_job_status_close_reopen_states():
    """JobStatus carries the two gated lifecycle-transition states."""
    assert JobStatus.PENDING_CLOSE.value == "pending_close"
    assert JobStatus.PENDING_REOPEN.value == "pending_reopen"


def test_job_review_kind_close_reopen():
    """JobReviewKind carries close and reopen gates."""
    assert JobReviewKind.CLOSE.value == "close"
    assert JobReviewKind.REOPEN.value == "reopen"


def test_job_approve_permission():
    """The job-approve permission string matches the catalog convention."""
    assert Permission.RECRUITING_JOB_APPROVE.value == "recruiting.job.approve"
