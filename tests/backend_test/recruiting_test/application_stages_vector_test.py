import json
import unittest
from pathlib import Path

from backend.common.recruiting_enums import ApplicationLockReason, ApplicationStage

_STAGES = Path("tests/shared/application_stages.json")
_LOCK_REASONS = Path("tests/shared/application_lock_reasons.json")


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


if __name__ == "__main__":
    unittest.main()
