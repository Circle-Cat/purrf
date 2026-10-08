import unittest
from datetime import datetime, timedelta, timezone

from backend.common.communication_enums import ContextType
from backend.entity.email_message_entity import EmailMessageEntity
from backend.entity.email_thread_entity import EmailThreadEntity  # noqa: F401
from backend.entity.users_entity import UsersEntity  # noqa: F401
from backend.repository.email_thread_repository import EmailThreadRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestEmailThreadRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = EmailThreadRepository()

    async def test_create_without_a_user(self):
        thread = await self.repo.create(
            self.session,
            user_id=None,
            gmail_thread_id="g-1",
            subject="Hi",
            context_type=ContextType.INQUIRIES_INBOX,
            context_id=None,
        )
        self.assertIsNone(thread.user_id)
        self.assertIsNone(thread.archived_at)
        self.assertIsNone(thread.archived_by_user_id)

    async def _thread(
        self, key, archived_at=None, context=ContextType.MENTORSHIP_INBOX
    ):
        thread = await self.repo.create(
            self.session,
            user_id=None,
            gmail_thread_id=f"open-{key}",
            subject=key,
            context_type=context,
            context_id=None,
        )
        thread.archived_at = archived_at
        await self.session.flush()
        return thread

    async def _inbound(self, thread, key, at, kind=None, failed=None):
        self.session.add(
            EmailMessageEntity(
                thread_id=thread.thread_id,
                gmail_message_id=f"open-{key}",
                direction="inbound",
                inbound_kind=kind,
                failed_recipients=failed,
                created_at=at,
            )
        )
        await self.session.flush()

    async def test_open_threads_leave_out_only_what_is_still_archived(self):
        t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
        archive = t0 + timedelta(days=1)
        later = archive + timedelta(hours=1)

        never = await self._thread("never")
        quiet = await self._thread("quiet", archive)
        await self._inbound(quiet, "quiet-before", t0, kind="human")
        reopened = await self._thread("reopened", archive)
        await self._inbound(reopened, "reopened-after", later, kind="human")
        legacy = await self._thread("legacy", archive)
        await self._inbound(legacy, "legacy-after", later)
        auto = await self._thread("auto", archive)
        await self._inbound(auto, "auto-after", later, kind="auto_reply")
        bounced = await self._thread("bounced", archive)
        await self._inbound(bounced, "bounced-after", later, kind="bounce")
        legacy_bounce = await self._thread("legacy-bounce", archive)
        await self._inbound(legacy_bounce, "lb-after", later, failed="x@ext.com")
        same_time = await self._thread("same-time", archive)
        await self._inbound(same_time, "same-time-at", archive, kind="human")
        other = await self._thread("other", context=ContextType.INQUIRIES_INBOX)

        mine = {
            t.thread_id
            for t in (
                never,
                quiet,
                reopened,
                legacy,
                auto,
                bounced,
                legacy_bounce,
                same_time,
            )
        }
        listed = await self.repo.list_open_by_context_types(
            self.session, [ContextType.MENTORSHIP_INBOX]
        )

        self.assertEqual(
            [t.subject for t in listed if t.thread_id in mine],
            ["never", "reopened", "legacy"],
        )
        self.assertNotIn(other.thread_id, {t.thread_id for t in listed})
        self.assertEqual(
            await self.repo.list_open_by_context_types(self.session, []), []
        )


if __name__ == "__main__":
    unittest.main()
