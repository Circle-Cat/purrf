"""Prefixes a newer upload replaced, and when the cleanup job may have them."""

import unittest
from datetime import datetime, timedelta, timezone

from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_retired_prefix_entity import (
    TrainingRetiredPrefixEntity,
)
from backend.repository.training_retired_prefix_repository import (
    TrainingRetiredPrefixRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestTrainingRetiredPrefixRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = TrainingRetiredPrefixRepository()
        self.now = datetime.now(timezone.utc)

        courses = [
            TrainingCourseEntity(name="Mentor Onboarding", is_active=True),
            TrainingCourseEntity(name="Mentee Onboarding", is_active=True),
        ]
        await self.insert_entities(courses)
        self.course_id = courses[0].course_id
        self.other_course_id = courses[1].course_id

    async def _retire(self, prefix, delete_after, *, course_id=None, deleted_at=None):
        entity = TrainingRetiredPrefixEntity(
            course_id=course_id or self.course_id,
            storage_prefix=prefix,
            delete_after=delete_after,
            deleted_at=deleted_at,
        )
        await self.insert_entities([entity])
        return entity

    async def test_add_records_the_prefix_with_its_delay(self):
        delete_after = self.now + timedelta(hours=24)

        added = await self.repo.add(
            self.session, self.course_id, "training/1/old-uuid/", delete_after
        )

        self.assertEqual(added.course_id, self.course_id)
        self.assertEqual(added.storage_prefix, "training/1/old-uuid/")
        self.assertEqual(added.delete_after, delete_after)

    async def test_a_freshly_added_prefix_is_not_yet_deleted(self):
        added = await self.repo.add(
            self.session,
            self.course_id,
            "training/1/old-uuid/",
            self.now + timedelta(hours=24),
        )

        self.assertIsNone(added.deleted_at)

    async def test_due_returns_a_prefix_whose_delay_has_elapsed(self):
        await self._retire("training/1/old-uuid/", self.now - timedelta(minutes=1))

        due = await self.repo.due(self.session, self.now)

        self.assertEqual([row.storage_prefix for row in due], ["training/1/old-uuid/"])

    async def test_due_withholds_a_prefix_whose_delay_has_not_elapsed(self):
        """In-flight requests may still be holding it; tokens live 12 hours."""
        await self._retire("training/1/old-uuid/", self.now + timedelta(hours=23))

        self.assertEqual(await self.repo.due(self.session, self.now), [])

    async def test_due_includes_a_prefix_due_exactly_now(self):
        await self._retire("training/1/old-uuid/", self.now)

        due = await self.repo.due(self.session, self.now)

        self.assertEqual([row.storage_prefix for row in due], ["training/1/old-uuid/"])

    async def test_due_skips_a_prefix_already_deleted(self):
        await self._retire(
            "training/1/gone/",
            self.now - timedelta(days=2),
            deleted_at=self.now - timedelta(days=1),
        )

        self.assertEqual(await self.repo.due(self.session, self.now), [])

    async def test_due_spans_courses(self):
        """The cleanup job runs over everything, not one course at a time."""
        await self._retire("training/1/old/", self.now - timedelta(hours=1))
        await self._retire(
            "training/2/old/",
            self.now - timedelta(hours=1),
            course_id=self.other_course_id,
        )

        due = await self.repo.due(self.session, self.now)

        self.assertEqual(
            sorted(row.storage_prefix for row in due),
            ["training/1/old/", "training/2/old/"],
        )

    async def test_due_returns_nothing_when_no_prefix_has_been_retired(self):
        self.assertEqual(await self.repo.due(self.session, self.now), [])


if __name__ == "__main__":
    unittest.main()
