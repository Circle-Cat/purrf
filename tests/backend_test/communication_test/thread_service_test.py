import unittest
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType, InboxService
from backend.common.recruiting_enums import JobKind
from backend.communication.thread_service import ThreadServiceResolver


def _thread(context_type, context_id=None):
    return Mock(context_type=context_type, context_id=context_id)


class ThreadServiceResolverTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.jobs = AsyncMock()
        self.resolver = ThreadServiceResolver(job_repository=self.jobs)
        self.session = Mock()

    async def test_inbox_contexts_map_to_their_own_service(self):
        expected = {
            ContextType.MENTORSHIP_INBOX: InboxService.MENTORSHIP,
            ContextType.RECRUITING_INBOX: InboxService.RECRUITING,
            ContextType.INQUIRIES_INBOX: InboxService.INQUIRIES,
        }
        for context_type, service in expected.items():
            with self.subTest(context_type=context_type):
                self.assertEqual(
                    await self.resolver.service_of(self.session, _thread(context_type)),
                    service,
                )
        self.jobs.get_by_application_id.assert_not_awaited()

    async def test_an_activity_thread_is_mentorship(self):
        service = await self.resolver.service_of(
            self.session, _thread(ContextType.ACTIVITY, 4)
        )

        self.assertEqual(service, InboxService.MENTORSHIP)

    async def test_an_application_to_an_activity_job_is_mentorship(self):
        self.jobs.get_by_application_id.return_value = Mock(kind=JobKind.ACTIVITY)

        service = await self.resolver.service_of(
            self.session, _thread(ContextType.APPLICATION, 31)
        )

        self.assertEqual(service, InboxService.MENTORSHIP)
        self.jobs.get_by_application_id.assert_awaited_once_with(self.session, 31)

    async def test_an_application_to_an_employment_job_is_recruiting(self):
        self.jobs.get_by_application_id.return_value = Mock(kind=JobKind.EMPLOYMENT)

        service = await self.resolver.service_of(
            self.session, _thread(ContextType.APPLICATION, 32)
        )

        self.assertEqual(service, InboxService.RECRUITING)

    async def test_an_application_whose_job_is_gone_raises(self):
        self.jobs.get_by_application_id.return_value = None

        with self.assertRaises(ValueError):
            await self.resolver.service_of(
                self.session, _thread(ContextType.APPLICATION, 33)
            )

    async def test_a_context_with_no_service_raises(self):
        with self.assertRaises(ValueError):
            await self.resolver.service_of(self.session, _thread(ContextType.BROADCAST))


if __name__ == "__main__":
    unittest.main()
