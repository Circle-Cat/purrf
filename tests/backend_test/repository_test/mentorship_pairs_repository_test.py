import unittest
from datetime import datetime, timezone
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)
from backend.common.mentorship_enums import (
    PairStatus,
    CommunicationMethod,
    MentorActionStatus,
    MenteeActionStatus,
)


class TestMentorShipPairsRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.repo = MentorshipPairsRepository()

        self.now = datetime.now(timezone.utc)

        self.users = [
            UsersEntity(
                first_name="Alice",
                last_name="Admin",
                timezone="Asia/Shanghai",
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                is_active=True,
                updated_timestamp=self.now,
            ),
            UsersEntity(
                first_name="Bob",
                last_name="Smith",
                timezone="America/New_York",
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                is_active=True,
                updated_timestamp=self.now,
            ),
            UsersEntity(
                first_name="Charlie",
                last_name="Inactive",
                timezone="Asia/Shanghai",
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                is_active=False,
                updated_timestamp=self.now,
            ),
        ]

        await self.insert_entities(self.users)

        self.rounds = [
            MentorshipRoundEntity(
                name="2025-spring",
                required_meetings=5,
            ),
            MentorshipRoundEntity(
                name="2025-fall",
                required_meetings=5,
            ),
            MentorshipRoundEntity(
                name="2026-spring",
                required_meetings=5,
            ),
        ]

        await self.insert_entities(self.rounds)

        self.pairs = [
            MentorshipPairsEntity(
                round_id=self.rounds[0].round_id,
                mentor_id=self.users[0].user_id,
                mentee_id=self.users[1].user_id,
                completed_count=5,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="",
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[1].round_id,
                mentor_id=self.users[0].user_id,
                mentee_id=self.users[1].user_id,
                completed_count=2,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="Mentor's area of expertise matches mentee's interests.",
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[0].round_id,
                mentor_id=self.users[2].user_id,
                mentee_id=self.users[0].user_id,
                completed_count=3,
                status=PairStatus.INACTIVE,
                mentor_action_status=MentorActionStatus.PENDING,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="Confirmed partnership for next round",
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[2].round_id,
                mentor_id=self.users[0].user_id,
                mentee_id=self.users[1].user_id,
                completed_count=0,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="",
                meeting_log={
                    "google_meetings": [{"meeting_id": "123"}, {"meeting_id": "456"}]
                },
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[2].round_id,
                mentor_id=self.users[0].user_id,
                mentee_id=self.users[2].user_id,
                completed_count=0,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="",
                meeting_log={"google_meetings": [{"meeting_id": "456"}]},
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[2].round_id,
                mentor_id=self.users[2].user_id,
                mentee_id=self.users[1].user_id,
                completed_count=0,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="",
                meeting_log=None,
            ),
        ]

        await self.insert_entities(self.pairs)

    async def test_get_pairs_by_user_id_existing(self):
        """Test passing a valid user ID returns unique partner IDs."""
        result = await self.repo.get_all_partner_ids(
            self.session, self.users[0].user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIn(self.users[1].user_id, result)
        self.assertIn(self.users[2].user_id, result)

    async def test_get_pairs_by_user_non_existent(self):
        """Test passing a non-existent user ID returns an empty collection."""
        result = await self.repo.get_all_partner_ids(self.session, 9999)

        self.assertIsNotNone(result)
        self.assertEqual(result, [])

    async def test_upsert_pairs_insert(self):
        """Test insert a new mentorship pairs entity correctly."""
        pair = MentorshipPairsEntity(
            round_id=self.rounds[2].round_id,
            mentor_id=self.users[1].user_id,
            mentee_id=self.users[2].user_id,
            completed_count=0,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.PENDING,
            mentee_action_status=MenteeActionStatus.PENDING,
            recommendation_reason="Confirmed partnership for next round.",
        )

        result = await self.repo.upsert_pairs(self.session, pair)

        self.assertIsNotNone(result.pair_id)
        self.assertEqual(result.mentor_id, pair.mentor_id)
        self.assertEqual(result.mentee_id, pair.mentee_id)
        self.assertEqual(result.round_id, pair.round_id)

    async def test_upsert_pairs_update(self):
        """Test update an existing mentorship_pairs entity correctly."""
        pair = MentorshipPairsEntity(
            round_id=self.rounds[2].round_id,
            mentor_id=self.users[1].user_id,
            mentee_id=self.users[2].user_id,
            completed_count=1,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.CONFIRMED,
            mentee_action_status=MenteeActionStatus.CONFIRMED,
            recommendation_reason="Strong alignment in goals.",
            meeting_log={"Date": "Feb 27, 2026", "Time": "8:30 AM - 9:00 AM (CST)"},
        )

        result = await self.repo.upsert_pairs(self.session, pair)

        self.assertEqual(result.mentor_action_status, pair.mentor_action_status)
        self.assertEqual(result.mentee_action_status, pair.mentee_action_status)
        self.assertEqual(result.recommendation_reason, pair.recommendation_reason)
        self.assertEqual(result.meeting_log, pair.meeting_log)

    async def test_get_pairs_with_partner_info_as_mentor(self):
        """Test retrieving pairs where current user is the mentor."""
        # Alice (users[0]) is the mentor for Bob (users[1]) in round[0]
        result = await self.repo.get_pairs_with_partner_info(
            self.session, self.users[0].user_id, self.rounds[0].round_id
        )

        # Alice should have 2 pairs in round 0: one with Bob, one with Charlie
        self.assertEqual(len(result), 2)

        # Verify the specific pair where Alice is Mentor
        pair_with_bob_tuple = next(
            (p, u) for p, u in result if u.user_id == self.users[1].user_id
        )
        pair, partner = pair_with_bob_tuple
        self.assertEqual(pair.mentee_id, self.users[1].user_id)
        self.assertEqual(partner.first_name, "Bob")

    async def test_get_pairs_with_partner_info_as_mentee(self):
        """Test retrieving pairs where current user is the mentee."""
        # Alice (users[0]) is the mentee for Charlie (users[2]) in round[0]
        result = await self.repo.get_pairs_with_partner_info(
            self.session, self.users[0].user_id, self.rounds[0].round_id
        )

        # Verify the specific pair where Alice is Mentee
        pair_with_charlie_tuple = next(
            (p, u) for p, u in result if u.user_id == self.users[2].user_id
        )
        pair, partner = pair_with_charlie_tuple
        self.assertEqual(pair.mentor_id, self.users[2].user_id)
        self.assertEqual(partner.first_name, "Charlie")

    async def test_get_pairs_with_partner_info_round_filter(self):
        """Test that results are correctly filtered by the round_id."""
        # Alice has only 1 pair in round[1] (with Bob)
        result = await self.repo.get_pairs_with_partner_info(
            self.session, self.users[0].user_id, self.rounds[1].round_id
        )

        self.assertEqual(len(result), 1)
        pair, partner = result[0]
        self.assertEqual(pair.round_id, self.rounds[1].round_id)
        self.assertEqual(partner.user_id, self.users[1].user_id)

    async def test_get_pairs_with_partner_info_no_result(self):
        """Test that an empty list is returned if no matches found for the user/round."""
        # Bob (users[1]) has no pairs in round[0] (He is in round[0] pair, but let's use Charlie who has none in round 1)
        result = await self.repo.get_pairs_with_partner_info(
            self.session, self.users[2].user_id, self.rounds[1].round_id
        )

        self.assertEqual(result, [])

    async def test_get_pairs_with_partner_info_status_filter(self):
        """Test that passing a status keeps only pairs in that status."""
        # Alice (users[0]) has two pairs in round[0]: mentor to Bob (ACTIVE)
        # and mentee to Charlie (INACTIVE).
        unfiltered = await self.repo.get_pairs_with_partner_info(
            self.session, self.users[0].user_id, self.rounds[0].round_id
        )
        self.assertEqual(len(unfiltered), 2)

        result = await self.repo.get_pairs_with_partner_info(
            self.session,
            self.users[0].user_id,
            self.rounds[0].round_id,
            status=PairStatus.ACTIVE,
        )

        self.assertEqual(len(result), 1)
        pair, partner = result[0]
        self.assertEqual(pair.status, PairStatus.ACTIVE)
        self.assertEqual(partner.user_id, self.users[1].user_id)

    async def test_get_pairs_with_partner_info_status_filter_no_match(self):
        """Test that a status matching no pair returns an empty list."""
        result = await self.repo.get_pairs_with_partner_info(
            self.session,
            self.users[0].user_id,
            self.rounds[1].round_id,
            status=PairStatus.INACTIVE,
        )

        self.assertEqual(result, [])

    async def test_get_active_pair_by_mentee_and_mentor_picks_the_named_mentor(self):
        """Test that a mentee holding two pairs in one round resolves per mentor."""
        # Bob (users[1]) is the mentee of both Alice (users[0]) and Charlie
        # (users[2]) in round[2]. Filtering on (mentee, round) alone would
        # match both rows; naming the mentor is what makes each lookup
        # single-valued.
        with_alice = await self.repo.get_active_pair_by_mentee_and_mentor(
            session=self.session,
            mentee_id=self.users[1].user_id,
            mentor_id=self.users[0].user_id,
            round_id=self.rounds[2].round_id,
        )
        with_charlie = await self.repo.get_active_pair_by_mentee_and_mentor(
            session=self.session,
            mentee_id=self.users[1].user_id,
            mentor_id=self.users[2].user_id,
            round_id=self.rounds[2].round_id,
        )

        self.assertIsNotNone(with_alice)
        self.assertIsNotNone(with_charlie)
        self.assertNotEqual(with_alice.pair_id, with_charlie.pair_id)
        self.assertEqual(with_alice.mentor_id, self.users[0].user_id)
        self.assertEqual(with_charlie.mentor_id, self.users[2].user_id)

    async def test_get_active_pair_by_mentee_and_mentor_after_mentor_change(self):
        """Test a mid-round mentor change: the ended pair is not returned."""
        # Bob (users[1]) is already Alice's (users[0]) mentee in round[1].
        # Add the pair he holds with the mentor he had before the change,
        # which is left behind as INACTIVE.
        previous_pair = MentorshipPairsEntity(
            round_id=self.rounds[1].round_id,
            mentor_id=self.users[2].user_id,
            mentee_id=self.users[1].user_id,
            completed_count=1,
            status=PairStatus.INACTIVE,
            mentor_action_status=MentorActionStatus.CONFIRMED,
            mentee_action_status=MenteeActionStatus.CONFIRMED,
            recommendation_reason="",
        )
        await self.insert_entities([previous_pair])

        current = await self.repo.get_active_pair_by_mentee_and_mentor(
            session=self.session,
            mentee_id=self.users[1].user_id,
            mentor_id=self.users[0].user_id,
            round_id=self.rounds[1].round_id,
        )
        previous = await self.repo.get_active_pair_by_mentee_and_mentor(
            session=self.session,
            mentee_id=self.users[1].user_id,
            mentor_id=self.users[2].user_id,
            round_id=self.rounds[1].round_id,
        )

        self.assertIsNotNone(current)
        self.assertEqual(current.mentor_id, self.users[0].user_id)
        self.assertEqual(current.status, PairStatus.ACTIVE)
        self.assertIsNone(previous)

    async def test_get_active_pair_by_mentee_and_mentor_skips_inactive(self):
        """Test that an inactive pair is not returned even when it is the only one."""
        # Alice (users[0]) is Charlie's (users[2]) mentee in round[0], INACTIVE.
        result = await self.repo.get_active_pair_by_mentee_and_mentor(
            session=self.session,
            mentee_id=self.users[0].user_id,
            mentor_id=self.users[2].user_id,
            round_id=self.rounds[0].round_id,
        )

        self.assertIsNone(result)

    async def test_get_active_pair_by_mentee_and_mentor_is_side_specific(self):
        """Test that the two user IDs are not interchangeable."""
        # pairs[0]: Alice (users[0]) mentors Bob (users[1]) in round[0]. Asking
        # for it with the sides swapped must not match -- callers use this to
        # require that the current user holds the mentee side.
        pair = self.pairs[0]
        result = await self.repo.get_active_pair_by_mentee_and_mentor(
            session=self.session,
            mentee_id=pair.mentor_id,
            mentor_id=pair.mentee_id,
            round_id=pair.round_id,
        )

        self.assertIsNone(result)

    async def test_get_active_pair_by_mentee_and_mentor_no_pair(self):
        """Test that two users with no pair in the round return None."""
        result = await self.repo.get_active_pair_by_mentee_and_mentor(
            session=self.session,
            mentee_id=self.users[1].user_id,
            mentor_id=self.users[0].user_id,
            round_id=9999,
        )

        self.assertIsNone(result)

    async def test_get_pair_with_partner_by_round_and_users_and_status_as_mentor(self):
        """Test retrieving a active pair and partner when user is the mentor."""
        pair = self.pairs[0]
        result = await self.repo.get_pair_with_partner_by_round_and_users_and_status(
            session=self.session,
            round_id=pair.round_id,
            user_id=pair.mentor_id,
            partner_id=pair.mentee_id,
            status=PairStatus.ACTIVE,
        )

        self.assertIsNotNone(result)
        returned_pair, returned_partner = result
        self.assertEqual(returned_pair.pair_id, pair.pair_id)
        self.assertEqual(returned_partner.user_id, pair.mentee_id)

    async def test_get_pair_with_partner_by_round_and_users_and_status_as_mentee(self):
        """Test retrieving a active pair and partner when user is the mentee (reversed roles)."""
        pair = self.pairs[0]
        result = await self.repo.get_pair_with_partner_by_round_and_users_and_status(
            session=self.session,
            round_id=pair.round_id,
            user_id=pair.mentee_id,
            partner_id=pair.mentor_id,
            status=PairStatus.ACTIVE,
        )

        self.assertIsNotNone(result)
        returned_pair, returned_partner = result
        self.assertEqual(returned_pair.pair_id, pair.pair_id)
        self.assertEqual(returned_partner.user_id, pair.mentor_id)

    async def test_get_pair_with_partner_by_round_and_users_and_status_no_match(self):
        """Test that a non-existent pair returns None."""
        result = await self.repo.get_pair_with_partner_by_round_and_users_and_status(
            session=self.session,
            round_id=9999,
            user_id=9999,
            partner_id=9998,
            status=PairStatus.ACTIVE,
        )

        self.assertIsNone(result)

    async def test_get_pair_by_round_and_users_with_wrong_status(self):
        """Test retrieving a inactive pair and partner."""
        pair = self.pairs[0]
        result = await self.repo.get_pair_with_partner_by_round_and_users_and_status(
            session=self.session,
            round_id=pair.round_id,
            user_id=pair.mentee_id,
            partner_id=pair.mentor_id,
            status=PairStatus.INACTIVE,
        )

        self.assertIsNone(result)

    async def test_get_pair_with_lock_returns_result_as_mentor(self):
        """Test that with_lock=True returns the correct pair and partner when user is the mentor."""
        pair = self.pairs[0]
        result = await self.repo.get_pair_with_partner_by_round_and_users_and_status(
            session=self.session,
            round_id=pair.round_id,
            user_id=pair.mentor_id,
            partner_id=pair.mentee_id,
            status=PairStatus.ACTIVE,
            with_lock=True,
        )

        self.assertIsNotNone(result)
        returned_pair, returned_partner = result
        self.assertEqual(returned_pair.pair_id, pair.pair_id)
        self.assertEqual(returned_partner.user_id, pair.mentee_id)

    async def test_get_pair_with_lock_returns_result_as_mentee(self):
        """Test that with_lock=True returns the correct pair and partner when user is the mentee."""
        pair = self.pairs[0]
        result = await self.repo.get_pair_with_partner_by_round_and_users_and_status(
            session=self.session,
            round_id=pair.round_id,
            user_id=pair.mentee_id,
            partner_id=pair.mentor_id,
            status=PairStatus.ACTIVE,
            with_lock=True,
        )

        self.assertIsNotNone(result)
        returned_pair, returned_partner = result
        self.assertEqual(returned_pair.pair_id, pair.pair_id)
        self.assertEqual(returned_partner.user_id, pair.mentor_id)

    async def test_get_pair_with_lock_returns_none_when_no_match(self):
        """Test that with_lock=True returns None when no matching pair exists."""
        result = await self.repo.get_pair_with_partner_by_round_and_users_and_status(
            session=self.session,
            round_id=9999,
            user_id=9999,
            partner_id=9998,
            status=PairStatus.ACTIVE,
            with_lock=True,
        )

        self.assertIsNone(result)

    async def test_get_pair_with_lock_emits_for_update_sql(self):
        """Test that with_lock=True generates a FOR UPDATE OF clause in the executed SQL."""
        from sqlalchemy import event
        from sqlalchemy.dialects import postgresql

        pair = self.pairs[0]
        captured_stmts = []

        def capture(conn, clauseelement, multiparams, params, execution_options):
            captured_stmts.append(clauseelement)

        event.listen(self.connection.sync_connection, "before_execute", capture)
        try:
            await self.repo.get_pair_with_partner_by_round_and_users_and_status(
                session=self.session,
                round_id=pair.round_id,
                user_id=pair.mentor_id,
                partner_id=pair.mentee_id,
                status=PairStatus.ACTIVE,
                with_lock=True,
            )
        finally:
            event.remove(self.connection.sync_connection, "before_execute", capture)

        pg_dialect = postgresql.dialect()
        compiled_sqls = [
            str(stmt.compile(dialect=pg_dialect))
            for stmt in captured_stmts
            if hasattr(stmt, "compile")
        ]
        self.assertTrue(
            any("FOR UPDATE" in sql for sql in compiled_sqls),
            f"Expected FOR UPDATE in SQL when with_lock=True. Got: {compiled_sqls}",
        )

    async def test_get_pair_without_lock_does_not_emit_for_update_sql(self):
        """Test that with_lock=False (default) does not generate a FOR UPDATE clause."""
        from sqlalchemy import event
        from sqlalchemy.dialects import postgresql

        pair = self.pairs[0]
        captured_stmts = []

        def capture(conn, clauseelement, multiparams, params, execution_options):
            captured_stmts.append(clauseelement)

        event.listen(self.connection.sync_connection, "before_execute", capture)
        try:
            await self.repo.get_pair_with_partner_by_round_and_users_and_status(
                session=self.session,
                round_id=pair.round_id,
                user_id=pair.mentor_id,
                partner_id=pair.mentee_id,
                status=PairStatus.ACTIVE,
            )
        finally:
            event.remove(self.connection.sync_connection, "before_execute", capture)

        pg_dialect = postgresql.dialect()
        compiled_sqls = [
            str(stmt.compile(dialect=pg_dialect))
            for stmt in captured_stmts
            if hasattr(stmt, "compile")
        ]
        self.assertFalse(
            any("FOR UPDATE" in sql for sql in compiled_sqls),
            f"Expected no FOR UPDATE in SQL when with_lock=False. Got: {compiled_sqls}",
        )

    async def test_get_all_active_pairs_by_round(self):
        """Test retrieving all active pairs by round."""
        result = await self.repo.get_active_pairs_by_round(
            session=self.session,
            round_id=self.rounds[0].round_id,
        )

        self.assertEqual(len(result), 1)

        self.assertTrue(all(p.status == PairStatus.ACTIVE for p in result))
        self.assertTrue(all(p.round_id == self.rounds[0].round_id for p in result))

    async def test_get_active_pairs_by_round_no_result(self):
        """Test no pairs returned for non-existing round."""
        result = await self.repo.get_active_pairs_by_round(
            session=self.session,
            round_id=999999,
        )

        self.assertEqual(result, [])

    async def test_upsert_pairs_batch_updates_multiple_pairs(self):
        """Updates a field on multiple existing pairs in a single batch call."""
        self.pairs[0].completed_count = 99
        self.pairs[1].completed_count = 88

        results = await self.repo.upsert_pairs_batch(
            self.session, [self.pairs[0], self.pairs[1]]
        )
        await self.session.commit()

        self.assertEqual(len(results), 2)

        refreshed_0 = await self.session.get(
            MentorshipPairsEntity, self.pairs[0].pair_id
        )
        await self.session.refresh(refreshed_0, ["completed_count"])
        refreshed_1 = await self.session.get(
            MentorshipPairsEntity, self.pairs[1].pair_id
        )
        await self.session.refresh(refreshed_1, ["completed_count"])

        self.assertEqual(refreshed_0.completed_count, 99)
        self.assertEqual(refreshed_1.completed_count, 88)

    async def test_upsert_pairs_batch_single_entity(self):
        """Updates a single entity when the batch contains only one element."""
        self.pairs[2].completed_count = 77

        results = await self.repo.upsert_pairs_batch(self.session, [self.pairs[2]])
        await self.session.commit()

        self.assertEqual(len(results), 1)

        refreshed = await self.session.get(MentorshipPairsEntity, self.pairs[2].pair_id)
        await self.session.refresh(refreshed, ["completed_count"])
        self.assertEqual(refreshed.completed_count, 77)

    async def test_upsert_pairs_batch_empty_list(self):
        """Returns an empty list when called with an empty entity list."""
        results = await self.repo.upsert_pairs_batch(self.session, [])
        self.assertEqual(results, [])

    async def test_upsert_pairs_batch_returns_list_of_entities(self):
        """Return value contains MentorshipPairsEntity instances with correct pair IDs."""
        results = await self.repo.upsert_pairs_batch(self.session, [self.pairs[0]])

        self.assertIsInstance(results, list)
        self.assertIsInstance(results[0], MentorshipPairsEntity)
        self.assertEqual(results[0].pair_id, self.pairs[0].pair_id)

    async def test_get_pair_stats(self):
        """Should only include active pairs and deduplicate matched_participants across pairs in the same round."""
        result = await self.repo.get_pair_stats(self.session)

        self.assertIsInstance(result, dict)

        # rounds[0]: pairs[2] is INACTIVE and excluded; only pairs[0] counts
        self.assertEqual(result[self.rounds[0].round_id]["active_pairs"], 1)
        self.assertEqual(result[self.rounds[0].round_id]["matched_participants"], 2)
        self.assertEqual(result[self.rounds[0].round_id]["total_completed_meetings"], 5)

        # rounds[2]: users[0] appears as mentor in pairs[3] and pairs[4] → deduped to 1
        self.assertEqual(result[self.rounds[2].round_id]["active_pairs"], 3)
        self.assertEqual(result[self.rounds[2].round_id]["matched_participants"], 4)
        self.assertEqual(result[self.rounds[2].round_id]["total_completed_meetings"], 0)

    async def test_get_pair_stats_empty(self):
        """Returns an empty dict when there are no active pairs for a round."""
        empty_round = MentorshipRoundEntity(name="empty-round", required_meetings=5)
        await self.insert_entities([empty_round])

        result = await self.repo.get_pair_stats(self.session)

        self.assertNotIn(empty_round.round_id, result)

    async def test_get_pair_by_id_existing(self):
        """Test that an existing pair_id returns the matching pair."""
        pair = self.pairs[0]
        result = await self.repo.get_pair_by_id(self.session, pair.pair_id)

        self.assertIsNotNone(result)
        self.assertEqual(result.pair_id, pair.pair_id)

    async def test_get_pair_by_id_non_existent(self):
        """Test that a non-existent pair_id returns None."""
        result = await self.repo.get_pair_by_id(self.session, 999)

        self.assertIsNone(result)

    async def test_get_pair_by_id_with_lock_returns_same_row(self):
        """Test that with_lock=True returns the same pair."""
        pair = self.pairs[0]
        result = await self.repo.get_pair_by_id(
            self.session, pair.pair_id, with_lock=True
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.pair_id, pair.pair_id)


if __name__ == "__main__":
    unittest.main()
