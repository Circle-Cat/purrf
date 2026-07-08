import unittest
import uuid
from datetime import datetime, timezone

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.application_comment_repository import (
    ApplicationCommentRepository,
)
from backend.repository.application_comment_mention_repository import (
    ApplicationCommentMentionRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column, unique email."""
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        primary_email=f"{uuid.uuid4().hex}@test.com",
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestApplicationCommentMentionRepository(BaseRepositoryTestLib):
    async def _seed_comment(self):
        """Create a job, two users, an application, and one comment on it.

        Returns:
            tuple[ApplicationCommentEntity, UsersEntity, UsersEntity]: The
                seeded comment, its author, and a second user usable as a
                mention target.
        """
        job = JobEntity(kind=JobKind.ACTIVITY, title="T", status=JobStatus.PUBLISHED)
        author = _make_user()
        mentioned = _make_user()
        await self.insert_entities([job, author, mentioned])
        app = ApplicationEntity(
            job_id=job.job_id,
            user_id=author.user_id,
            stage=ApplicationStage.RECRUITER_SCREENING,
        )
        await self.insert_entities([app])
        comment_repo = ApplicationCommentRepository()
        comment = await comment_repo.create(
            self.session, app.application_id, author.user_id, "Hey @[?]"
        )
        return comment, author, mentioned

    async def test_get_by_comment_ids_returns_empty_before_any_mention(self):
        comment, _author, _mentioned = await self._seed_comment()
        repo = ApplicationCommentMentionRepository()

        result = await repo.get_by_comment_ids(self.session, [comment.comment_id])

        self.assertEqual(result, [])

    async def test_create_mentions_persists_one_row_per_id(self):
        comment, _author, mentioned = await self._seed_comment()
        repo = ApplicationCommentMentionRepository()

        await repo.create_mentions(
            self.session, comment.comment_id, [mentioned.user_id]
        )
        result = await repo.get_by_comment_ids(self.session, [comment.comment_id])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].comment_id, comment.comment_id)
        self.assertEqual(result[0].mentioned_user_id, mentioned.user_id)

    async def test_get_by_comment_ids_only_returns_rows_for_those_comments(self):
        comment1, author, mentioned = await self._seed_comment()
        comment_repo = ApplicationCommentRepository()
        comment2 = await comment_repo.create(
            self.session, comment1.application_id, author.user_id, "Second"
        )
        repo = ApplicationCommentMentionRepository()
        await repo.create_mentions(
            self.session, comment1.comment_id, [mentioned.user_id]
        )
        await repo.create_mentions(
            self.session, comment2.comment_id, [mentioned.user_id]
        )

        result = await repo.get_by_comment_ids(self.session, [comment1.comment_id])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].comment_id, comment1.comment_id)

    async def test_get_by_comment_ids_empty_list_returns_empty(self):
        repo = ApplicationCommentMentionRepository()

        result = await repo.get_by_comment_ids(self.session, [])

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
