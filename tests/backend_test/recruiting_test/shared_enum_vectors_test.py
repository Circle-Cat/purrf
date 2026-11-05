import json
import unittest
from pathlib import Path

from backend.common.recruiting_enums import (
    ApplicationLockReason,
    ApplicationStage,
    JobStatus,
)

_STAGES = Path("tests/shared/application_stages.json")
_LOCK_REASONS = Path("tests/shared/application_lock_reasons.json")
_JOB_STATUSES = Path("tests/shared/job_statuses.json")


class ApplicationStagesVectorTest(unittest.TestCase):
    """Pins the shared stage vector to the enum the frontend mirrors."""

    def test_vector_matches_the_enum_exactly(self):
        shared = json.loads(_STAGES.read_text(encoding="utf-8"))
        self.assertEqual(shared, [stage.value for stage in ApplicationStage])


class ApplicationLockReasonsVectorTest(unittest.TestCase):
    """Pins the shared lock-reason vector to the enum the frontend words."""

    def test_vector_matches_the_enum_exactly(self):
        shared = json.loads(_LOCK_REASONS.read_text(encoding="utf-8"))
        self.assertEqual(shared, [r.value for r in ApplicationLockReason])


class JobStatusesVectorTest(unittest.TestCase):
    """Pins the shared job-status vector to the enum the frontend maps.

    The frontend splits these statuses across three maps -- which have an
    Operate row, what each pending one is waiting for, and which base badge
    each shows. A status added here and nowhere else renders a blank badge and
    a notice that says a posting is locked without saying what for, so
    jobStatus.test.js checks that split against this same file.
    """

    def test_vector_matches_the_enum_exactly(self):
        shared = json.loads(_JOB_STATUSES.read_text(encoding="utf-8"))
        self.assertEqual(shared, [s.value for s in JobStatus])


if __name__ == "__main__":
    unittest.main()
