"""Unit tests for recruiting review enums and the job-approve permission."""

import unittest

from backend.common.recruiting_enums import (
    PUBLICLY_VISIBLE_JOB_STATUSES,
    JobReviewKind,
    JobReviewStatus,
    JobStatus,
)
from backend.common.permissions import Permission


class RecruitingEnumsTest(unittest.TestCase):
    def test_job_status_has_review_states(self):
        """JobStatus carries the two review-gate states added for publishing."""
        assert JobStatus.PENDING_REVIEW.value == "pending_review"
        assert (
            JobStatus.PUBLISHED_PENDING_REVISION.value == "published_pending_revision"
        )

    def test_job_review_enums(self):
        """JobReviewStatus and JobReviewKind expose exactly their MVP members."""
        assert {s.value for s in JobReviewStatus} == {
            "pending",
            "approved",
            "rejected",
        }
        assert {k.value for k in JobReviewKind} == {
            "initial",
            "revision",
            "close",
            "reopen",
        }

    def test_job_status_close_reopen_states(self):
        """JobStatus carries the two gated lifecycle-transition states."""
        assert JobStatus.PENDING_CLOSE.value == "pending_close"
        assert JobStatus.PENDING_REOPEN.value == "pending_reopen"

    def test_job_review_kind_close_reopen(self):
        """JobReviewKind carries close and reopen gates."""
        assert JobReviewKind.CLOSE.value == "close"
        assert JobReviewKind.REOPEN.value == "reopen"

    def test_publicly_visible_job_statuses(self):
        """A posting awaiting a revision or close decision is still live.

        Both states keep serving the last approved version, so candidates must
        keep seeing (and be able to apply to) the posting until the reviewer
        decides. PENDING_REVIEW and PENDING_REOPEN are not live: neither has an
        approved version on offer.
        """
        assert PUBLICLY_VISIBLE_JOB_STATUSES == frozenset({
            JobStatus.PUBLISHED,
            JobStatus.PUBLISHED_PENDING_REVISION,
            JobStatus.PENDING_CLOSE,
        })

    def test_job_approve_permission(self):
        """The job-approve permission string matches the catalog convention."""
        assert Permission.RECRUITING_JOB_APPROVE.value == "recruiting.job.approve"


if __name__ == "__main__":
    unittest.main()
