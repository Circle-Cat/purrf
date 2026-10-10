import copy
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock
from dateutil.parser import isoparse
from backend.mentorship.matching_eligibility import (
    HistoryFinding,
    IneligibleReason,
)
from backend.mentorship.mentorship_admin_service import MentorshipAdminService
from backend.repository.user_id_condition import UserIdCondition
from backend.dto.participant_search_filter_dto import (
    ParticipantSearchFilterDto,
    UnregisteredFilterDto,
)
from backend.dto.participant_search_row_dto import (
    ParticipantSearchPairRow,
    ParticipantSearchRow,
    PersonSearchRow,
)
from backend.dto.admin_meeting_log_dto import AdminMeetingDto
from backend.dto.v2_meeting_batch_update_dto import (
    V2MeetingBatchUpdateDto,
    V2MeetingUpdateItemDto,
)
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    MeetingNoteTag,
    MeetingSource,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
    PairStatus,
    ParticipantNoteTag,
)


def _make_row(**kwargs):
    row_fields = dict(
        user_id=1,
        round_id=None,
        participant_role=None,
        approval_status=None,
        is_blocked=False,
        is_deactivated=False,
        is_internal=False,
    )
    row_fields.update(kwargs)
    return ParticipantSearchRow(**row_fields)


def _search_pair(
    pair_id, mentor_id, mentee_id, pair_status=PairStatus.ACTIVE, completed_count=0
):
    return ParticipantSearchPairRow(
        pair_id=pair_id,
        mentor_id=mentor_id,
        mentee_id=mentee_id,
        pair_status=pair_status,
        completed_count=completed_count,
    )


def _make_pair(mentor_id=1, mentee_id=2, pair_id=1):
    pair = MagicMock()
    pair.pair_id = pair_id
    pair.mentor_id = mentor_id
    pair.mentee_id = mentee_id
    # A stand-in for the legacy JSONB blob. apply_v2_meeting_batch must never
    # read or write this -- present so the "left untouched" pin test has
    # something concrete to compare against.
    pair.meeting_log = {"untouched": True}
    return pair


def _make_meeting(
    meeting_id="m1",
    pair_id=1,
    source=MeetingSource.GOOGLE,
    start_datetime="2024-01-01T10:00:00+00:00",
    end_datetime="2024-01-01T11:00:00+00:00",
    is_completed=False,
    created_datetime="2024-01-01T09:00:00+00:00",
    absent_user_id=None,
    late_user_ids=None,
    has_unknown_absent=None,
    has_unknown_late=None,
    has_insufficient_duration=None,
):
    """A real (unpersisted) MentorshipMeetingEntity -- this is what the admin
    read and edit paths now work with instead of JSONB dict entries."""
    return MentorshipMeetingEntity(
        meeting_id=meeting_id,
        pair_id=pair_id,
        source=source,
        start_datetime=isoparse(start_datetime) if start_datetime else None,
        end_datetime=isoparse(end_datetime) if end_datetime else None,
        is_completed=is_completed,
        created_datetime=isoparse(created_datetime) if created_datetime else None,
        absent_user_id=absent_user_id,
        late_user_ids=late_user_ids,
        has_unknown_absent=has_unknown_absent,
        has_unknown_late=has_unknown_late,
        has_insufficient_duration=has_insufficient_duration,
    )


def _round_in_progress():
    now = datetime.now(timezone.utc)
    return MagicMock(
        promotion_start_at=now - timedelta(days=1),
        feedback_deadline_at=now + timedelta(days=1),
    )


def _round_ended():
    now = datetime.now(timezone.utc)
    return MagicMock(
        promotion_start_at=now - timedelta(days=200),
        feedback_deadline_at=now - timedelta(days=1),
    )


class TestMentorshipAdminService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_notes = MagicMock()
        self.mock_notes.list_tagged = AsyncMock(return_value=[])
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_users_and_emails_by_ids = AsyncMock()

        self.mock_participants_repo = MagicMock()
        self.mock_participants_repo.search_participants_for_admin = AsyncMock()

        self.mock_rounds_repo = MagicMock()
        self.mock_rounds_repo.get_all_rounds = AsyncMock(return_value=[])

        self.mock_training_repo = MagicMock()
        self.mock_training_repo.get_training_by_user_ids_and_categories = AsyncMock(
            return_value=[]
        )

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_pair_by_id = AsyncMock()

        self.mock_meeting_repo = MagicMock()
        self.mock_meeting_repo.get_meetings_by_pair = AsyncMock(return_value=[])
        self.mock_meeting_repo.get_meetings_by_pairs = AsyncMock(return_value={})
        self.mock_meeting_repo.delete_meetings = AsyncMock(return_value=0)
        self.mock_meeting_repo.recalculate_completed_count = AsyncMock(return_value=0)

        self.mock_participants_repo.search_unregistered_for_admin = AsyncMock()
        self.mock_participants_repo.list_registered_rounds_by_user_ids = AsyncMock(
            return_value={}
        )
        self.mock_rounds_repo.get_by_round_id = AsyncMock(
            return_value=_round_in_progress()
        )

        self.mock_application_repo = MagicMock()
        self.mock_application_repo.list_hired_activity_roles_by_user_ids = AsyncMock(
            return_value={}
        )

        self.mock_mapper = MagicMock()
        self.mock_mapper.map_to_admin_meeting_dto.side_effect = (
            lambda meeting, *, is_completed, note_tags: AdminMeetingDto(
                meeting_id=meeting["meeting_id"],
                start_datetime=meeting["start_datetime"],
                end_datetime=meeting["end_datetime"],
                is_completed=is_completed,
                note=note_tags,
                create_datetime=meeting["created_datetime"],
            )
        )

        self.mock_session = AsyncMock()
        self.mock_logger = MagicMock()
        self.mock_eligibility = MagicMock()
        self.mock_eligibility.eligible_user_ids = AsyncMock(return_value=set())
        self.mock_eligibility.needs_exemption = AsyncMock(return_value={})
        self.mock_approvals = MagicMock()
        self.mock_approvals.pending_exemptions = AsyncMock(return_value={})

        self.mock_email_service = MagicMock()
        self.notified_query = object()
        self.mock_email_service.notified_user_ids = AsyncMock(
            return_value=self.notified_query
        )

        self.service = MentorshipAdminService(
            users_repository=self.mock_users_repo,
            participants_repository=self.mock_participants_repo,
            rounds_repository=self.mock_rounds_repo,
            training_repository=self.mock_training_repo,
            pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            logger=self.mock_logger,
            mentorship_meeting_repository=self.mock_meeting_repo,
            application_repository=self.mock_application_repo,
            matching_eligibility_service=self.mock_eligibility,
            mentorship_approval_service=self.mock_approvals,
            note_repository=self.mock_notes,
            approval_service=MagicMock(),
            mentorship_email_service=self.mock_email_service,
        )

    async def test_each_row_counts_the_marks_in_its_own_round(self):
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(user_id=21, round_id=7),
                _make_row(user_id=21, round_id=5),
                _make_row(user_id=22, round_id=7),
            ],
            3,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                uid: MagicMock(
                    user_id=uid, first_name="U", last_name="X", preferred_name=None
                )
                for uid in (21, 22)
            },
            {},
        )

        def _note(user_id, round_id, tag):
            return SimpleNamespace(user_id=user_id, round_id=round_id, tag=tag)

        self.mock_notes.list_tagged.return_value = [
            _note(21, 7, ParticipantNoteTag.NO_SHOW),
            _note(21, 7, ParticipantNoteTag.NO_SHOW),
            _note(21, 5, ParticipantNoteTag.RED_FLAG),
            _note(22, 7, ParticipantNoteTag.RED_FLAG),
        ]

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto(user_id=21)
        )

        self.assertEqual(
            [
                (r.user_id, r.round_id, r.marks.no_show, r.marks.red_flag)
                for r in result.participant_rows
            ],
            [(21, 7, 2, 0), (21, 5, 0, 1), (22, 7, 0, 1)],
        )
        self.mock_notes.list_tagged.assert_awaited_once_with(
            self.mock_session,
            [21, 22],
            [ParticipantNoteTag.NO_SHOW, ParticipantNoteTag.RED_FLAG],
        )
        self.assertEqual(
            result.participant_rows[0].marks.model_dump(by_alias=True),
            {"noShow": 2, "redFlag": 0},
        )

    async def test_meeting_log_says_whether_its_round_is_in_progress(self):
        pair = _make_pair()
        pair.round_id = 7
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        self.mock_rounds_repo.get_by_round_id.return_value = _round_in_progress()
        live = await self.service.get_meeting_log(self.mock_session, pair_id=1)
        self.mock_rounds_repo.get_by_round_id.return_value = _round_ended()
        ended = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertTrue(live.round_in_progress)
        self.assertFalse(ended.round_in_progress)
        self.mock_rounds_repo.get_by_round_id.assert_awaited_with(self.mock_session, 7)

    async def test_apply_batch_refuses_a_round_that_has_ended(self):
        """A past round's meeting log is history: nothing is deleted or
        changed, and the refusal names its code for the page."""
        pair = _make_pair()
        google = _make_meeting(meeting_id="google-1", is_completed=False)
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [google]
        self.mock_rounds_repo.get_by_round_id.return_value = _round_ended()

        with self.assertRaises(ConflictError) as caught:
            await self.service.apply_v2_meeting_batch(
                self.mock_session,
                1,
                V2MeetingBatchUpdateDto(
                    updates=[
                        V2MeetingUpdateItemDto(meeting_id="google-1", is_completed=True)
                    ],
                    deletes=[],
                ),
            )

        self.assertEqual(caught.exception.code, "round_not_in_progress")
        self.assertFalse(google.is_completed)
        self.mock_meeting_repo.delete_meetings.assert_not_awaited()
        self.mock_session.commit.assert_not_awaited()

    async def test_unregistered_unknown_round_raises(self):
        self.mock_rounds_repo.get_by_round_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.search_unregistered(
                self.mock_session, 9, UnregisteredFilterDto()
            )

        self.mock_participants_repo.search_unregistered_for_admin.assert_not_awaited()

    async def test_unregistered_is_refused_for_a_round_not_in_progress(self):
        now = datetime.now(timezone.utc)
        for label, (start, end) in {
            "not started": (now + timedelta(days=1), now + timedelta(days=2)),
            "over": (now - timedelta(days=2), now - timedelta(days=1)),
        }.items():
            with self.subTest(label):
                self.mock_rounds_repo.get_by_round_id.return_value = MagicMock(
                    promotion_start_at=start, feedback_deadline_at=end
                )
                with self.assertRaises(ValueError):
                    await self.service.search_unregistered(
                        self.mock_session, 9, UnregisteredFilterDto()
                    )

        self.mock_participants_repo.search_unregistered_for_admin.assert_not_awaited()

    async def test_unregistered_empty_page_skips_the_lookups(self):
        self.mock_participants_repo.search_unregistered_for_admin.return_value = (
            [],
            0,
        )

        result = await self.service.search_unregistered(
            self.mock_session, 9, UnregisteredFilterDto()
        )

        self.assertEqual((result.rows, result.total), ([], 0))
        self.mock_users_repo.get_users_and_emails_by_ids.assert_not_awaited()
        self.mock_application_repo.list_hired_activity_roles_by_user_ids.assert_not_awaited()

    async def test_unregistered_rows_carry_roles_and_past_rounds(self):
        """Roles come back mentor first whatever the set's order; rounds taken
        part counts the person's rounds and last round is the first of them
        (the repository orders them latest first)."""
        filters = UnregisteredFilterDto(q="ada")
        self.mock_participants_repo.search_unregistered_for_admin.return_value = (
            [
                PersonSearchRow(
                    user_id=5, is_blocked=True, is_deactivated=False, is_internal=False
                ),
                PersonSearchRow(
                    user_id=6, is_blocked=False, is_deactivated=True, is_internal=True
                ),
            ],
            12,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                5: MagicMock(first_name="Ada", last_name="Lee", preferred_name=None),
                6: MagicMock(first_name="Ben", last_name="Ng", preferred_name="B"),
            },
            {
                5: [
                    MagicMock(email="ada@x.com", is_primary=True),
                    MagicMock(email="ada@old.com", is_primary=False),
                ],
            },
        )
        self.mock_application_repo.list_hired_activity_roles_by_user_ids.return_value = {
            5: {ParticipantRole.MENTEE, ParticipantRole.MENTOR},
            6: {ParticipantRole.MENTEE},
        }
        fall, spring = MagicMock(), MagicMock()
        fall.name, spring.name = "2025 Fall", "2025 Spring"
        self.mock_participants_repo.list_registered_rounds_by_user_ids.return_value = {
            5: [fall, spring],
        }

        result = await self.service.search_unregistered(
            self.mock_session, 9, filters, limit=10, offset=20, order="desc"
        )

        self.mock_participants_repo.search_unregistered_for_admin.assert_awaited_once_with(
            self.mock_session, 9, filters, 10, 20, "desc", user_id_condition=None
        )
        self.mock_application_repo.list_hired_activity_roles_by_user_ids.assert_awaited_once_with(
            self.mock_session, [5, 6]
        )
        self.assertEqual(result.total, 12)
        ada, ben = result.rows
        self.assertEqual(
            (
                ada.admitted_roles,
                ada.rounds_taken_part,
                ada.last_round_name,
                ada.primary_email,
                ada.alternative_emails,
                ada.is_blocked,
                ada.is_deactivated,
            ),
            (
                [ParticipantRole.MENTOR, ParticipantRole.MENTEE],
                2,
                "2025 Fall",
                "ada@x.com",
                ["ada@old.com"],
                True,
                False,
            ),
        )
        self.assertEqual(
            (
                ben.admitted_roles,
                ben.rounds_taken_part,
                ben.last_round_name,
                ben.primary_email,
                ben.is_deactivated,
                ben.is_internal,
            ),
            ([ParticipantRole.MENTEE], 0, None, None, True, True),
        )
        wire = result.model_dump(by_alias=True, mode="json")["rows"][0]
        self.assertEqual(
            {k: wire[k] for k in ("admittedRoles", "roundsTakenPart", "lastRoundName")},
            {
                "admittedRoles": ["mentor", "mentee"],
                "roundsTakenPart": 2,
                "lastRoundName": "2025 Fall",
            },
        )

    async def test_notification_state_picks_what_to_keep_or_leave_out(self):
        self.mock_participants_repo.search_participants_for_admin.return_value = ([], 0)
        cases = {
            "notified": (dict(sent=True, scheduled=False), False),
            "scheduled": (dict(sent=False, scheduled=True), False),
            "not_notified": (dict(sent=True, scheduled=True), True),
        }
        for state, (flags, exclude) in cases.items():
            with self.subTest(state=state):
                self.mock_email_service.notified_user_ids.reset_mock()
                await self.service.search_participants(
                    self.mock_session,
                    ParticipantSearchFilterDto(
                        round_id=7,
                        notification_stage="midterm_reminder",
                        notification_state=state,
                    ),
                )
                self.mock_email_service.notified_user_ids.assert_awaited_once_with(
                    self.mock_session, 7, "midterm_reminder", **flags
                )
                call = self.mock_participants_repo.search_participants_for_admin.await_args
                self.assertEqual(
                    call.kwargs["user_id_condition"],
                    UserIdCondition(self.notified_query, exclude=exclude),
                )

    async def test_unregistered_takes_the_notification_filter(self):
        self.mock_participants_repo.search_unregistered_for_admin.return_value = ([], 0)
        await self.service.search_unregistered(
            self.mock_session,
            9,
            UnregisteredFilterDto(
                notification_stage="round_recruitment",
                notification_state="not_notified",
            ),
        )
        self.mock_email_service.notified_user_ids.assert_awaited_once_with(
            self.mock_session, 9, "round_recruitment", sent=True, scheduled=True
        )
        call = self.mock_participants_repo.search_unregistered_for_admin.await_args
        self.assertEqual(
            call.kwargs["user_id_condition"],
            UserIdCondition(self.notified_query, exclude=True),
        )

    async def test_without_the_notification_filter_kit_is_not_involved(self):
        self.mock_participants_repo.search_participants_for_admin.return_value = ([], 0)
        await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto(round_id=7)
        )
        self.mock_email_service.notified_user_ids.assert_not_awaited()
        call = self.mock_participants_repo.search_participants_for_admin.await_args
        self.assertIsNone(call.kwargs["user_id_condition"])

    async def test_notification_filter_needs_both_halves_and_a_round(self):
        for filters in (
            ParticipantSearchFilterDto(round_id=7, notification_stage="admission"),
            ParticipantSearchFilterDto(round_id=7, notification_state="notified"),
            ParticipantSearchFilterDto(
                notification_stage="admission", notification_state="notified"
            ),
        ):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                await self.service.search_participants(self.mock_session, filters)
        with self.assertRaises(ValueError):
            await self.service.search_unregistered(
                self.mock_session,
                9,
                UnregisteredFilterDto(notification_state="notified"),
            )
        self.mock_participants_repo.search_participants_for_admin.assert_not_awaited()
        self.mock_participants_repo.search_unregistered_for_admin.assert_not_awaited()
        self.mock_email_service.notified_user_ids.assert_not_awaited()

    async def test_eligible_lists_only_the_eligible_in_a_round_in_progress(self):
        self.mock_eligibility.eligible_user_ids.return_value = {4, 2}
        self.mock_participants_repo.search_participants_for_admin.return_value = ([], 0)

        await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto(round_id=7, eligible=True)
        )

        self.mock_eligibility.eligible_user_ids.assert_awaited_once_with(
            self.mock_session, 7
        )
        call = self.mock_participants_repo.search_participants_for_admin.await_args
        self.assertEqual(call.kwargs["only_user_ids"], {2, 4})

    async def test_without_eligible_nobody_is_left_out(self):
        self.mock_participants_repo.search_participants_for_admin.return_value = ([], 0)

        await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto(round_id=7)
        )

        self.mock_eligibility.eligible_user_ids.assert_not_awaited()
        call = self.mock_participants_repo.search_participants_for_admin.await_args
        self.assertIsNone(call.kwargs["only_user_ids"])

    async def test_eligible_is_refused_outside_a_round_in_progress(self):
        now = datetime.now(timezone.utc)
        cases = {
            "no round": (None, None),
            "unknown round": (7, None),
            "not started": (
                7,
                MagicMock(
                    promotion_start_at=now + timedelta(days=1),
                    feedback_deadline_at=now + timedelta(days=2),
                ),
            ),
            "over": (
                7,
                MagicMock(
                    promotion_start_at=now - timedelta(days=2),
                    feedback_deadline_at=now - timedelta(days=1),
                ),
            ),
        }
        for label, (round_id, round_entity) in cases.items():
            with self.subTest(label):
                self.mock_rounds_repo.get_by_round_id.return_value = round_entity
                with self.assertRaises(ValueError):
                    await self.service.search_participants(
                        self.mock_session,
                        ParticipantSearchFilterDto(round_id=round_id, eligible=True),
                    )
        self.mock_eligibility.eligible_user_ids.assert_not_awaited()
        self.mock_participants_repo.search_participants_for_admin.assert_not_awaited()

    async def test_needs_exemption_lists_why_and_the_request_waiting(self):
        self.mock_eligibility.needs_exemption.return_value = {
            21: [HistoryFinding(IneligibleReason.MEETINGS_SHORT, 5, 2, 6)],
            22: [HistoryFinding(IneligibleReason.QUIT_AFTER_MATCH, 6)],
        }
        past = [MagicMock(round_id=5), MagicMock(round_id=6)]
        past[0].name, past[1].name = "2025 Spring", "2025 Fall"
        self.mock_rounds_repo.get_all_rounds.return_value = past
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [_make_row(user_id=21, round_id=7), _make_row(user_id=22, round_id=7)],
            2,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                uid: MagicMock(
                    user_id=uid, first_name="U", last_name="X", preferred_name=None
                )
                for uid in (21, 22)
            },
            {},
        )
        self.mock_approvals.pending_exemptions.return_value = {
            22: {
                "request_id": 61,
                "action": "exempt_matching",
                "status": "pending",
                "round": {"round_id": 7, "name": "2026 Spring"},
                "target_id": "7:22",
                "person": {"user_id": 22, "name": "U X"},
                "raised_by": {"user_id": 9, "name": "Ada Ng"},
                "reviewer": {"user_id": 8, "name": "Rae Kim"},
                "reason": "Mentor left",
            }
        }

        result = await self.service.search_participants(
            self.mock_session,
            ParticipantSearchFilterDto(round_id=7, needs_exemption=True),
        )

        call = self.mock_participants_repo.search_participants_for_admin.await_args
        self.assertEqual(call.kwargs["only_user_ids"], {21, 22})
        self.mock_approvals.pending_exemptions.assert_awaited_once_with(
            self.mock_session, 7, [21, 22]
        )
        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(
            [f.model_dump() for f in rows[21].exemption_findings],
            [
                {
                    "reason": "meetings_short",
                    "round_id": 5,
                    "round_name": "2025 Spring",
                    "completed": 2,
                    "required": 6,
                }
            ],
        )
        self.assertIsNone(rows[21].exemption_request)
        self.assertEqual(rows[22].exemption_findings[0].reason, "quit_after_match")
        self.assertEqual(rows[22].exemption_findings[0].round_name, "2025 Fall")
        self.assertEqual(rows[22].exemption_request.reviewer.name, "Rae Kim")

    async def test_needs_exemption_and_eligible_together_are_refused(self):
        with self.assertRaises(ValueError):
            await self.service.search_participants(
                self.mock_session,
                ParticipantSearchFilterDto(
                    round_id=7, eligible=True, needs_exemption=True
                ),
            )
        self.mock_participants_repo.search_participants_for_admin.assert_not_awaited()

    async def test_needs_exemption_is_refused_outside_a_round_in_progress(self):
        self.mock_rounds_repo.get_by_round_id.return_value = None

        for round_id in (None, 7):
            with self.subTest(round_id=round_id):
                with self.assertRaises(ValueError):
                    await self.service.search_participants(
                        self.mock_session,
                        ParticipantSearchFilterDto(
                            round_id=round_id, needs_exemption=True
                        ),
                    )
        self.mock_eligibility.needs_exemption.assert_not_awaited()

    async def test_other_lists_carry_no_exemption_columns(self):
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [_make_row(user_id=21, round_id=7)],
            1,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                21: MagicMock(
                    user_id=21, first_name="U", last_name="X", preferred_name=None
                )
            },
            {},
        )

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto(round_id=7)
        )

        self.assertEqual(result.participant_rows[0].exemption_findings, [])
        self.assertIsNone(result.participant_rows[0].exemption_request)
        self.mock_approvals.pending_exemptions.assert_not_awaited()

    async def test_empty_rows_returns_immediately(self):
        """Returns empty result without calling other repos when no rows found."""
        self.mock_participants_repo.search_participants_for_admin.return_value = ([], 0)

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        self.assertEqual(result.participant_rows, [])
        self.assertEqual(result.total, 0)
        self.mock_users_repo.get_users_and_emails_by_ids.assert_not_awaited()
        self.mock_rounds_repo.get_all_rounds.assert_not_awaited()
        self.mock_training_repo.get_training_by_user_ids_and_categories.assert_not_awaited()

    async def test_account_and_internal_flags_come_from_each_row(self):
        """Each flag lands on its own field; one user per flag so a swapped
        read cannot pass."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(user_id=1, is_blocked=True),
                _make_row(user_id=2, is_deactivated=True),
                _make_row(user_id=3, is_internal=True),
            ],
            3,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                uid: MagicMock(
                    user_id=uid, first_name="U", last_name="X", preferred_name=None
                )
                for uid in (1, 2, 3)
            },
            {},
        )

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        flags = {
            r.user_id: (r.is_blocked, r.is_deactivated, r.is_internal)
            for r in result.participant_rows
        }
        self.assertEqual(
            flags,
            {
                1: (True, False, False),
                2: (False, True, False),
                3: (False, False, True),
            },
        )

    async def test_partner_ids_included_in_user_fetch(self):
        """users repo receives both the participant's and the partner's user_id."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [_make_row(user_id=1, pairs=[_search_pair(5, mentor_id=1, mentee_id=2)])],
            1,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = []

        await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        _, called_ids = self.mock_users_repo.get_users_and_emails_by_ids.call_args[0]
        self.assertEqual(set(called_ids), {1, 2})

    async def test_every_pair_of_a_participant_lands_on_their_one_row(self):
        """Someone who changed mentor mid-round is one row holding both
        pairs, in the repo's pair_id order, each with its own partner, its
        own liveness and its own completed count."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(
                    user_id=1,
                    participant_role=ParticipantRole.MENTEE,
                    pairs=[
                        _search_pair(
                            99,
                            mentor_id=2,
                            mentee_id=1,
                            pair_status=PairStatus.INACTIVE,
                            completed_count=3,
                        ),
                        _search_pair(
                            100,
                            mentor_id=3,
                            mentee_id=1,
                            pair_status=PairStatus.ACTIVE,
                            completed_count=1,
                        ),
                    ],
                ),
            ],
            1,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                uid: MagicMock(
                    user_id=uid,
                    first_name=f"User{uid}",
                    last_name="X",
                    preferred_name=None,
                )
                for uid in (1, 2, 3)
            },
            {},
        )

        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = []

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        (row,) = result.participant_rows
        self.assertEqual(
            [
                (
                    p.pair_id,
                    p.partner.id,
                    p.partner.is_active,
                    p.completed_meeting_count,
                )
                for p in row.pairs
            ],
            [(99, 2, False, 3), (100, 3, True, 1)],
        )
        # The table reads these camelCase keys off the wire.
        wire = result.model_dump(by_alias=True)["participantRows"][0]
        self.assertNotIn("pairId", wire)
        self.assertEqual(
            {k: wire["pairs"][1][k] for k in ("pairId", "completedMeetingCount")},
            {"pairId": 100, "completedMeetingCount": 1},
        )
        self.assertEqual(wire["pairs"][1]["partner"]["id"], 3)

    async def test_tagged_meetings_become_each_pairs_attendance_issues(self):
        """Only meetings carrying a note tag are listed, under their own pair,
        in the repository's order, with the tags the meeting log shows."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(
                    user_id=1,
                    participant_role=ParticipantRole.MENTEE,
                    pairs=[
                        _search_pair(
                            99,
                            mentor_id=2,
                            mentee_id=1,
                            pair_status=PairStatus.INACTIVE,
                        ),
                        _search_pair(100, mentor_id=3, mentee_id=1),
                    ],
                ),
            ],
            1,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                uid: MagicMock(
                    user_id=uid, first_name="U", last_name="X", preferred_name=None
                )
                for uid in (1, 2, 3)
            },
            {},
        )
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {
            99: [
                _make_meeting(
                    meeting_id="a",
                    pair_id=99,
                    start_datetime="2026-08-02T17:00:00+00:00",
                    has_insufficient_duration=True,
                ),
            ],
            100: [
                _make_meeting(
                    meeting_id="b",
                    pair_id=100,
                    start_datetime="2026-08-30T17:00:00+00:00",
                    absent_user_id=1,
                ),
                _make_meeting(
                    meeting_id="c",
                    pair_id=100,
                    start_datetime="2026-09-06T17:00:00+00:00",
                    is_completed=True,
                ),
                _make_meeting(
                    meeting_id="d",
                    pair_id=100,
                    start_datetime="2026-09-13T17:00:00+00:00",
                    is_completed=True,
                    late_user_ids=[3, 1],
                ),
            ],
        }

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        self.mock_meeting_repo.get_meetings_by_pairs.assert_awaited_once_with(
            self.mock_session, [99, 100]
        )
        (row,) = result.participant_rows
        issues = {
            p.pair_id: [(i.start_datetime.day, i.note) for i in p.attendance_issues]
            for p in row.pairs
        }
        self.assertEqual(
            issues,
            {
                99: [(2, [MeetingNoteTag.INSUFFICIENT_DURATION])],
                100: [
                    (30, [MeetingNoteTag.MENTEE_ABSENT]),
                    (13, [MeetingNoteTag.MENTOR_LATE, MeetingNoteTag.MENTEE_LATE]),
                ],
            },
        )
        wire = result.model_dump(by_alias=True, mode="json")["participantRows"][0]
        self.assertEqual(
            wire["pairs"][1]["attendanceIssues"][0],
            {"startDatetime": "2026-08-30T17:00:00Z", "note": ["mentee_absent"]},
        )

    async def test_each_pair_carries_its_earliest_meeting(self):
        """First contact is derived: the earliest meeting the pair has booked
        or held. A pair with no meetings has none."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(
                    user_id=1,
                    participant_role=ParticipantRole.MENTEE,
                    pairs=[
                        _search_pair(100, mentor_id=3, mentee_id=1),
                        _search_pair(101, mentor_id=4, mentee_id=1),
                    ],
                ),
            ],
            1,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                uid: MagicMock(
                    user_id=uid, first_name="U", last_name="X", preferred_name=None
                )
                for uid in (1, 3, 4)
            },
            {},
        )
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {
            100: [
                _make_meeting(
                    meeting_id="later",
                    pair_id=100,
                    start_datetime="2026-09-20T17:00:00+00:00",
                ),
                _make_meeting(
                    meeting_id="first",
                    pair_id=100,
                    start_datetime="2026-09-06T17:00:00+00:00",
                ),
            ],
        }

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        (row,) = result.participant_rows
        first = {p.pair_id: p.first_meeting_at for p in row.pairs}
        self.assertEqual(first[100], isoparse("2026-09-06T17:00:00+00:00"))
        self.assertIsNone(first[101])

    async def test_a_pair_on_two_rows_is_fetched_once_for_the_page(self):
        """Mentor and mentee rows share the pair; the page's meetings come
        from one call with each pair_id once, and both rows show the issue."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(
                    user_id=2,
                    participant_role=ParticipantRole.MENTOR,
                    pairs=[_search_pair(7, mentor_id=2, mentee_id=1)],
                ),
                _make_row(
                    user_id=1,
                    participant_role=ParticipantRole.MENTEE,
                    pairs=[_search_pair(7, mentor_id=2, mentee_id=1)],
                ),
            ],
            2,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                uid: MagicMock(
                    user_id=uid, first_name="U", last_name="X", preferred_name=None
                )
                for uid in (1, 2)
            },
            {},
        )
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {
            7: [_make_meeting(pair_id=7, has_unknown_late=True)],
        }

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        self.mock_meeting_repo.get_meetings_by_pairs.assert_awaited_once_with(
            self.mock_session, [7]
        )
        self.assertEqual(
            [r.pairs[0].attendance_issues[0].note for r in result.participant_rows],
            [[MeetingNoteTag.UNKNOWN_LATE], [MeetingNoteTag.UNKNOWN_LATE]],
        )

    async def test_no_pairs_gives_an_empty_pair_list(self):
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [_make_row(user_id=1, participant_role=ParticipantRole.MENTEE)],
            1,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1, first_name="U", last_name="X", preferred_name=None
                )
            },
            {},
        )
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = []

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        self.assertEqual(result.participant_rows[0].pairs, [])

    async def test_partner_resolves_to_the_other_side_of_the_pair(self):
        """The partner is always the other participant in the pair."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(
                    user_id=1,
                    participant_role=ParticipantRole.MENTOR,
                    pairs=[_search_pair(99, mentor_id=1, mentee_id=2)],
                ),
                _make_row(
                    user_id=2,
                    participant_role=ParticipantRole.MENTEE,
                    pairs=[_search_pair(99, mentor_id=1, mentee_id=2)],
                ),
            ],
            2,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = []

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(rows[1].pairs[0].partner.id, 2)
        self.assertEqual(rows[2].pairs[0].partner.id, 1)

    async def test_onboarding_status_requires_done_training(self):
        """mentor/mentee_onboarding_status returns the raw TrainingStatus from the training record."""
        self.mock_participants_repo.search_participants_for_admin.return_value = (
            [
                _make_row(user_id=1, participant_role=ParticipantRole.MENTEE),
                _make_row(user_id=2, participant_role=ParticipantRole.MENTEE),
                _make_row(user_id=3, participant_role=ParticipantRole.MENTOR),
            ],
            3,
        )
        self.mock_users_repo.get_users_and_emails_by_ids.return_value = (
            {
                1: MagicMock(
                    user_id=1,
                    first_name="Alice",
                    last_name="Doe",
                    preferred_name="Alice Doe",
                ),
                2: MagicMock(
                    user_id=2,
                    first_name="Bob",
                    last_name="Smith",
                    preferred_name="Bob Smith",
                ),
                3: MagicMock(
                    user_id=3,
                    first_name="Carol",
                    last_name="Jones",
                    preferred_name="Carol Jones",
                ),
            },
            {},
        )
        self.mock_rounds_repo.get_all_rounds.return_value = []
        self.mock_training_repo.get_training_by_user_ids_and_categories.return_value = [
            MagicMock(
                user_id=1,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.DONE,
            ),
            MagicMock(
                user_id=2,
                category=TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                status=TrainingStatus.IN_PROGRESS,
            ),
            MagicMock(
                user_id=3,
                category=TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                status=TrainingStatus.TO_DO,
            ),
        ]

        result = await self.service.search_participants(
            self.mock_session, ParticipantSearchFilterDto()
        )

        rows = {r.user_id: r for r in result.participant_rows}
        self.assertEqual(rows[1].mentee_onboarding_status, TrainingStatus.DONE)
        self.assertIsNone(rows[1].mentor_onboarding_status)
        self.assertEqual(rows[2].mentee_onboarding_status, TrainingStatus.IN_PROGRESS)
        self.assertIsNone(rows[2].mentor_onboarding_status)
        self.assertEqual(rows[3].mentor_onboarding_status, TrainingStatus.TO_DO)
        self.assertIsNone(rows[3].mentee_onboarding_status)

    async def test_get_meeting_log_pair_not_found(self):
        """Returns None when pair_id does not exist."""
        self.mock_pairs_repo.get_pair_by_id.return_value = None

        result = await self.service.get_meeting_log(self.mock_session, pair_id=999)

        self.assertIsNone(result)

    async def test_get_meeting_log_v2_notes_and_repository_order(self):
        """v2 (any GOOGLE row present): round_version v2, notes derived from
        row fields, meetings kept in the order the repository returned
        them (start_datetime ascending) -- not re-sorted by created_datetime."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        m1 = _make_meeting(
            meeting_id="m1",
            start_datetime="2024-01-01T10:00:00+00:00",
            created_datetime="2024-01-01T09:00:00+00:00",
            is_completed=False,
            absent_user_id=1,
            late_user_ids=[2],
        )
        m2 = _make_meeting(
            meeting_id="m2",
            start_datetime="2024-02-01T10:00:00+00:00",
            created_datetime="2024-02-01T09:00:00+00:00",
            is_completed=True,
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [m1, m2]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v2")
        self.assertEqual([m.meeting_id for m in result.meetings], ["m1", "m2"])
        self.assertIn(MeetingNoteTag.MENTOR_ABSENT, result.meetings[0].note)
        self.assertIn(MeetingNoteTag.MENTEE_LATE, result.meetings[0].note)
        self.assertEqual(result.meetings[1].note, [])
        self.mock_meeting_repo.get_meetings_by_pair.assert_awaited_once_with(
            self.mock_session, 1
        )

    async def test_get_meeting_log_keeps_repository_start_datetime_order(self):
        """Ordering decision, pinned: this path trusts the repository's
        start_datetime order rather than re-sorting by created_datetime --
        a row created later but scheduled earlier still comes first."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        early_start_late_created = _make_meeting(
            meeting_id="early-start",
            start_datetime="2024-01-01T10:00:00+00:00",
            created_datetime="2024-03-01T09:00:00+00:00",
        )
        late_start_early_created = _make_meeting(
            meeting_id="late-start",
            start_datetime="2024-02-01T10:00:00+00:00",
            created_datetime="2024-01-01T09:00:00+00:00",
        )
        # This is the order the real repository would return them in
        # (start_datetime ascending); if this method instead re-sorted by
        # created_datetime, the result would come out reversed.
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [
            early_start_late_created,
            late_start_early_created,
        ]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(
            [m.meeting_id for m in result.meetings], ["early-start", "late-start"]
        )

    async def test_get_meeting_log_v1_reads_real_is_completed(self):
        """v1 (only MANUAL rows): round_version v1; is_completed is the
        row's real value, not hardcoded True; note is always empty (MANUAL
        rows have no attendance columns)."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        manual = _make_meeting(
            meeting_id="v1-m1",
            source=MeetingSource.MANUAL,
            is_completed=False,
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [manual]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v1")
        self.assertEqual(result.meetings[0].is_completed, False)
        self.assertEqual(result.meetings[0].note, [])

    async def test_get_meeting_log_no_rows_defaults_to_v2(self):
        """A pair with no meeting rows at all defaults to v2 with an empty list."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        self.mock_meeting_repo.get_meetings_by_pair.return_value = []
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v2")
        self.assertEqual(result.meetings, [])

    async def test_get_meeting_log_mixed_pair_returns_both_generations(self):
        """A pair holding both MANUAL and GOOGLE rows shows both -- no
        priority branch hides the manual entries -- and round_version is v2
        because a GOOGLE row is present."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        manual = _make_meeting(
            meeting_id="manual-1",
            source=MeetingSource.MANUAL,
            start_datetime="2024-01-01T10:00:00+00:00",
            created_datetime="2024-01-01T09:00:00+00:00",
            is_completed=True,
        )
        google = _make_meeting(
            meeting_id="google-1",
            source=MeetingSource.GOOGLE,
            start_datetime="2024-02-01T10:00:00+00:00",
            created_datetime="2024-02-01T09:00:00+00:00",
            is_completed=False,
        )
        # Ordered as the repository would return them: start_datetime asc.
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [manual, google]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(result.round_version, "v2")
        self.assertEqual(
            [m.meeting_id for m in result.meetings], ["manual-1", "google-1"]
        )
        self.assertTrue(result.meetings[0].is_completed)
        self.assertFalse(result.meetings[1].is_completed)

    async def test_get_meeting_log_v2_unknown_absent_and_unknown_late(self):
        """Unknown absent/late flags produce UNKNOWN_ABSENT/UNKNOWN_LATE tags."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        row = _make_meeting(
            meeting_id="m1", has_unknown_absent=True, has_unknown_late=True
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [row]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(
            result.meetings[0].note,
            [MeetingNoteTag.UNKNOWN_ABSENT, MeetingNoteTag.UNKNOWN_LATE],
        )

    async def test_get_meeting_log_v2_insufficient_duration(self):
        """has_insufficient_duration produces the INSUFFICIENT_DURATION tag."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        row = _make_meeting(meeting_id="m1", has_insufficient_duration=True)
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [row]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertEqual(
            result.meetings[0].note, [MeetingNoteTag.INSUFFICIENT_DURATION]
        )

    async def test_get_meeting_log_v2_mentee_absent_and_mentor_late(self):
        """Mentee absence and mentor lateness are tagged from the opposite-role fields."""
        pair = MagicMock()
        pair.pair_id = 1
        pair.mentor_id = 1
        pair.mentee_id = 2
        row = _make_meeting(meeting_id="m1", absent_user_id=2, late_user_ids=[1])
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [row]
        self.mock_pairs_repo.get_pair_by_id.return_value = pair

        result = await self.service.get_meeting_log(self.mock_session, pair_id=1)

        self.assertIn(MeetingNoteTag.MENTEE_ABSENT, result.meetings[0].note)
        self.assertIn(MeetingNoteTag.MENTOR_LATE, result.meetings[0].note)

    def test_validate_note_tags_allows_valid_combinations(self):
        """Test that valid note tag combinations do not raise."""
        self.service._validate_note_tags(None)
        self.service._validate_note_tags([])
        self.service._validate_note_tags([
            MeetingNoteTag.MENTOR_LATE,
            MeetingNoteTag.MENTEE_LATE,
        ])

    def test_validate_note_tags_rejects_two_absent_tags(self):
        """Two absent tags in the same note list is invalid."""
        with self.assertRaises(ValueError):
            self.service._validate_note_tags([
                MeetingNoteTag.MENTOR_ABSENT,
                MeetingNoteTag.MENTEE_ABSENT,
            ])

    def test_validate_note_tags_rejects_unknown_late_with_specific_late(self):
        """Unknown and specific late tags are mutually exclusive."""
        with self.assertRaises(ValueError):
            self.service._validate_note_tags([
                MeetingNoteTag.UNKNOWN_LATE,
                MeetingNoteTag.MENTOR_LATE,
            ])

    def test_validate_note_tags_rejects_same_role_absent_and_late(self):
        """The same role cannot be marked as both absent and late."""
        with self.assertRaises(ValueError):
            self.service._validate_note_tags([
                MeetingNoteTag.MENTOR_ABSENT,
                MeetingNoteTag.MENTOR_LATE,
            ])
        with self.assertRaises(ValueError):
            self.service._validate_note_tags([
                MeetingNoteTag.MENTEE_ABSENT,
                MeetingNoteTag.MENTEE_LATE,
            ])

    def test_validate_note_tags_allows_unknown_absent_with_unknown_late(self):
        """unknown_absent and unknown_late don't pin down the same person."""
        self.service._validate_note_tags([
            MeetingNoteTag.UNKNOWN_ABSENT,
            MeetingNoteTag.UNKNOWN_LATE,
        ])

    def test_rejects_completed_meeting_with_an_absent_tag(self):
        """Both `has_unknown_absent` and `absent_user_id` conflict with `is_completed`."""
        for kwargs in (
            {"has_unknown_absent": True},
            {"absent_user_id": 5},
        ):
            with self.assertRaises(ValueError):
                self.service._validate_no_absent_if_completed(
                    _make_meeting(is_completed=True, **kwargs)
                )

    def test_apply_note_tags_maps_every_tag_and_clears(self):
        """Every MeetingNoteTag maps correctly and clears unrelated attributes
        on the meeting row."""
        mentor_id, mentee_id = 1, 2
        cleared = {
            "has_insufficient_duration": False,
            "has_unknown_absent": False,
            "absent_user_id": None,
            "has_unknown_late": False,
            "late_user_ids": [],
        }
        cases = [
            (
                [MeetingNoteTag.INSUFFICIENT_DURATION],
                {**cleared, "has_insufficient_duration": True},
            ),
            ([MeetingNoteTag.UNKNOWN_ABSENT], {**cleared, "has_unknown_absent": True}),
            ([MeetingNoteTag.MENTOR_ABSENT], {**cleared, "absent_user_id": mentor_id}),
            ([MeetingNoteTag.MENTEE_ABSENT], {**cleared, "absent_user_id": mentee_id}),
            ([MeetingNoteTag.UNKNOWN_LATE], {**cleared, "has_unknown_late": True}),
            (
                [MeetingNoteTag.MENTOR_LATE, MeetingNoteTag.MENTEE_LATE],
                {**cleared, "late_user_ids": [mentor_id, mentee_id]},
            ),
            ([], cleared),
        ]
        for note, expected in cases:
            meeting = _make_meeting(
                has_insufficient_duration=True,
                has_unknown_absent=True,
                absent_user_id=999,
                has_unknown_late=True,
                late_user_ids=[999],
            )
            self.service._apply_note_tags(meeting, note, mentor_id, mentee_id)
            for field, value in expected.items():
                self.assertEqual(
                    getattr(meeting, field), value, f"note={note}, field={field}"
                )

    def test_apply_note_tags_reassigns_late_user_ids_not_appends(self):
        """late_user_ids must be a brand-new list object -- ARRAY(Integer) is
        not Mutable-wrapped, so an in-place append would not be detected by
        the unit of work and would silently fail to persist."""
        meeting = _make_meeting(late_user_ids=[999])
        original_list = meeting.late_user_ids

        self.service._apply_note_tags(
            meeting, [MeetingNoteTag.MENTOR_LATE], mentor_id=1, mentee_id=2
        )

        self.assertIsNot(meeting.late_user_ids, original_list)
        self.assertEqual(meeting.late_user_ids, [1])

    async def test_apply_batch_rejects_malformed_requests_before_touching_db(self):
        """Empty request, overlapping IDs, and invalid note combos are rejected before touching the DB."""
        cases = [
            V2MeetingBatchUpdateDto(),
            V2MeetingBatchUpdateDto(
                updates=[V2MeetingUpdateItemDto(meeting_id="m1", is_completed=True)],
                deletes=["m1"],
            ),
            V2MeetingBatchUpdateDto(
                updates=[
                    V2MeetingUpdateItemDto(
                        meeting_id="m1",
                        note=[
                            MeetingNoteTag.MENTOR_ABSENT,
                            MeetingNoteTag.MENTEE_ABSENT,
                        ],
                    )
                ]
            ),
        ]
        for batch in cases:
            with self.assertRaises(ValueError):
                await self.service.apply_v2_meeting_batch(self.mock_session, 1, batch)
        self.mock_pairs_repo.get_pair_by_id.assert_not_awaited()
        self.mock_meeting_repo.get_meetings_by_pair.assert_not_awaited()

    async def test_apply_batch_rejects_manual_only_row(self):
        """A pair with only a manual row still rejects editing it (baseline
        per-row rejection, not just the mixed-pair case below)."""
        pair = _make_pair()
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [
            _make_meeting(meeting_id="manual-1", source=MeetingSource.MANUAL)
        ]

        with self.assertRaises(ConflictError):
            await self.service.apply_v2_meeting_batch(
                self.mock_session, 1, V2MeetingBatchUpdateDto(deletes=["manual-1"])
            )
        self.mock_meeting_repo.delete_meetings.assert_not_awaited()

    async def test_apply_batch_manual_row_conflicts_even_when_pair_also_has_google_rows(
        self,
    ):
        """Per-row check, the headline fix: a manual row is rejected even
        though the same pair also holds an editable google row -- the exact
        case that made a mixed pair permanently uneditable under the old
        per-pair check."""
        pair = _make_pair()
        manual = _make_meeting(meeting_id="manual-1", source=MeetingSource.MANUAL)
        google = _make_meeting(meeting_id="google-1", source=MeetingSource.GOOGLE)
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [manual, google]

        with self.assertRaises(ConflictError):
            await self.service.apply_v2_meeting_batch(
                self.mock_session,
                1,
                V2MeetingBatchUpdateDto(deletes=["manual-1"]),
            )
        self.mock_meeting_repo.delete_meetings.assert_not_awaited()

    async def test_apply_batch_google_row_succeeds_on_same_mixed_pair(self):
        """The same mixed pair's google row can still be edited -- the other
        half of the headline fix."""
        pair = _make_pair()
        manual = _make_meeting(meeting_id="manual-1", source=MeetingSource.MANUAL)
        google = _make_meeting(
            meeting_id="google-1", source=MeetingSource.GOOGLE, is_completed=False
        )
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [
            [manual, google],  # fetched inside apply_v2_meeting_batch
            [manual, google],  # re-fetched by the trailing _build_meeting_log_dto
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1

        result = await self.service.apply_v2_meeting_batch(
            self.mock_session,
            1,
            V2MeetingBatchUpdateDto(
                updates=[
                    V2MeetingUpdateItemDto(meeting_id="google-1", is_completed=True)
                ]
            ),
        )

        self.assertTrue(google.is_completed)
        self.assertEqual(pair.completed_count, 1)
        self.mock_session.commit.assert_awaited_once()
        self.assertEqual(result.round_version, "v2")

    async def test_apply_batch_rejects_partial_update_conflicting_with_existing_row(
        self,
    ):
        """A partial update still catches a conflict via the untouched field."""
        pair = _make_pair()
        cases = [
            _make_meeting(
                meeting_id="google-1", is_completed=False, has_unknown_absent=True
            ),
            _make_meeting(meeting_id="google-1", is_completed=True),
        ]
        updates = [
            V2MeetingUpdateItemDto(meeting_id="google-1", is_completed=True),
            V2MeetingUpdateItemDto(
                meeting_id="google-1", note=[MeetingNoteTag.MENTOR_ABSENT]
            ),
        ]
        for meeting, update_item in zip(cases, updates):
            self.mock_pairs_repo.get_pair_by_id.return_value = pair
            self.mock_meeting_repo.get_meetings_by_pair.return_value = [meeting]

            with self.assertRaises(ValueError):
                await self.service.apply_v2_meeting_batch(
                    self.mock_session,
                    1,
                    V2MeetingBatchUpdateDto(updates=[update_item]),
                )
            self.mock_session.commit.assert_not_awaited()

    async def test_apply_batch_skips_conflict_check_when_fields_untouched(self):
        """The conflict check is skipped unless is_completed or note is modified."""
        pair = _make_pair()
        meeting = _make_meeting(
            meeting_id="google-1", is_completed=True, has_unknown_absent=True
        )
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [
            [meeting],
            [meeting],
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1

        result = await self.service.apply_v2_meeting_batch(
            self.mock_session,
            1,
            V2MeetingBatchUpdateDto(
                updates=[V2MeetingUpdateItemDto(meeting_id="google-1")]
            ),
        )

        self.mock_session.commit.assert_awaited_once()
        self.assertEqual(result.round_version, "v2")

    async def test_apply_batch_rejects_unknown_meeting_id(self):
        """A meeting_id not present among this pair's rows is a client error."""
        pair = _make_pair()
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [
            _make_meeting(meeting_id="m1", is_completed=False)
        ]

        with self.assertRaises(ValueError):
            await self.service.apply_v2_meeting_batch(
                self.mock_session, 1, V2MeetingBatchUpdateDto(deletes=["missing"])
            )

    async def test_apply_batch_mixed_update_and_delete(self):
        """Mixed updates, deletes, and no-op updates correctly recalculate
        completed_count; nothing in this method writes pair.meeting_log."""
        pair = _make_pair(mentor_id=10, mentee_id=20)
        original_meeting_log = copy.deepcopy(pair.meeting_log)
        m1 = _make_meeting(meeting_id="m1", is_completed=False)
        m2 = _make_meeting(meeting_id="m2", is_completed=True)
        m3 = _make_meeting(meeting_id="m3", is_completed=True)
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [
            [m1, m2, m3],  # fetched inside apply_v2_meeting_batch
            [m1, m3],  # re-fetched by the trailing _build_meeting_log_dto (m2 deleted)
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 2

        result = await self.service.apply_v2_meeting_batch(
            self.mock_session,
            1,
            V2MeetingBatchUpdateDto(
                updates=[
                    V2MeetingUpdateItemDto(
                        meeting_id="m1",
                        is_completed=True,
                        note=[MeetingNoteTag.MENTOR_LATE],
                    ),
                    V2MeetingUpdateItemDto(meeting_id="m3"),  # null fields: no-op
                ],
                deletes=["m2"],
            ),
        )

        self.mock_meeting_repo.delete_meetings.assert_awaited_once_with(
            self.mock_session, 1, ["m2"]
        )
        self.assertTrue(m1.is_completed)
        self.assertEqual(m1.late_user_ids, [pair.mentor_id])
        self.assertTrue(m3.is_completed)  # unchanged: both update fields were null
        self.assertIsNone(m3.absent_user_id)  # untouched by the no-op update
        self.assertEqual(pair.completed_count, 2)
        self.mock_session.commit.assert_awaited_once()
        self.assertEqual(result.round_version, "v2")
        # Pin: apply_v2_meeting_batch must never read or write pair.meeting_log.
        self.assertEqual(pair.meeting_log, original_meeting_log)

    async def test_apply_batch_uses_row_lock_and_returns_meeting_log(self):
        """Loads the pair with with_lock=True and returns the pair's current
        meeting log built from rows after the edit."""
        pair = _make_pair()
        m1 = _make_meeting(meeting_id="m1", is_completed=True)
        self.mock_pairs_repo.get_pair_by_id.return_value = pair
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [[m1], []]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 0

        result = await self.service.apply_v2_meeting_batch(
            self.mock_session, 1, V2MeetingBatchUpdateDto(deletes=["m1"])
        )

        self.mock_pairs_repo.get_pair_by_id.assert_awaited_once_with(
            self.mock_session, 1, with_lock=True
        )
        self.mock_meeting_repo.delete_meetings.assert_awaited_once_with(
            self.mock_session, 1, ["m1"]
        )
        self.assertEqual(result.round_version, "v2")
        self.assertEqual(result.meetings, [])


def _feedback_user(user_id, first_name, last_name="Doe", preferred_name=None):
    return MagicMock(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        preferred_name=preferred_name,
    )


def _feedback_participant(role, program_feedback=None, pair_feedback=None):
    return MagicMock(
        participant_role=role,
        program_feedback=program_feedback,
        pair_feedback=pair_feedback,
    )


class TestGetRoundFeedback(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users_repo = MagicMock()
        self.users_repo.get_all_by_ids = AsyncMock()
        self.participants_repo = MagicMock()
        self.participants_repo.get_feedback_owed_in_round = AsyncMock()
        self.rounds_repo = MagicMock()
        # `name` is MagicMock's own constructor argument, so it is set after.
        round_entity = MagicMock(round_id=7)
        round_entity.name = "2026 Fall"
        self.rounds_repo.get_by_round_id = AsyncMock(return_value=round_entity)
        self.session = AsyncMock()
        self.service = MentorshipAdminService(
            users_repository=self.users_repo,
            participants_repository=self.participants_repo,
            rounds_repository=self.rounds_repo,
            training_repository=MagicMock(),
            pairs_repository=MagicMock(),
            mentorship_mapper=MagicMock(),
            logger=MagicMock(),
            mentorship_meeting_repository=MagicMock(),
            application_repository=MagicMock(),
            matching_eligibility_service=MagicMock(),
            mentorship_approval_service=MagicMock(),
            note_repository=MagicMock(),
            approval_service=MagicMock(),
            mentorship_email_service=MagicMock(),
        )

    async def test_maps_sent_and_unsent_rows_and_names_partners(self):
        ann = _feedback_user(21, "Ann", preferred_name="Annie")
        bob = _feedback_user(11, "Bob")
        dan = _feedback_user(23, "Dan")
        self.participants_repo.get_feedback_owed_in_round.return_value = [
            (
                _feedback_participant(
                    ParticipantRole.MENTEE,
                    {
                        "most_valuable_aspects": "career advice",
                        "challenges": "time zones",
                        "program_rating": 4,
                    },
                    [{"partner_id": 11, "rating": 2, "feedback": "late often"}],
                ),
                ann,
            ),
            (
                _feedback_participant(
                    ParticipantRole.MENTOR,
                    {"program_rating": 5},
                    [
                        {"partner_id": 21, "rating": 3, "feedback": None},
                        {"partner_id": 99, "rating": 1},
                    ],
                ),
                bob,
            ),
            (_feedback_participant(ParticipantRole.MENTEE), dan),
        ]
        # 99 no longer resolves to a user.
        self.users_repo.get_all_by_ids.return_value = [ann, bob]

        result = await self.service.get_round_feedback(self.session, 7)

        self.rounds_repo.get_by_round_id.assert_awaited_once_with(self.session, 7)
        self.participants_repo.get_feedback_owed_in_round.assert_awaited_once_with(
            self.session, 7
        )
        self.assertEqual(
            sorted(self.users_repo.get_all_by_ids.await_args.args[1]), [11, 21, 99]
        )
        self.assertEqual(
            (result.round_id, result.round_name, result.owed, result.sent),
            (7, "2026 Fall", 3, 2),
        )

        ann_row, bob_row, dan_row = result.participants
        self.assertEqual(ann_row.user_id, 21)
        self.assertEqual(ann_row.name, "Annie")
        self.assertEqual(ann_row.role, ParticipantRole.MENTEE)
        self.assertTrue(ann_row.has_submitted)
        self.assertEqual(ann_row.most_valuable_aspects, "career advice")
        self.assertEqual(ann_row.challenges, "time zones")
        self.assertEqual(ann_row.program_rating, 4)
        self.assertEqual(
            [
                (f.partner_id, f.partner_name, f.rating, f.feedback)
                for f in ann_row.partner_feedback
            ],
            [(11, "Bob Doe", 2, "late often")],
        )

        self.assertEqual(bob_row.program_rating, 5)
        self.assertIsNone(bob_row.most_valuable_aspects)
        self.assertEqual(
            [
                (f.partner_id, f.partner_name, f.rating, f.feedback)
                for f in bob_row.partner_feedback
            ],
            [(21, "Annie", 3, None), (99, None, 1, None)],
        )

        self.assertFalse(dan_row.has_submitted)
        self.assertIsNone(dan_row.program_rating)
        self.assertEqual(dan_row.partner_feedback, [])

    async def test_unknown_round_raises(self):
        self.rounds_repo.get_by_round_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.get_round_feedback(self.session, 404)

        self.participants_repo.get_feedback_owed_in_round.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
