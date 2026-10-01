import unittest
from unittest.mock import AsyncMock, Mock

from sqlalchemy import select

from backend.common.ops_enums import OPS_ALERT_SUBJECT_TYPE
from backend.communication.gmail_sync_service import GmailSyncService, PushOutcome
from backend.entity.event_entity import EventEntity
from backend.ops import recipient_resolvers  # noqa: F401 (registers)
from backend.ops.ops_alert_service import OpsAlertService
from backend.repository.gmail_sync_state_repository import GmailSyncStateRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_MAILBOX = "purrf-db-test@example.com"
_WRITTEN = "gmail_sync_db_test"


class _WritingHandler:
    """Writes one event per thread, then fails for ``failing`` after the write."""

    def __init__(self, failing):
        self.failing = failing

    async def sync_tracked_thread(self, session, thread):
        session.add(
            EventEntity(
                subject_type=_WRITTEN,
                subject_id=1,
                actor_id=None,
                event_type="test.synced",
                details={"thread": thread.gmail_thread_id},
            )
        )
        await session.flush()
        if thread.gmail_thread_id == self.failing:
            raise RuntimeError("failed after its insert")
        return 1


class TestGmailSyncServiceOnARealSession(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.gmail = Mock()
        self.gmail.get_profile.return_value = {
            "email_address": _MAILBOX,
            "history_id": 500,
        }
        self.gmail.list_history.return_value = {
            "history_id": 150,
            "thread_ids": {"t-bad", "t-ok"},
        }
        threads = AsyncMock()
        threads.get_by_gmail_thread_id.side_effect = lambda session, gid: Mock(
            gmail_thread_id=gid, context_type="application"
        )
        registry = Mock()
        registry.get.return_value = _WritingHandler(failing="t-bad")
        self.states = GmailSyncStateRepository()
        self.service = GmailSyncService(
            gmail_client=self.gmail,
            state_repository=self.states,
            thread_repository=threads,
            context_registry=registry,
            ops_alerts=OpsAlertService(logger=Mock()),
            watch_topic="projects/p/topics/gmail",
            database=Mock(),
            logger=Mock(),
        )
        self.state = await self.states.create(self.session, _MAILBOX, 100)
        await self.session.commit()

    async def _written_threads(self):
        result = await self.session.execute(
            select(EventEntity.details).where(EventEntity.subject_type == _WRITTEN)
        )
        return [details["thread"] for details in result.scalars()]

    async def test_a_failing_thread_rolls_back_only_its_own_writes(self):
        outcome = await self.service.handle_push(self.session, _MAILBOX, 120)

        self.assertEqual(outcome, PushOutcome.ACK)
        self.assertEqual(await self._written_threads(), ["t-ok"])
        # Read off the entity loaded before the savepoint rollback: an
        # expired attribute here would raise MissingGreenlet.
        self.assertEqual(self.state.last_history_id, 150)
        self.assertIn("t-bad", self.state.last_error)
        self.assertEqual(self.state.last_alert_kind, "sync_failed")
        fresh = await self.states.get(self.session, _MAILBOX)
        self.assertEqual(fresh.last_history_id, 150)
        alerts = await self.session.execute(
            select(EventEntity).where(
                EventEntity.subject_type == OPS_ALERT_SUBJECT_TYPE,
                EventEntity.subject_id == self.state.id,
            )
        )
        self.assertEqual(len(alerts.scalars().all()), 1)


if __name__ == "__main__":
    unittest.main()
