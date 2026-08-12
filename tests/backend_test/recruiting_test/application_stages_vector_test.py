import json
import unittest
from pathlib import Path

from backend.common.recruiting_enums import ApplicationStage

# Contract shared with the frontend glossary. The stage vocabulary a candidate
# reads is rendered from a glossary keyed by these values, so a stage added
# here without a term would show a raw enum name. Pinning the vector to the
# enum here, and the glossary to the vector on the JS side, makes that
# omission a red test on whichever side falls behind.
_VECTOR = Path("tests/shared/application_stages.json")


class ApplicationStagesVectorTest(unittest.TestCase):
    """Pins the shared stage vector to the enum the frontend mirrors."""

    def test_vector_matches_the_enum_exactly(self):
        shared = json.loads(_VECTOR.read_text(encoding="utf-8"))
        self.assertEqual(shared, [stage.value for stage in ApplicationStage])


if __name__ == "__main__":
    unittest.main()
