import json
import unittest
from pathlib import Path

from backend.common.recruiting_enums import ApplicationStage

_VECTOR = Path("tests/shared/application_stages.json")


class ApplicationStagesVectorTest(unittest.TestCase):
    """Pins the shared stage vector to the enum the frontend mirrors."""

    def test_vector_matches_the_enum_exactly(self):
        shared = json.loads(_VECTOR.read_text(encoding="utf-8"))
        self.assertEqual(shared, [stage.value for stage in ApplicationStage])


if __name__ == "__main__":
    unittest.main()
