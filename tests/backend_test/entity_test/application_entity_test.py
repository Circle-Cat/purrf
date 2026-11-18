import unittest
from sqlalchemy import inspect, select
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.common.recruiting_enums import ApplicationStage


class TestApplicationEntities(unittest.TestCase):
    def test_application_defaults_to_applied_stage(self):
        app = ApplicationEntity(job_id=1, user_id=2, stage=ApplicationStage.APPLIED)
        self.assertEqual(app.__tablename__, "application")
        self.assertEqual(app.job_id, 1)
        self.assertEqual(app.user_id, 2)
        self.assertEqual(app.stage, ApplicationStage.APPLIED)

    def test_application_current_round_round_trips(self):
        app = ApplicationEntity(
            job_id=1, user_id=2, stage=ApplicationStage.APPLIED, current_round=3
        )
        self.assertEqual(app.current_round, 3)

    def test_application_current_round_column_default_is_one(self):
        column = ApplicationEntity.__table__.c.current_round
        self.assertEqual(column.default.arg, 1)
        self.assertEqual(column.server_default.arg, "1")

    def test_submission_carries_snapshot_and_resume_ref(self):
        sub = ApplicationSubmissionEntity(
            application_id=1,
            version=1,
            submission={"personal": {"firstName": "A"}, "answers": {}},
            resume_object_key="resumes/abc.pdf",
            resume_sha256="abc",
        )
        self.assertEqual(sub.__tablename__, "application_submission")
        self.assertEqual(sub.version, 1)
        self.assertEqual(sub.resume_object_key, "resumes/abc.pdf")
        self.assertEqual(sub.submission["personal"]["firstName"], "A")

    # is_frozen is no longer used and is dropped in the next release. Until
    # then the ORM must neither read nor write it, so a pod running this code
    # keeps working once the column is gone.
    def test_submission_is_frozen_is_nullable_without_a_default(self):
        column = ApplicationSubmissionEntity.__table__.c.is_frozen
        self.assertTrue(column.nullable)
        self.assertIsNone(column.default)
        self.assertIsNone(column.server_default)

    def test_submission_is_frozen_is_not_mapped(self):
        self.assertNotIn("is_frozen", inspect(ApplicationSubmissionEntity).attrs)

    def test_loading_a_submission_does_not_select_is_frozen(self):
        sql = str(select(ApplicationSubmissionEntity))
        self.assertIn("application_submission.submission_id", sql)
        self.assertNotIn("is_frozen", sql)


if __name__ == "__main__":
    unittest.main()
