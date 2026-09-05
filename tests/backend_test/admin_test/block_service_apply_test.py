import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.admin.block_service import BlockService
from backend.common.recruiting_enums import ApplicationStage
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.users_entity import UsersEntity

TARGET = 5
ACTOR = 2

# Relative to now, never an absolute date: a fixture pinned to a wall-clock date
# is a test that starts failing on a day nobody touched this code.
UPCOMING = datetime.now(timezone.utc) + timedelta(days=3)
STARTED = datetime.now(timezone.utc) - timedelta(days=3)


class _BlockServiceTestBase(unittest.IsolatedAsyncioTestCase):
    """Repositories and fixtures shared by the apply and pre-flight suites.

    Ported from BoardService.blacklist's tests when the kernel moved here. The
    fixtures differ in one honest way: list_by_user returns EVERY application
    of the user, the trigger included, because that is what the repository
    really returns -- the old fixtures could leave it out only because the old
    method handled the trigger separately.
    """

    async def asyncSetUp(self):
        self.users_repo = MagicMock()
        self.app_repo = MagicMock()
        self.sub_repo = MagicMock()
        self.interview_repo = MagicMock()
        self.interview_repo.list_by_application_ids = AsyncMock(return_value=[])
        self.interview_svc = MagicMock()
        self.interview_svc.cancel_for_round = AsyncMock(return_value=True)
        self.session = AsyncMock()

        recorder = patch(
            "backend.admin.block_service.record_event", new_callable=AsyncMock
        )
        self.record_event = recorder.start()
        self.addCleanup(recorder.stop)

        self.service = BlockService(
            users_repository=self.users_repo,
            application_repository=self.app_repo,
            application_submission_repository=self.sub_repo,
            application_interview_repository=self.interview_repo,
            interview_scheduling_service=self.interview_svc,
            logger=MagicMock(),
        )

    # -- fixtures -----------------------------------------------------------

    def _user(self, user_id=TARGET):
        row = UsersEntity(first_name="A", last_name="B")
        row.user_id = user_id
        row.is_blocked = False
        row.blocked_by = None
        row.blocked_at = None
        row.blocked_reason = None
        return row

    def _application(
        self, application_id, stage=ApplicationStage.RECRUITER_SCREENING, tags=None
    ):
        row = ApplicationEntity(
            job_id=1,
            user_id=TARGET,
            stage=stage,
            sub_status="pending",
            current_round=1,
        )
        row.application_id = application_id
        row.tags = tags
        return row

    def _submission(self, application_id=10, is_frozen=False):
        return ApplicationSubmissionEntity(
            application_id=application_id,
            version=1,
            submission={"answers": {}},
            is_frozen=is_frozen,
        )

    def _interview_row(
        self, application_id=10, stage=ApplicationStage.BEHAVIORAL, round=1, start_at=None
    ):
        return SimpleNamespace(
            interview_id=900 + application_id,
            application_id=application_id,
            stage=stage,
            round=round,
            google_event_id=f"evt-{application_id}",
            meet_link=None,
            start_at=start_at or UPCOMING,
            end_at=(start_at or UPCOMING),
            timezone="America/Los_Angeles",
            scheduled_by=ACTOR,
        )

    def _seed(self, applications, user=None):
        """Wire the repositories around a user's full set of applications."""
        by_id = {a.application_id: a for a in applications}
        self.users_repo.get_user_by_user_id = AsyncMock(
            return_value=user if user is not None else self._user()
        )
        self.app_repo.get_by_id = AsyncMock(
            side_effect=lambda _s, application_id, for_update=False: by_id.get(
                application_id
            )
        )
        self.app_repo.list_by_user = AsyncMock(
            return_value=[(a, MagicMock()) for a in applications]
        )
        self.app_repo.update = AsyncMock(side_effect=lambda _s, row: row)
        self.sub_repo.get_current = AsyncMock(return_value=None)
        self.sub_repo.update = AsyncMock(side_effect=lambda _s, row: row)
        return by_id

    async def _apply(self, reason="Fabricated credentials"):
        await self.service.apply_block(
            self.session, actor_id=ACTOR, user_id=TARGET, reason=reason
        )


class TestBlockServiceApply(_BlockServiceTestBase):
    """The block kernel: the three consequences, with no triggering
    application to hang them on."""

    async def test_writes_block_fields_on_the_user(self):
        user = self._user()
        self._seed([self._application(10)], user=user)

        await self._apply()

        self.assertTrue(user.is_blocked)
        self.assertEqual(user.blocked_by, ACTOR)
        self.assertEqual(user.blocked_reason, "Fabricated credentials")
        self.assertIsNotNone(user.blocked_at)

    async def test_missing_user_raises(self):
        self.users_repo.get_user_by_user_id = AsyncMock(return_value=None)
        self.app_repo.list_by_user = AsyncMock(return_value=[])

        with self.assertRaises(ValueError):
            await self._apply()

        self.app_repo.list_by_user.assert_not_awaited()

    async def test_does_not_commit(self):
        """Both callers own their own transaction. If the kernel committed, a
        later failure in the approval flow could not roll the block back."""
        self._seed([self._application(10)])

        await self._apply()

        self.session.commit.assert_not_awaited()

    # -- the application sweep ----------------------------------------------

    async def test_closes_tags_and_freezes_the_application(self):
        application = self._application(10, stage=ApplicationStage.TECH)
        application.current_round = 2
        application.sub_status = "in_progress"
        application.tags = {"existing": "keep-me"}
        current_sub = self._submission(application_id=10, is_frozen=False)
        self._seed([application])
        self.sub_repo.get_current = AsyncMock(return_value=current_sub)

        await self._apply()

        self.assertEqual(application.stage, ApplicationStage.REJECTED)
        self.assertIsNone(application.sub_status)
        self.assertEqual(application.current_round, 1)
        self.assertEqual(application.tags["existing"], "keep-me")
        self.assertTrue(application.tags["blacklisted"])
        self.assertTrue(current_sub.is_frozen)
        self.app_repo.update.assert_awaited_once()

    async def test_row_locks_every_application_it_touches(self):
        self._seed([self._application(10), self._application(11)])

        await self._apply()

        self.assertEqual(
            [c.kwargs["for_update"] for c in self.app_repo.get_by_id.await_args_list],
            [True, True],
        )

    async def test_logs_activity(self):
        self._seed([self._application(10, stage=ApplicationStage.TECH)])

        await self._apply()

        self.record_event.assert_awaited_once_with(
            self.session,
            subject_type="application",
            subject_id=10,
            actor_id=ACTOR,
            event_type="recruiting.blacklisted",
            details={
                "fromStage": ApplicationStage.TECH.value,
                "reason": "Fabricated credentials",
            },
        )

    async def test_sweeps_every_application_including_hired(self):
        """Blacklisting closes out EVERY application of the user (2026-07-22
        decision). In-flight and already-HIRED rows are rejected + tagged;
        already-REJECTED rows that aren't yet tagged get the tag backfilled
        with their stage kept."""
        in_flight = self._application(11, stage=ApplicationStage.APPLIED)
        in_flight.current_round = 2
        hired = self._application(12, stage=ApplicationStage.HIRED)
        rejected = self._application(13, stage=ApplicationStage.REJECTED)
        rejected.current_round = 4
        self._seed([self._application(10, stage=ApplicationStage.TECH),
                    in_flight, hired, rejected])

        await self._apply()

        self.assertEqual(in_flight.stage, ApplicationStage.REJECTED)
        self.assertTrue(in_flight.tags["blacklisted"])
        self.assertIsNone(in_flight.sub_status)
        self.assertEqual(in_flight.current_round, 1)

        self.assertEqual(hired.stage, ApplicationStage.REJECTED)
        self.assertTrue(hired.tags["blacklisted"])
        self.assertEqual(hired.current_round, 1)

        # Stage kept, round kept, only the tag backfilled.
        self.assertEqual(rejected.stage, ApplicationStage.REJECTED)
        self.assertTrue(rejected.tags["blacklisted"])
        self.assertEqual(rejected.current_round, 4)

        self.app_repo.list_by_user.assert_awaited_once_with(self.session, TARGET)
        self.assertEqual(self.record_event.call_count, 4)
        by_app = {
            call.kwargs["subject_id"]: call for call in self.record_event.call_args_list
        }
        self.assertEqual(
            by_app[12].kwargs["details"]["fromStage"], ApplicationStage.HIRED.value
        )
        self.assertEqual(
            by_app[13].kwargs["details"]["fromStage"], ApplicationStage.REJECTED.value
        )

    async def test_skips_already_tagged_applications(self):
        """A prior block already handled some rows; re-running leaves them
        untouched and logs no duplicate activity."""
        prior = self._application(
            11, stage=ApplicationStage.REJECTED, tags={"blacklisted": True}
        )
        prior.current_round = 5
        self._seed([self._application(10, stage=ApplicationStage.TECH), prior])

        await self._apply(reason="Repeat offender")

        self.assertEqual(prior.stage, ApplicationStage.REJECTED)
        self.assertEqual(prior.tags, {"blacklisted": True})
        self.assertEqual(prior.current_round, 5)
        self.assertEqual(self.record_event.call_count, 1)
        self.assertEqual(self.record_event.call_args_list[0].kwargs["subject_id"], 10)

    # -- the meeting sweep --------------------------------------------------

    async def test_cancels_every_upcoming_meeting_it_sweeps(self):
        self._seed([
            self._application(10, stage=ApplicationStage.BEHAVIORAL),
            self._application(11, stage=ApplicationStage.TECH),
        ])
        self.interview_repo.list_by_application_ids = AsyncMock(
            return_value=[
                self._interview_row(application_id=10),
                self._interview_row(
                    application_id=11, stage=ApplicationStage.TECH, round=2
                ),
            ]
        )

        await self._apply()

        self.assertEqual(
            [c.args[1:] for c in self.interview_svc.cancel_for_round.await_args_list],
            [
                (10, ApplicationStage.BEHAVIORAL, 1, ACTOR),
                (11, ApplicationStage.TECH, 2, ACTOR),
            ],
        )
        for call_args in self.interview_svc.cancel_for_round.await_args_list:
            self.assertEqual(call_args.kwargs, {"via": "blacklisted"})

    async def test_never_asks_before_cancelling(self):
        """Unlike an advance or a reject, a block carries no opt-out: the
        candidate is banned org-wide, so the meeting will not happen."""
        self._seed([self._application(10, stage=ApplicationStage.BEHAVIORAL)])
        self.interview_repo.list_by_application_ids = AsyncMock(
            return_value=[self._interview_row(application_id=10)]
        )

        await self._apply()

        self.interview_svc.cancel_for_round.assert_awaited_once()

    async def test_skips_an_already_blacklisted_applications_meeting(self):
        """A row already tagged is left untouched by the sweep, so its meeting
        is not re-cancelled either."""
        self._seed([
            self._application(10, stage=ApplicationStage.BEHAVIORAL),
            self._application(11, stage=ApplicationStage.TECH,
                              tags={"blacklisted": True}),
        ])

        await self._apply()

        self.interview_repo.list_by_application_ids.assert_awaited_once_with(
            self.session, [10]
        )

    async def test_cancels_inside_the_same_transaction(self):
        commits_seen_at_cancel = []

        async def record(*_args, **_kwargs):
            commits_seen_at_cancel.append(self.session.commit.await_count)
            return True

        self.interview_svc.cancel_for_round = AsyncMock(side_effect=record)
        self._seed([self._application(10, stage=ApplicationStage.BEHAVIORAL)])
        self.interview_repo.list_by_application_ids = AsyncMock(
            return_value=[self._interview_row(application_id=10)]
        )

        await self._apply()

        self.assertEqual(commits_seen_at_cancel, [0])


class TestBlockServicePreflight(_BlockServiceTestBase):
    """The pre-flight must mirror the sweep exactly, or the confirm dialog
    lies about what is going to happen."""

    async def test_counts_only_what_will_change(self):
        self._seed([
            self._application(10, stage=ApplicationStage.TECH),
            self._application(12, stage=ApplicationStage.HIRED),
            self._application(11, stage=ApplicationStage.REJECTED,
                              tags={"blacklisted": True}),
        ])
        self.interview_repo.list_by_application_ids = AsyncMock(
            return_value=[
                self._interview_row(application_id=10),
                self._interview_row(application_id=12, start_at=STARTED),
            ]
        )

        view = await self.service.preflight(self.session, TARGET)

        self.assertEqual(view.application_count, 2)
        self.assertEqual(view.interview_times, [UPCOMING])

    async def test_excludes_already_tagged_applications_from_the_interview_scan(self):
        self._seed([
            self._application(10, stage=ApplicationStage.TECH),
            self._application(11, stage=ApplicationStage.REJECTED,
                              tags={"blacklisted": True}),
        ])

        await self.service.preflight(self.session, TARGET)

        self.interview_repo.list_by_application_ids.assert_awaited_once_with(
            self.session, [10]
        )

    async def test_interview_times_are_soonest_first(self):
        later = UPCOMING + timedelta(days=2)
        self._seed([self._application(10), self._application(11)])
        self.interview_repo.list_by_application_ids = AsyncMock(
            return_value=[
                self._interview_row(application_id=11, start_at=later),
                self._interview_row(application_id=10),
            ]
        )

        view = await self.service.preflight(self.session, TARGET)

        self.assertEqual(view.interview_times, [UPCOMING, later])

    async def test_nothing_booked_is_an_empty_list(self):
        self._seed([self._application(10)])

        view = await self.service.preflight(self.session, TARGET)

        self.assertEqual(view.interview_times, [])
        self.assertEqual(view.application_count, 1)


if __name__ == "__main__":
    unittest.main()
