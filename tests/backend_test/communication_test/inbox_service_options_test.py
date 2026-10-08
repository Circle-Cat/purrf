import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType
from backend.common.permissions import Permission
from backend.common.recruiting_enums import ApplicationStage, JobKind
from tests.backend_test.communication_test.inbox_service_read_test import (
    _ALL,
    _Fixture,
    _in,
    _out,
    _thread,
    _user,
    _viewer,
)

_ANALYST = SimpleNamespace(job_id=5, kind=JobKind.EMPLOYMENT, title="Data Analyst")
_DESIGNER = SimpleNamespace(job_id=9, kind=JobKind.EMPLOYMENT, title="Designer")
_MENTEE = SimpleNamespace(job_id=6, kind=JobKind.ACTIVITY, title="Mentee 2026")


def _application(application_id, job, stage, user_id):
    return SimpleNamespace(
        application_id=application_id, job_id=job.job_id, user_id=user_id, stage=stage
    )


def _attached(mid, minutes, attachments):
    message = _in(mid, minutes, attachments=attachments)
    message.gmail_message_id = f"gm-{mid}"
    return message


class _OptionsFixture(_Fixture):
    def setUp(self):
        super().setUp()
        self.threads = [
            _thread(1, ContextType.MENTORSHIP_INBOX),
            _thread(2, ContextType.RECRUITING_INBOX),
            _thread(3, ContextType.INQUIRIES_INBOX),
            _thread(4, ContextType.MENTORSHIP_INBOX),
            _thread(5, ContextType.ACTIVITY, 8, user_id=32),
        ]
        self.messages = {
            1: [
                _attached(
                    10,
                    0,
                    [
                        {"name": "cv.pdf", "size": 3, "gmailAttachmentId": "att-a"},
                        {"name": "b.png", "size": 4, "gmailAttachmentId": "att-b"},
                    ],
                )
            ],
            2: [_in(20, 0)],
            3: [
                _attached(
                    30, 0, [{"name": "q.txt", "size": 1, "gmailAttachmentId": "att-q"}]
                )
            ],
            4: [_out(40, 0)],
            5: [
                _attached(
                    50, 0, [{"name": "id.pdf", "size": 2, "gmailAttachmentId": "att-i"}]
                )
            ],
        }
        self.gmail.get_attachment = Mock(return_value=b"BYTES")


class DownloadTest(_OptionsFixture):
    async def test_downloads_by_gmail_attachment_id_and_returns_the_name(self):
        content, name = await self.service.download_attachment(
            self.session, _viewer(*_ALL), 1, 10, 1
        )

        self.assertEqual((content, name), (b"BYTES", "b.png"))
        self.gmail.get_attachment.assert_called_once_with("gm-10", "att-b")

    async def test_an_assigned_thread_still_serves_its_attachments(self):
        viewer = _viewer(Permission.MENTORSHIP_ADMIN_WRITE)

        content, name = await self.service.download_attachment(
            self.session, viewer, 5, 50, 0
        )

        self.assertEqual((content, name), (b"BYTES", "id.pdf"))
        self.gmail.get_attachment.assert_called_once_with("gm-50", "att-i")

    async def test_an_assigned_thread_of_a_hidden_service_is_not_found(self):
        viewer = _viewer(Permission.INQUIRIES_MANAGE)

        with self.assertRaisesRegex(ValueError, "thread 5 not found"):
            await self.service.download_attachment(self.session, viewer, 5, 50, 0)

        self.gmail.get_attachment.assert_not_called()

    async def test_message_of_another_thread_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "attachment not found"):
            await self.service.download_attachment(
                self.session, _viewer(*_ALL), 1, 30, 0
            )

        self.gmail.get_attachment.assert_not_called()

    async def test_out_of_range_and_negative_index_are_rejected(self):
        for index in (2, -1):
            with self.assertRaisesRegex(ValueError, "attachment not found"):
                await self.service.download_attachment(
                    self.session, _viewer(*_ALL), 1, 10, index
                )

        self.gmail.get_attachment.assert_not_called()

    async def test_message_without_attachments_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "attachment not found"):
            await self.service.download_attachment(
                self.session, _viewer(*_ALL), 2, 20, 0
            )

    async def test_invisible_thread_is_not_found(self):
        viewer = _viewer(Permission.MENTORSHIP_ADMIN_WRITE)

        with self.assertRaisesRegex(ValueError, "thread 3 not found"):
            await self.service.download_attachment(self.session, viewer, 3, 30, 0)

        self.gmail.get_attachment.assert_not_called()


class RoundOptionsTest(_OptionsFixture):
    def setUp(self):
        super().setUp()
        self.rounds = [
            SimpleNamespace(round_id=9, name="2026 Fall"),
            SimpleNamespace(round_id=8, name="2026 Summer"),
            SimpleNamespace(round_id=7, name="2026 Spring"),
        ]
        self.rounds_service.get_round_slots = AsyncMock(
            return_value=SimpleNamespace(active_round_id=8, registration_round_id=9)
        )
        self.participant_repo.get_by_user_id_and_round_id = AsyncMock(
            side_effect=lambda s, uid, rid: object() if (uid, rid) == (32, 7) else None
        )

    async def test_marks_the_active_round_and_the_registered_ones(self):
        result = await self.service.assign_options(self.session, _viewer(*_ALL), 1, 32)

        self.assertIsNone(result.jobs)
        self.assertEqual(
            [(r.round_id, r.name, r.current, r.registered) for r in result.rounds],
            [
                (9, "2026 Fall", False, False),
                (8, "2026 Summer", True, False),
                (7, "2026 Spring", False, True),
            ],
        )

    async def test_no_active_round_marks_none_current(self):
        self.rounds_service.get_round_slots.return_value = SimpleNamespace(
            active_round_id=None
        )

        result = await self.service.assign_options(self.session, _viewer(*_ALL), 1, 32)

        self.assertFalse(any(r.current for r in result.rounds))

    async def test_inquiries_thread_cannot_be_assigned(self):
        with self.assertRaises(ValueError):
            await self.service.assign_options(self.session, _viewer(*_ALL), 3, 32)

    async def test_tracked_thread_cannot_be_assigned(self):
        with self.assertRaises(ValueError):
            await self.service.assign_options(self.session, _viewer(*_ALL), 4, 32)

    async def test_invisible_thread_is_not_found(self):
        viewer = _viewer(Permission.RECRUITING_APPLICATION_ADVANCE)

        with self.assertRaisesRegex(ValueError, "thread 1 not found"):
            await self.service.assign_options(self.session, viewer, 1, 32)

    async def test_assigned_thread_is_not_found(self):
        with self.assertRaisesRegex(ValueError, "thread 5 not found"):
            await self.service.assign_options(self.session, _viewer(*_ALL), 5, 32)


class JobOptionsTest(_OptionsFixture):
    def setUp(self):
        super().setUp()
        self.applications = []
        self.application_repo.list_by_user = AsyncMock(
            side_effect=lambda s, uid: [
                (
                    a,
                    next(
                        j
                        for j in (_ANALYST, _DESIGNER, _MENTEE)
                        if j.job_id == a.job_id
                    ),
                )
                for a in self.applications
                if a.user_id == uid
            ]
        )

    async def _options(self, person_id):
        return await self.service.assign_options(
            self.session, _viewer(*_ALL), 2, person_id
        )

    async def test_person_without_employment_applications_gets_an_empty_list(self):
        self.applications = [_application(1, _MENTEE, ApplicationStage.APPLIED, 41)]

        result = await self._options(41)

        self.assertIsNone(result.rounds)
        self.assertEqual(result.jobs, [])

    async def test_all_rejected_falls_back_to_the_newest(self):
        self.applications = [
            _application(10, _ANALYST, ApplicationStage.REJECTED, 40),
            _application(12, _ANALYST, ApplicationStage.REJECTED, 40),
            _application(11, _ANALYST, ApplicationStage.REJECTED, 40),
        ]

        (job,) = (await self._options(40)).jobs

        self.assertEqual(
            (
                job.job_id,
                job.title,
                job.application_id,
                job.application_status,
                job.fallback,
            ),
            (5, "Data Analyst", 12, "rejected", True),
        )

    async def test_live_application_beats_a_newer_rejected_one(self):
        self.applications = [
            _application(10, _ANALYST, ApplicationStage.TECH, 40),
            _application(12, _ANALYST, ApplicationStage.REJECTED, 40),
        ]

        (job,) = (await self._options(40)).jobs

        self.assertEqual((job.application_id, job.fallback), (10, False))

    async def test_every_employment_job_is_listed_newest_pick_first(self):
        self.applications = [
            _application(10, _ANALYST, ApplicationStage.APPLIED, 40),
            _application(11, _DESIGNER, ApplicationStage.APPLIED, 40),
            _application(12, _MENTEE, ApplicationStage.APPLIED, 40),
            _application(13, _ANALYST, ApplicationStage.APPLIED, 99),
        ]

        result = await self._options(40)

        self.assertEqual(
            [(j.job_id, j.application_id) for j in result.jobs], [(9, 11), (5, 10)]
        )


class SearchPeopleTest(_OptionsFixture):
    def setUp(self):
        super().setUp()
        self.found = [_user(7, "Ann", "Lee"), _user(42, "Bo", "Chan")]
        self.user_repo.list_users = AsyncMock(
            side_effect=lambda s, **kw: (
                [(u, False) for u in self.found],
                len(self.found),
            )
        )
        self.user_repo.get_user_by_user_id = AsyncMock(
            side_effect=lambda s, uid: next(
                (u for u in self.found + [_user(5, "Cy", "Dow")] if u.user_id == uid),
                None,
            )
        )
        self.email_repo.get_contact_emails_by_user_ids = AsyncMock(
            side_effect=lambda s, ids: {i: f"u{i}@ext.com" for i in ids if i != 7}
        )

    async def test_returns_name_and_contact_email(self):
        result = await self.service.search_people(self.session, "ann")

        self.assertEqual(
            [(p.user_id, p.name, p.email) for p in result],
            [(7, "Ann Lee", None), (42, "Bo Chan", "u42@ext.com")],
        )
        self.user_repo.list_users.assert_awaited_once()
        self.assertEqual(self.user_repo.list_users.await_args.kwargs["search"], "ann")
        self.assertEqual(self.user_repo.list_users.await_args.kwargs["limit"], 20)

    async def test_digit_query_puts_the_exact_id_first_without_duplicating(self):
        for q in ("42", "#42"):
            result = await self.service.search_people(self.session, q)

            self.assertEqual([p.user_id for p in result], [42, 7])

    async def test_digit_query_adds_an_exact_hit_the_text_search_missed(self):
        result = await self.service.search_people(self.session, "5")

        self.assertEqual([p.user_id for p in result], [5, 7, 42])

    async def test_never_returns_more_than_twenty(self):
        self.found = [_user(100 + i, "A", str(i)) for i in range(20)]

        result = await self.service.search_people(self.session, "#5")

        self.assertEqual(len(result), 20)
        self.assertEqual(result[0].user_id, 5)

    async def test_blocked_people_are_not_offered(self):
        blocked = _user(5, "Cy", "Dow")
        blocked.is_blocked = True
        self.user_repo.get_user_by_user_id = AsyncMock(return_value=blocked)

        result = await self.service.search_people(self.session, "5")

        self.assertIs(self.user_repo.list_users.await_args.kwargs["is_blocked"], False)
        self.assertEqual([p.user_id for p in result], [7, 42])

    async def test_blank_query_returns_nothing(self):
        self.assertEqual(await self.service.search_people(self.session, "  "), [])
        self.user_repo.list_users.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
