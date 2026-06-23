import unittest
from unittest.mock import MagicMock
from backend.recruiting.recruiting_controller import RecruitingController


class TestRecruitingController(unittest.TestCase):
    def setUp(self):
        self.controller = RecruitingController(MagicMock(), MagicMock(), MagicMock())

    def test_routes_registered(self):
        """Assert all 10 recruiting routes are registered with the correct path and HTTP method."""
        routes = {(r.path, m) for r in self.controller.router.routes for m in r.methods}
        self.assertIn(("/recruiting/jobs", "POST"), routes)
        self.assertIn(("/recruiting/jobs", "GET"), routes)
        self.assertIn(("/recruiting/jobs/{job_id}", "PUT"), routes)
        self.assertIn(("/recruiting/jobs/{job_id}", "GET"), routes)
        self.assertIn(("/recruiting/jobs/{job_id}/publish", "POST"), routes)
        self.assertIn(("/recruiting/jobs/{job_id}/close", "POST"), routes)
        self.assertIn(("/recruiting/jobs/{job_id}/applications", "POST"), routes)
        self.assertIn(("/recruiting/jobs/{job_id}/board", "GET"), routes)
        self.assertIn(("/recruiting/applications/{application_id}/view", "POST"), routes)
        self.assertIn(("/recruiting/applications/{application_id}/advance", "POST"), routes)


if __name__ == "__main__":
    unittest.main()
