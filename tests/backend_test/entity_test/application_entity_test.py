import unittest
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


if __name__ == "__main__":
    unittest.main()
