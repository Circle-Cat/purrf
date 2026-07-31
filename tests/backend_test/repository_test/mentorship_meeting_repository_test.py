import unittest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError, NoResultFound
from backend.common.mentorship_enums import (
    CommunicationMethod,
    MeetingSource,
    MenteeActionStatus,
    MentorActionStatus,
    PairStatus,
)
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.mentorship_meeting_repository import (
    MentorshipMeetingRepository,
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
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestMentorshipMeetingRepository(BaseRepositoryTestLib):
    async def _seed_pair(self, completed_count: int = 0) -> MentorshipPairsEntity:
        """Create a round, a mentor, a mentee, and one pair.

        Returns:
            MentorshipPairsEntity: The seeded pair.
        """
        round_ = MentorshipRoundEntity(name="round", required_meetings=5)
        mentor = _make_user()
        mentee = _make_user()
        await self.insert_entities([round_, mentor, mentee])
        pair = MentorshipPairsEntity(
            round_id=round_.round_id,
            mentor_id=mentor.user_id,
            mentee_id=mentee.user_id,
            completed_count=completed_count,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.CONFIRMED,
            mentee_action_status=MenteeActionStatus.CONFIRMED,
            recommendation_reason="",
        )
        await self.insert_entities([pair])
        return pair

    def _manual_meeting(self, pair_id: int, **overrides) -> MentorshipMeetingEntity:
        start = overrides.pop(
            "start_datetime", datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        )
        default_end = start + timedelta(minutes=30) if start is not None else None
        end = overrides.pop("end_datetime", default_end)
        kwargs = dict(
            meeting_id=str(uuid.uuid4()),
            pair_id=pair_id,
            source=MeetingSource.MANUAL,
            start_datetime=start,
            end_datetime=end,
            is_completed=False,
            created_datetime=datetime.now(timezone.utc),
        )
        kwargs.update(overrides)
        return MentorshipMeetingEntity(**kwargs)

    def _google_meeting(self, pair_id: int, **overrides) -> MentorshipMeetingEntity:
        start = overrides.pop(
            "start_datetime", datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        )
        end = overrides.pop("end_datetime", start + timedelta(minutes=30))
        kwargs = dict(
            meeting_id=str(uuid.uuid4()),
            pair_id=pair_id,
            source=MeetingSource.GOOGLE,
            start_datetime=start,
            end_datetime=end,
            is_completed=False,
            created_datetime=datetime.now(timezone.utc),
            google_meeting_code="abc-defg-hij",
        )
        kwargs.update(overrides)
        return MentorshipMeetingEntity(**kwargs)

    def _legacy_meeting(self, pair_id: int, **overrides) -> MentorshipMeetingEntity:
        kwargs = dict(
            meeting_id=f"legacy-{pair_id}-{uuid.uuid4()}",
            pair_id=pair_id,
            source=MeetingSource.LEGACY,
            start_datetime=None,
            end_datetime=None,
            is_completed=True,
            created_datetime=datetime.now(timezone.utc),
        )
        kwargs.update(overrides)
        return MentorshipMeetingEntity(**kwargs)

    # --- get_meetings_by_pair ---

    async def test_get_meetings_by_pair_orders_oldest_first_and_scopes_to_pair(self):
        pair = await self._seed_pair()
        other_pair = await self._seed_pair()
        m_late = self._manual_meeting(
            pair.pair_id,
            start_datetime=datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 1, 3, 10, 30, tzinfo=timezone.utc),
        )
        m_early = self._manual_meeting(
            pair.pair_id,
            start_datetime=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc),
        )
        m_other_pair = self._manual_meeting(other_pair.pair_id)
        await self.insert_entities([m_late, m_early, m_other_pair])
        repo = MentorshipMeetingRepository()

        result = await repo.get_meetings_by_pair(self.session, pair.pair_id)

        self.assertEqual(
            [m.meeting_id for m in result], [m_early.meeting_id, m_late.meeting_id]
        )

    async def test_get_meetings_by_pair_breaks_tied_start_by_created_datetime(self):
        """Two rows sharing a start_datetime must come back in
        created_datetime order, not arbitrary order -- proving the tiebreaker
        is load-bearing rather than accidental."""
        pair = await self._seed_pair()
        shared_start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
        shared_end = shared_start + timedelta(minutes=30)
        # meeting_id values are chosen (not random) so that ascending
        # meeting_id order is the REVERSE of the expected created_datetime
        # order. That way, if the created_datetime tiebreaker were ever
        # removed from the query, the fallback ordering by meeting_id would
        # produce the wrong result deterministically, instead of coincidentally
        # matching about half the time.
        m_created_later = self._manual_meeting(
            pair.pair_id,
            meeting_id="a-tie-created-later",
            start_datetime=shared_start,
            end_datetime=shared_end,
            created_datetime=datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
        )
        m_created_earlier = self._manual_meeting(
            pair.pair_id,
            meeting_id="b-tie-created-earlier",
            start_datetime=shared_start,
            end_datetime=shared_end,
            created_datetime=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        )
        # Inserted in the "wrong" order on purpose: only the created_datetime
        # tiebreaker in the query, not insertion order, should decide.
        await self.insert_entities([m_created_later, m_created_earlier])
        repo = MentorshipMeetingRepository()

        result = await repo.get_meetings_by_pair(self.session, pair.pair_id)

        self.assertEqual(
            [m.meeting_id for m in result],
            [m_created_earlier.meeting_id, m_created_later.meeting_id],
        )

    async def test_get_meetings_by_pair_excludes_legacy_by_default(self):
        pair = await self._seed_pair()
        manual = self._manual_meeting(pair.pair_id)
        legacy = self._legacy_meeting(pair.pair_id)
        await self.insert_entities([manual, legacy])
        repo = MentorshipMeetingRepository()

        result = await repo.get_meetings_by_pair(self.session, pair.pair_id)

        self.assertEqual([m.meeting_id for m in result], [manual.meeting_id])

    async def test_get_meetings_by_pair_includes_legacy_when_opted_in(self):
        pair = await self._seed_pair()
        manual = self._manual_meeting(pair.pair_id)
        legacy = self._legacy_meeting(pair.pair_id)
        await self.insert_entities([manual, legacy])
        repo = MentorshipMeetingRepository()

        result = await repo.get_meetings_by_pair(
            self.session, pair.pair_id, include_legacy=True
        )

        self.assertEqual(
            [m.meeting_id for m in result], [manual.meeting_id, legacy.meeting_id]
        )

    async def test_get_meetings_by_pair_null_starts_sort_last_with_legacy(self):
        """With include_legacy=True, NULL-start LEGACY rows must sort after
        every timed row, not arbitrarily."""
        pair = await self._seed_pair()
        m_early = self._manual_meeting(
            pair.pair_id,
            start_datetime=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc),
        )
        m_late = self._manual_meeting(
            pair.pair_id,
            start_datetime=datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 1, 3, 10, 30, tzinfo=timezone.utc),
        )
        # meeting_id values are chosen (not random) so that ascending
        # meeting_id order among the two NULL-start rows is the REVERSE of
        # the expected created_datetime order -- see the analogous comment
        # in test_get_meetings_by_pair_breaks_tied_start_by_created_datetime.
        legacy_a = self._legacy_meeting(
            pair.pair_id,
            meeting_id="b-legacy-a-first-created",
            created_datetime=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        )
        legacy_b = self._legacy_meeting(
            pair.pair_id,
            meeting_id="a-legacy-b-second-created",
            created_datetime=datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
        )
        # Inserted out of expected order on purpose.
        await self.insert_entities([legacy_b, m_late, legacy_a, m_early])
        repo = MentorshipMeetingRepository()

        result = await repo.get_meetings_by_pair(
            self.session, pair.pair_id, include_legacy=True
        )

        self.assertEqual(
            [m.meeting_id for m in result],
            [
                m_early.meeting_id,
                m_late.meeting_id,
                legacy_a.meeting_id,
                legacy_b.meeting_id,
            ],
        )

    # --- get_meetings_by_pairs ---

    async def test_get_meetings_by_pairs_empty_input_returns_empty_dict_no_query(self):
        repo = MentorshipMeetingRepository()

        result = await repo.get_meetings_by_pairs(self.session, [])

        self.assertEqual(result, {})

    async def test_get_meetings_by_pairs_groups_orders_and_omits_pairs_with_no_rows(
        self,
    ):
        pair_a = await self._seed_pair()
        pair_b = await self._seed_pair()
        pair_c_no_meetings = await self._seed_pair()
        a_late = self._manual_meeting(
            pair_a.pair_id,
            start_datetime=datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 1, 3, 10, 30, tzinfo=timezone.utc),
        )
        a_early = self._manual_meeting(
            pair_a.pair_id,
            start_datetime=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc),
        )
        b_only = self._manual_meeting(pair_b.pair_id)
        a_legacy = self._legacy_meeting(pair_a.pair_id)
        await self.insert_entities([a_late, a_early, b_only, a_legacy])
        repo = MentorshipMeetingRepository()

        result = await repo.get_meetings_by_pairs(
            self.session, [pair_a.pair_id, pair_b.pair_id, pair_c_no_meetings.pair_id]
        )

        self.assertEqual(
            [m.meeting_id for m in result[pair_a.pair_id]],
            [a_early.meeting_id, a_late.meeting_id],
        )
        self.assertEqual(
            [m.meeting_id for m in result[pair_b.pair_id]], [b_only.meeting_id]
        )
        self.assertNotIn(pair_c_no_meetings.pair_id, result)

    async def test_get_meetings_by_pairs_includes_legacy_when_opted_in(self):
        pair = await self._seed_pair()
        manual = self._manual_meeting(pair.pair_id)
        legacy = self._legacy_meeting(pair.pair_id)
        await self.insert_entities([manual, legacy])
        repo = MentorshipMeetingRepository()

        result = await repo.get_meetings_by_pairs(
            self.session, [pair.pair_id], include_legacy=True
        )

        self.assertEqual(
            [m.meeting_id for m in result[pair.pair_id]],
            [manual.meeting_id, legacy.meeting_id],
        )

    async def test_get_meetings_by_pairs_does_not_query_per_pair(self):
        """One query for the whole batch, not one per pair id."""
        pair_a = await self._seed_pair()
        pair_b = await self._seed_pair()
        await self.insert_entities(
            [self._manual_meeting(pair_a.pair_id), self._manual_meeting(pair_b.pair_id)]
        )
        repo = MentorshipMeetingRepository()
        statements = []
        original_execute = self.session.execute

        async def _counting_execute(stmt, *args, **kwargs):
            statements.append(stmt)
            return await original_execute(stmt, *args, **kwargs)

        self.session.execute = _counting_execute
        try:
            await repo.get_meetings_by_pairs(
                self.session, [pair_a.pair_id, pair_b.pair_id]
            )
        finally:
            self.session.execute = original_execute

        self.assertEqual(len(statements), 1)

    # --- get_pending_google_meetings_by_pairs ---

    async def test_get_pending_google_meetings_by_pairs_filters_correctly(self):
        pair = await self._seed_pair()
        pending_google = self._google_meeting(pair.pair_id, is_completed=False)
        completed_google = self._google_meeting(pair.pair_id, is_completed=True)
        pending_manual = self._manual_meeting(pair.pair_id, is_completed=False)
        pending_legacy = self._legacy_meeting(pair.pair_id, is_completed=False)
        google_no_code = self._google_meeting(
            pair.pair_id, is_completed=False, google_meeting_code=None
        )
        await self.insert_entities([
            pending_google,
            completed_google,
            pending_manual,
            pending_legacy,
            google_no_code,
        ])
        repo = MentorshipMeetingRepository()

        result = await repo.get_pending_google_meetings_by_pairs(
            self.session, [pair.pair_id]
        )

        self.assertEqual([m.meeting_id for m in result], [pending_google.meeting_id])

    async def test_get_pending_google_meetings_by_pairs_empty_input_returns_empty_list(
        self,
    ):
        repo = MentorshipMeetingRepository()

        result = await repo.get_pending_google_meetings_by_pairs(self.session, [])

        self.assertEqual(result, [])

    # --- get_meeting_by_google_meeting_code ---

    async def test_get_meeting_by_google_meeting_code_hit(self):
        pair = await self._seed_pair()
        meeting = self._google_meeting(pair.pair_id, google_meeting_code="code-123")
        await self.insert_entities([meeting])
        repo = MentorshipMeetingRepository()

        result = await repo.get_meeting_by_google_meeting_code(self.session, "code-123")

        self.assertIsNotNone(result)
        self.assertEqual(result.meeting_id, meeting.meeting_id)

    async def test_get_meeting_by_google_meeting_code_miss(self):
        repo = MentorshipMeetingRepository()

        result = await repo.get_meeting_by_google_meeting_code(
            self.session, "does-not-exist"
        )

        self.assertIsNone(result)

    # --- insert_meeting ---

    async def test_insert_meeting_manual_without_google_columns_succeeds(self):
        pair = await self._seed_pair()
        meeting = self._manual_meeting(pair.pair_id)
        repo = MentorshipMeetingRepository()

        result = await repo.insert_meeting(self.session, meeting)

        self.assertEqual(result.meeting_id, meeting.meeting_id)
        fetched = await self.session.get(MentorshipMeetingEntity, meeting.meeting_id)
        self.assertIsNotNone(fetched)

    async def test_insert_meeting_manual_with_google_field_violates_check(self):
        pair = await self._seed_pair()
        meeting = self._manual_meeting(
            pair.pair_id, google_meeting_code="should-not-be-here"
        )
        repo = MentorshipMeetingRepository()

        with self.assertRaises(IntegrityError):
            await repo.insert_meeting(self.session, meeting)

    async def test_insert_meeting_end_before_start_violates_check(self):
        pair = await self._seed_pair()
        start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        meeting = self._manual_meeting(
            pair.pair_id, start_datetime=start, end_datetime=start
        )
        repo = MentorshipMeetingRepository()

        with self.assertRaises(IntegrityError):
            await repo.insert_meeting(self.session, meeting)

    async def test_insert_meeting_manual_without_times_violates_check(self):
        pair = await self._seed_pair()
        meeting = self._manual_meeting(
            pair.pair_id, start_datetime=None, end_datetime=None
        )
        repo = MentorshipMeetingRepository()

        with self.assertRaises(IntegrityError):
            await repo.insert_meeting(self.session, meeting)

    async def test_insert_meeting_legacy_without_times_succeeds(self):
        pair = await self._seed_pair()
        meeting = self._legacy_meeting(pair.pair_id)
        repo = MentorshipMeetingRepository()

        result = await repo.insert_meeting(self.session, meeting)

        self.assertEqual(result.meeting_id, meeting.meeting_id)

    # --- delete_meetings ---

    async def test_delete_meetings_only_deletes_specified_pair_and_ids(self):
        pair = await self._seed_pair()
        other_pair = await self._seed_pair()
        m1 = self._manual_meeting(pair.pair_id)
        m2 = self._manual_meeting(pair.pair_id)
        m3_other_pair = self._manual_meeting(other_pair.pair_id)
        await self.insert_entities([m1, m2, m3_other_pair])
        repo = MentorshipMeetingRepository()

        deleted_count = await repo.delete_meetings(
            self.session, pair.pair_id, [m1.meeting_id, m3_other_pair.meeting_id]
        )

        self.assertEqual(deleted_count, 1)
        remaining = await repo.get_meetings_by_pair(self.session, pair.pair_id)
        self.assertEqual([m.meeting_id for m in remaining], [m2.meeting_id])
        other_remaining = await repo.get_meetings_by_pair(
            self.session, other_pair.pair_id
        )
        self.assertEqual(
            [m.meeting_id for m in other_remaining], [m3_other_pair.meeting_id]
        )

    async def test_delete_meetings_empty_ids_returns_zero(self):
        pair = await self._seed_pair()
        repo = MentorshipMeetingRepository()

        deleted_count = await repo.delete_meetings(self.session, pair.pair_id, [])

        self.assertEqual(deleted_count, 0)

    # --- recalculate_completed_count ---

    async def test_recalculate_completed_count_mixed_sources_and_statuses(self):
        pair = await self._seed_pair(completed_count=999)
        completed_manual = self._manual_meeting(pair.pair_id, is_completed=True)
        completed_google = self._google_meeting(pair.pair_id, is_completed=True)
        pending_manual = self._manual_meeting(pair.pair_id, is_completed=False)
        await self.insert_entities([completed_manual, completed_google, pending_manual])
        repo = MentorshipMeetingRepository()

        new_count = await repo.recalculate_completed_count(self.session, pair.pair_id)

        self.assertEqual(new_count, 2)
        refreshed = await self.session.get(MentorshipPairsEntity, pair.pair_id)
        await self.session.refresh(refreshed, ["completed_count"])
        self.assertEqual(refreshed.completed_count, 2)

    async def test_recalculate_completed_count_includes_legacy_rows(self):
        pair = await self._seed_pair(completed_count=0)
        legacy_rows = [
            self._legacy_meeting(pair.pair_id, is_completed=True) for _ in range(3)
        ]
        await self.insert_entities(legacy_rows)
        repo = MentorshipMeetingRepository()

        new_count = await repo.recalculate_completed_count(self.session, pair.pair_id)

        self.assertEqual(new_count, 3)
        refreshed = await self.session.get(MentorshipPairsEntity, pair.pair_id)
        await self.session.refresh(refreshed, ["completed_count"])
        self.assertEqual(refreshed.completed_count, 3)

    async def test_recalculate_completed_count_nonexistent_pair_raises(self):
        """Pins the documented (surprising) behavior: there is no existence
        check, so an unknown pair_id raises NoResultFound rather than
        returning None or 0."""
        repo = MentorshipMeetingRepository()

        with self.assertRaises(NoResultFound):
            await repo.recalculate_completed_count(self.session, -1)


if __name__ == "__main__":
    unittest.main()
