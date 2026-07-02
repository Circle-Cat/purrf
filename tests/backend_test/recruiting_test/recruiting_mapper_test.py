import unittest

from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.entity.job_entity import JobEntity
from backend.common.recruiting_enums import JobKind, JobStatus


class TestRecruitingMapper(unittest.TestCase):
    def setUp(self):
        """Instantiate the mapper under test."""
        self.mapper = RecruitingMapper()

    def _make_job_entity(self, **kw):
        """Build a JobEntity fixture with sensible defaults for mapper tests."""
        defaults = {
            "kind": JobKind.ACTIVITY,
            "title": "T",
            "status": JobStatus.PUBLISHED,
            "description": "d",
        }
        defaults.update(kw)
        job = JobEntity(**defaults)
        job.job_id = 1
        return job

    def test_to_public_job_summary_dto_exposes_only_card_fields(self):
        job = self._make_job_entity()
        dto = self.mapper.to_public_job_summary_dto(job)
        self.assertEqual(dto.id, job.job_id)
        self.assertEqual(dto.title, job.title)
        self.assertEqual(dto.kind, job.kind)
        self.assertEqual(dto.description, job.description)
        self.assertEqual(
            set(type(dto).model_fields.keys()), {"id", "title", "kind", "description"}
        )


if __name__ == "__main__":
    unittest.main()
