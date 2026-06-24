import unittest
from backend.entity.job_entity import JobEntity
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.common.mentorship_enums import ParticipantRole
from backend.recruiting.recruiting_mapper import RecruitingMapper


class TestRecruitingMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = RecruitingMapper()

    def test_to_job_dto(self):
        job = JobEntity(
            job_id=7,
            kind=JobKind.ACTIVITY,
            mentorship_role=ParticipantRole.MENTOR,
            status=JobStatus.PUBLISHED,
            title="Mentor",
            description="jd",
            form_schema={"type": "object"},
        )
        dto = self.mapper.to_job_dto(job)
        self.assertEqual(dto.id, 7)
        self.assertEqual(dto.title, "Mentor")
        self.assertEqual(dto.status, JobStatus.PUBLISHED)
        self.assertEqual(dto.mentorship_role, ParticipantRole.MENTOR)


if __name__ == "__main__":
    unittest.main()
