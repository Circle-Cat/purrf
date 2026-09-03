import os
import unittest
from unittest.mock import patch

from backend.common.mentorship_enums import TrainingCategory
from backend.common.training_links import external_link_for


class TestExternalLinkFor(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"MENTORSHIP_MENTOR_ONBOARDING_LINK": "https://example.com/mentor"},
    )
    def test_a_configured_category_resolves_to_its_url(self):
        self.assertEqual(
            external_link_for(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING),
            "https://example.com/mentor",
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_a_configured_category_with_nothing_set_resolves_to_nothing(self):
        self.assertIsNone(
            external_link_for(TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING)
        )

    def test_a_category_that_never_had_a_link_resolves_to_nothing(self):
        """Only the two mentorship onboarding courses are hosted elsewhere."""
        self.assertIsNone(external_link_for(TrainingCategory.CORPORATE_CULTURE_COURSE))

    def test_a_course_with_no_category_resolves_to_nothing(self):
        self.assertIsNone(external_link_for(None))


if __name__ == "__main__":
    unittest.main()
