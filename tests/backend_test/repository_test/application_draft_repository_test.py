import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import JobKind, JobStatus
from backend.entity.application_draft_entity import ApplicationDraftEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.application_draft_repository import (
    ApplicationDraftRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user(first_name: str) -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column."""
    return UsersEntity(
        first_name=first_name,
        last_name="Tester",
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestApplicationDraftRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = ApplicationDraftRepository()
        # Two of each, and created users-first so no user_id equals a job_id
        # by accident of both sequences starting at 1.
        self.alice = _make_user("Alice")
        self.bob = _make_user("Bob")
        await self.insert_entities([self.alice, self.bob])
        filler = [_make_user(f"Filler{i}") for i in range(3)]
        await self.insert_entities(filler)
        self.engineer = JobEntity(
            kind=JobKind.EMPLOYMENT, title="Engineer", status=JobStatus.PUBLISHED
        )
        self.mentee = JobEntity(
            kind=JobKind.ACTIVITY, title="Mentee", status=JobStatus.CLOSED
        )
        await self.insert_entities([self.engineer, self.mentee])

    async def _set_updated(self, user_id: int, job_id: int, when: datetime):
        await self.session.execute(
            update(ApplicationDraftEntity)
            .where(
                ApplicationDraftEntity.user_id == user_id,
                ApplicationDraftEntity.job_id == job_id,
            )
            .values(updated_timestamp=when)
        )

    async def test_get_returns_none_without_a_draft(self):
        self.assertIsNone(
            await self.repo.get(self.session, self.alice.user_id, self.engineer.job_id)
        )

    async def test_upsert_creates_a_draft_that_get_reads_back(self):
        created = await self.repo.upsert(
            self.session,
            self.alice.user_id,
            self.engineer.job_id,
            {"answers": {"q1": "draft"}},
        )

        found = await self.repo.get(
            self.session, self.alice.user_id, self.engineer.job_id
        )
        self.assertEqual(created.application_draft_id, found.application_draft_id)
        self.assertEqual(self.alice.user_id, found.user_id)
        self.assertEqual(self.engineer.job_id, found.job_id)
        self.assertEqual({"answers": {"q1": "draft"}}, found.content)
        self.assertIsNotNone(found.updated_timestamp)
        self.assertIsNotNone(found.created_datetime)

    async def test_get_does_not_swap_user_and_job(self):
        await self.repo.upsert(
            self.session, self.alice.user_id, self.engineer.job_id, {"a": 1}
        )

        if self.engineer.job_id != self.alice.user_id:
            self.assertIsNone(
                await self.repo.get(
                    self.session, self.engineer.job_id, self.alice.user_id
                )
            )
        self.assertIsNone(
            await self.repo.get(self.session, self.bob.user_id, self.engineer.job_id)
        )
        self.assertIsNone(
            await self.repo.get(self.session, self.alice.user_id, self.mentee.job_id)
        )

    async def test_upsert_overwrites_the_same_row_and_moves_updated_timestamp(self):
        first = await self.repo.upsert(
            self.session, self.alice.user_id, self.engineer.job_id, {"v": 1}
        )
        first_id = first.application_draft_id
        first_created = first.created_datetime
        long_ago = datetime(2020, 1, 1, tzinfo=timezone.utc)
        await self._set_updated(self.alice.user_id, self.engineer.job_id, long_ago)

        second = await self.repo.upsert(
            self.session, self.alice.user_id, self.engineer.job_id, {"v": 2}
        )

        self.assertEqual(first_id, second.application_draft_id)
        self.assertEqual({"v": 2}, second.content)
        self.assertEqual(first_created, second.created_datetime)
        self.assertGreater(second.updated_timestamp, long_ago)
        rows = (
            (
                await self.session.execute(
                    select(ApplicationDraftEntity).where(
                        ApplicationDraftEntity.user_id == self.alice.user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        self.assertEqual(1, len(rows))

    async def test_one_draft_per_user_per_job_is_kept_apart(self):
        await self.repo.upsert(
            self.session, self.alice.user_id, self.engineer.job_id, {"who": "a-eng"}
        )
        await self.repo.upsert(
            self.session, self.alice.user_id, self.mentee.job_id, {"who": "a-men"}
        )
        await self.repo.upsert(
            self.session, self.bob.user_id, self.engineer.job_id, {"who": "b-eng"}
        )

        for user, job, expected in (
            (self.alice, self.engineer, "a-eng"),
            (self.alice, self.mentee, "a-men"),
            (self.bob, self.engineer, "b-eng"),
        ):
            with self.subTest(expected=expected):
                found = await self.repo.get(self.session, user.user_id, job.job_id)
                self.assertEqual({"who": expected}, found.content)

    async def test_the_table_refuses_a_second_row_for_the_same_pair(self):
        await self.repo.upsert(
            self.session, self.alice.user_id, self.engineer.job_id, {"v": 1}
        )
        self.session.add(
            ApplicationDraftEntity(
                user_id=self.alice.user_id,
                job_id=self.engineer.job_id,
                content={"v": 2},
            )
        )
        with self.assertRaises(IntegrityError):
            await self.session.flush()

    async def test_delete_removes_only_that_draft(self):
        await self.repo.upsert(
            self.session, self.alice.user_id, self.engineer.job_id, {"v": 1}
        )
        await self.repo.upsert(
            self.session, self.alice.user_id, self.mentee.job_id, {"v": 2}
        )
        await self.repo.upsert(
            self.session, self.bob.user_id, self.engineer.job_id, {"v": 3}
        )

        await self.repo.delete(self.session, self.alice.user_id, self.engineer.job_id)

        self.assertIsNone(
            await self.repo.get(self.session, self.alice.user_id, self.engineer.job_id)
        )
        self.assertIsNotNone(
            await self.repo.get(self.session, self.alice.user_id, self.mentee.job_id)
        )
        self.assertIsNotNone(
            await self.repo.get(self.session, self.bob.user_id, self.engineer.job_id)
        )

    async def test_delete_without_a_draft_is_a_no_op(self):
        await self.repo.delete(self.session, self.alice.user_id, self.engineer.job_id)

    async def test_list_by_user_with_job_is_newest_saved_first(self):
        await self.repo.upsert(
            self.session, self.alice.user_id, self.engineer.job_id, {"v": 1}
        )
        await self.repo.upsert(
            self.session, self.alice.user_id, self.mentee.job_id, {"v": 2}
        )
        await self.repo.upsert(
            self.session, self.bob.user_id, self.engineer.job_id, {"v": 3}
        )
        base = datetime(2026, 11, 1, tzinfo=timezone.utc)
        # The engineer draft was created first but saved last.
        await self._set_updated(
            self.alice.user_id, self.engineer.job_id, base + timedelta(days=2)
        )
        await self._set_updated(self.alice.user_id, self.mentee.job_id, base)

        rows = await self.repo.list_by_user_with_job(self.session, self.alice.user_id)

        self.assertEqual(
            [self.engineer.job_id, self.mentee.job_id],
            [draft.job_id for draft, _ in rows],
        )
        self.assertEqual(["Engineer", "Mentee"], [job.title for _, job in rows])
        self.assertTrue(all(draft.user_id == self.alice.user_id for draft, _ in rows))

    async def test_list_by_user_with_job_is_empty_without_drafts(self):
        self.assertEqual(
            [], await self.repo.list_by_user_with_job(self.session, self.bob.user_id)
        )


if __name__ == "__main__":
    unittest.main()
