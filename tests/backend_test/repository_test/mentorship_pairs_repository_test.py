import unittest
import uuid
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
    UserTimezone,
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
                timezone=UserTimezone.ASIA_SHANGHAI,
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="alice@example.com",
                is_active=True,
                updated_timestamp=self.now,
                subject_identifier=str(uuid.uuid4()),
            ),
            UsersEntity(
                first_name="Bob",
                last_name="Smith",
                timezone=UserTimezone.AMERICA_NEW_YORK,
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="bob@example.com",
                is_active=True,
                updated_timestamp=self.now,
                subject_identifier=str(uuid.uuid4()),
            ),
            UsersEntity(
                first_name="Charlie",
                last_name="Inactive",
                timezone=UserTimezone.ASIA_SHANGHAI,
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="charlie@example.com",
                is_active=False,
                updated_timestamp=self.now,
                subject_identifier=str(uuid.uuid4()),
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

    async def test_get_partner_ids_by_user_and_round(self):
        """Test passing both user_id and round_id returns the unique partner IDs."""
        result = await self.repo.get_partner_ids_by_user_and_round(
            self.session, self.users[0].user_id, self.rounds[0].round_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIn(self.users[1].user_id, result)
        self.assertIn(self.users[2].user_id, result)

    async def test_get_partner_ids_by_user_and_round_by_user_non_existent(self):
        """Test passing non-existent user ID and valid rounds ID returns an empty collection."""
        result = await self.repo.get_partner_ids_by_user_and_round(
            self.session, 9999, self.rounds[0].round_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result, [])

    async def test_get_partner_ids_by_user_and_round_by_round_non_existent(self):
        """Test passing valid user ID and non-existent rounds ID returns an empty collection."""
        result = await self.repo.get_partner_ids_by_user_and_round(
            self.session, self.users[0].user_id, 9999
        )

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

    async def test_remove_meeting_from_log_success(self):
        """Test successfully removing a meeting from meeting_log using index 3."""
        pair = self.pairs[3]

        result = await self.repo.remove_meeting_from_log(
            self.session,
            user_id=pair.mentor_id,
            meeting_id="123",
        )
        await self.session.commit()

        self.assertTrue(result)

        # Verify that the meeting was actually removed from the database
        refreshed = await self.session.get(MentorshipPairsEntity, pair.pair_id)
        # Ensure we get the latest data from the database
        await self.session.refresh(refreshed, ["meeting_log"])

        meeting_ids = [
            m["meeting_id"] for m in refreshed.meeting_log["google_meetings"]
        ]
        self.assertNotIn("123", meeting_ids)
        self.assertIn("456", meeting_ids)

    async def test_remove_meeting_from_log_not_found(self):
        """Test that removing a non-existent meeting_id returns False."""
        # Use the pair at index 4 which only contains meeting_id "456"
        pair = self.pairs[4]

        result = await self.repo.remove_meeting_from_log(
            self.session,
            user_id=pair.mentor_id,
            meeting_id="999",
        )
        self.assertFalse(result)

    async def test_remove_meeting_from_log_invalid_user(self):
        """Test that removing a meeting with an unauthorized user_id returns False."""

        result = await self.repo.remove_meeting_from_log(
            self.session,
            user_id=9999,
            meeting_id="123",
        )
        self.assertFalse(result)

    async def test_remove_meeting_from_log_null_log(self):
        """Test removing a meeting when the log itself is None."""
        pair = self.pairs[5]

        result = await self.repo.remove_meeting_from_log(
            self.session,
            user_id=pair.mentor_id,
            meeting_id="123",
        )
        self.assertFalse(result)

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

    async def test_clear_google_meetings_invalid_input(self):
        """Test invalid input raises ValueError."""
        with self.assertRaises(ValueError):
            await self.repo.clear_google_meetings_by_user_pair_and_round(
                self.session,
                current_user_id=None,
                partner_id=1,
                round_id=1,
            )

    async def test_clear_google_meetings_by_user_pair_and_round_success(self):
        """Test clearing google meetings for a matched user pair in a given round."""
        pair = self.pairs[3]

        result = await self.repo.clear_google_meetings_by_user_pair_and_round(
            self.session,
            current_user_id=pair.mentor_id,
            partner_id=pair.mentee_id,
            round_id=pair.round_id,
        )
        await self.session.commit()

        self.assertTrue(result)

        refreshed = await self.session.get(MentorshipPairsEntity, pair.pair_id)
        await self.session.refresh(refreshed, ["meeting_log"])

        self.assertEqual(refreshed.meeting_log["google_meetings"], [])

    async def test_clear_google_meetings_by_user_pair_and_round_reverse_order(self):
        """Test clearing google meetings works regardless of user order."""
        pair = self.pairs[4]

        result = await self.repo.clear_google_meetings_by_user_pair_and_round(
            self.session,
            current_user_id=pair.mentee_id,
            partner_id=pair.mentor_id,
            round_id=pair.round_id,
        )
        await self.session.commit()

        self.assertTrue(result)

        refreshed = await self.session.get(MentorshipPairsEntity, pair.pair_id)
        await self.session.refresh(refreshed, ["meeting_log"])

        self.assertEqual(refreshed.meeting_log["google_meetings"], [])

    async def test_clear_google_meetings_by_user_pair_and_round_not_found(self):
        """Test clearing google meetings returns False when no pair matches."""
        pair = self.pairs[3]

        result = await self.repo.clear_google_meetings_by_user_pair_and_round(
            self.session,
            current_user_id=pair.mentor_id,
            partner_id=9999,
            round_id=pair.round_id,
        )

        self.assertFalse(result)

    async def test_clear_google_meetings_by_user_pair_and_round_null_log(self):
        """Test clearing google meetings initializes google_meetings when meeting_log is None."""
        pair = self.pairs[5]

        result = await self.repo.clear_google_meetings_by_user_pair_and_round(
            self.session,
            current_user_id=pair.mentor_id,
            partner_id=pair.mentee_id,
            round_id=pair.round_id,
        )
        await self.session.commit()

        self.assertTrue(result)

        refreshed = await self.session.get(MentorshipPairsEntity, pair.pair_id)
        await self.session.refresh(refreshed, ["meeting_log"])

        self.assertEqual(refreshed.meeting_log, {"google_meetings": []})

    async def test_append_google_meeting_to_existing_list(self):
        """Appending to an existing list preserves old entries and adds the new one."""
        pair = self.pairs[3]  # has google_meetings: [123, 456]
        new_entry = {
            "meeting_id": "789",
            "meet_link": "https://meet.google.com/new",
            "is_completed": False,
        }

        await self.repo.append_google_meeting(
            session=self.session,
            pair_id=pair.pair_id,
            meeting_entry=new_entry,
        )
        await self.session.commit()

        refreshed = await self.session.get(MentorshipPairsEntity, pair.pair_id)
        await self.session.refresh(refreshed, ["meeting_log"])

        meetings = refreshed.meeting_log["google_meetings"]
        self.assertEqual(len(meetings), 3)
        meeting_ids = [m["meeting_id"] for m in meetings]
        self.assertIn("123", meeting_ids)
        self.assertIn("456", meeting_ids)
        self.assertIn("789", meeting_ids)

    async def test_append_google_meeting_to_null_log(self):
        """Appending when meeting_log is NULL creates the structure from scratch."""
        pair = self.pairs[5]  # meeting_log=None
        new_entry = {
            "meeting_id": "first",
            "meet_link": "https://meet.google.com/first",
            "is_completed": False,
        }

        await self.repo.append_google_meeting(
            session=self.session,
            pair_id=pair.pair_id,
            meeting_entry=new_entry,
        )
        await self.session.commit()

        refreshed = await self.session.get(MentorshipPairsEntity, pair.pair_id)
        await self.session.refresh(refreshed, ["meeting_log"])

        self.assertIsNotNone(refreshed.meeting_log)
        meetings = refreshed.meeting_log["google_meetings"]
        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0]["meeting_id"], "first")

    async def test_append_google_meeting_preserves_other_log_keys(self):
        """Appending when meeting_log has no google_meetings key creates it without losing other keys."""
        pair = MentorshipPairsEntity(
            round_id=self.rounds[0].round_id,
            mentor_id=self.users[1].user_id,
            mentee_id=self.users[2].user_id,
            completed_count=0,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.CONFIRMED,
            mentee_action_status=MenteeActionStatus.CONFIRMED,
            recommendation_reason="",
            meeting_log={"other_key": "value"},
        )
        created = await self.repo.upsert_pairs(self.session, pair)

        new_entry = {
            "meeting_id": "only",
            "meet_link": "https://meet.google.com/only",
            "is_completed": False,
        }
        await self.repo.append_google_meeting(
            session=self.session,
            pair_id=created.pair_id,
            meeting_entry=new_entry,
        )
        await self.session.commit()

        refreshed = await self.session.get(MentorshipPairsEntity, created.pair_id)
        await self.session.refresh(refreshed, ["meeting_log"])

        meetings = refreshed.meeting_log["google_meetings"]
        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0]["meeting_id"], "only")
        self.assertEqual(refreshed.meeting_log["other_key"], "value")


if __name__ == "__main__":
    unittest.main()
