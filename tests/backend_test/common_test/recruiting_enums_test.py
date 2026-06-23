import unittest
from backend.common.recruiting_enums import (
    UserType, JobKind, JobStatus, ApplicationStage,
)
from backend.common.permissions import Permission


class TestRecruitingEnums(unittest.TestCase):
    def test_user_type_values(self):
        self.assertEqual(UserType.EXTERNAL.value, "external")
        self.assertEqual(UserType.INTERNAL.value, "internal")

    def test_job_enums_values(self):
        self.assertEqual(JobKind.ACTIVITY.value, "activity")
        self.assertEqual(JobStatus.DRAFT.value, "draft")
        self.assertEqual(JobStatus.PUBLISHED.value, "published")

    def test_application_stage_mvp_members(self):
        self.assertEqual(ApplicationStage.RECRUITER_SCREENING.value, "recruiter_screening")
        self.assertEqual(ApplicationStage.HIRED.value, "hired")
        self.assertEqual(ApplicationStage.REJECTED.value, "rejected")

    def test_recruiting_permissions_exist(self):
        self.assertEqual(Permission.RECRUITING_JOB_WRITE.value, "recruiting.job.write")
        self.assertEqual(Permission.RECRUITING_APPLICATION_ADVANCE.value, "recruiting.application.advance")


if __name__ == "__main__":
    unittest.main()
