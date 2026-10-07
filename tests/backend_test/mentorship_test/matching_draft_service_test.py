"""Taking a run's result for editing and saving the draft."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import ConflictError
from backend.mentorship.matching_contract import Candidate, MenteeResult
from backend.mentorship.matching_draft_service import MatchingDraftService


def _no_approvals():
    """An approval service with nothing pending and nothing closed."""
    approvals = MagicMock()
    approvals.get_pending_for_target = AsyncMock(return_value=None)
    approvals.get_latest_closed_for_target = AsyncMock(return_value=None)
    return approvals


def _change(mentee_id, mentor_id, reason=""):
    return SimpleNamespace(
        mentee_id=mentee_id, mentor_id=mentor_id, recommendation_reason=reason
    )


def _user(user_id, first_name, last_name):
    return SimpleNamespace(
        user_id=user_id, first_name=first_name, last_name=last_name, preferred_name=None
    )


class MatchingDraftServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = MagicMock()
        self.storage.current_run_id.return_value = "r7-x-y"
        self.storage.read_run_result.return_value = SimpleNamespace(status="succeeded")
        self.storage.read_all_results.return_value = {
            "1": MenteeResult(
                mentor_id="10",
                score=80,
                match_type="hungarian",
                recommendation_reason="Matched on skills",
                candidates=[Candidate(mentor_id="11", score=70)],
            ),
            "2": MenteeResult(candidates=[Candidate(mentor_id="12", score=40)]),
        }
        self.storage.take_edit_lock.return_value = True
        self.storage.edit_lock.return_value = ("9", 1800)
        self.storage.read_draft.return_value = {"1": object()}
        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(return_value=[_user(9, "Ann", "Lee")])
        self.approvals = _no_approvals()
        self.service = MatchingDraftService(
            matching_storage=self.storage,
            users_repository=self.users,
            approval_service=self.approvals,
            logger=MagicMock(),
        )
        self.session = MagicMock()

    async def test_taking_the_lock_says_who_and_until_when(self):
        lock = await self.service.take_lock(self.session, 7, 9)

        self.storage.take_edit_lock.assert_called_once_with("r7-x-y", "9")
        self.assertEqual(lock["user_id"], "9")
        self.assertEqual(lock["name"], "Ann Lee")
        self.assertIn("expires_at", lock)

    async def test_a_lock_another_admin_holds_is_refused_by_name(self):
        self.storage.take_edit_lock.return_value = False
        self.storage.edit_lock.return_value = ("5", 900)
        self.users.get_all_by_ids.return_value = [_user(5, "Bo", "Ng")]

        with self.assertRaises(ConflictError) as caught:
            await self.service.take_lock(self.session, 7, 9)

        self.assertEqual(str(caught.exception), "Being edited by Bo Ng.")

    async def test_there_is_nothing_to_edit_without_a_succeeded_run(self):
        for reported in (None, SimpleNamespace(status="failed")):
            with self.subTest(reported=reported):
                self.storage.read_run_result.return_value = reported
                with self.assertRaises(ValueError):
                    await self.service.take_lock(self.session, 7, 9)
        self.storage.current_run_id.return_value = None
        with self.assertRaises(ValueError):
            self.service.save_changes(7, 9, [])

    def test_releasing_gives_back_only_this_admin_s_lock(self):
        self.service.release_lock(7, 9)

        self.storage.release_edit_lock.assert_called_once_with("r7-x-y", "9")

    def test_saving_writes_changes_drops_reverts_and_releases_the_lock(self):
        result = self.service.save_changes(
            7,
            9,
            [
                _change("1", "11", "Moved to a candidate"),
                _change("2", "12", "Given her candidate"),
            ],
        )

        entries, removed = self.storage.write_draft.call_args.args[1:]
        self.assertEqual(sorted(entries), ["1", "2"])
        self.assertEqual(entries["1"].mentor_id, "11")
        self.assertEqual(entries["1"].edited_by, "9")
        self.assertEqual(removed, [])
        self.storage.release_edit_lock.assert_called_once_with("r7-x-y", "9")
        self.assertEqual(result, {"draft_count": 1})

    def test_a_change_back_to_the_matcher_s_choice_leaves_the_draft(self):
        self.service.save_changes(7, 9, [_change("1", "10", "Matched on skills")])

        entries, removed = self.storage.write_draft.call_args.args[1:]
        self.assertEqual((entries, removed), ({}, ["1"]))

    def test_a_mentor_who_is_not_a_candidate_is_refused(self):
        for change in (_change("1", "12"), _change("2", "10"), _change("99", None)):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.service.save_changes(7, 9, [change])
        self.storage.write_draft.assert_not_called()

    def test_saving_without_the_lock_is_refused(self):
        for held in (None, ("5", 900)):
            with self.subTest(held=held):
                self.storage.edit_lock.return_value = held
                with self.assertRaises(ConflictError):
                    self.service.save_changes(7, 9, [_change("1", None)])
        self.storage.write_draft.assert_not_called()

    async def test_a_result_waiting_for_approval_to_publish_cannot_be_taken(self):
        self.approvals.get_pending_for_target.return_value = MagicMock()

        with self.assertRaises(ConflictError) as caught:
            await self.service.take_lock(self.session, 7, 9)

        self.assertEqual(str(caught.exception), "Waiting for approval to publish.")
        self.assertEqual(
            self.approvals.get_pending_for_target.await_args.args[1:],
            ("publish_matching", "r7-x-y"),
        )
        self.storage.take_edit_lock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
