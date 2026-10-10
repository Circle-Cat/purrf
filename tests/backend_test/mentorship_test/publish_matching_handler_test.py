"""Publishing a matching result through an approval: when it may be asked
for, what has to still hold when it is approved, and what approving writes."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.common.exceptions import ConflictError
from backend.common.mentorship_enums import (
    ApprovalStatus,
    MenteeActionStatus,
    MentorActionStatus,
    PairStatus,
    ParticipantNoteTag,
)
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.mentorship.matching_contract import (
    SKILL_KEYS,
    Candidate,
    MenteeResult,
    PersonRecord,
)
from backend.mentorship.matching_draft import DraftEntry
from backend.mentorship.matching_eligibility import HistoryFinding, IneligibleReason
from backend.mentorship.matching_eligibility_service import Assessment
from backend.mentorship.publish_matching_handler import PublishMatchingHandler

RUN = "r7-x-y"
ROUND = 7
RAISER = 90
REVIEWER = 80

_NO_SKILLS = {key: False for key in SKILL_KEYS}


def _mentor(user_id, slots):
    return PersonRecord(
        role="mentor",
        user_id=user_id,
        display_name=f"Mentor {user_id}",
        skills=_NO_SKILLS,
        max_partners=slots,
    )


def _matched(mentor_id, reason, score=70):
    return MenteeResult(
        mentor_id=mentor_id,
        match_type="hungarian",
        score=score,
        recommendation_reason=reason,
        candidates=[Candidate(mentor_id="13", score=40)],
    )


def _unmatched():
    return MenteeResult(candidates=[Candidate(mentor_id="13", score=30)])


def _person(user_id, first, last, *, status=ApprovalStatus.SIGNED_UP, cap=1):
    user = SimpleNamespace(
        user_id=user_id,
        first_name=first,
        last_name=last,
        preferred_name=None,
        is_active=True,
        is_blocked=False,
    )
    participant = SimpleNamespace(approval_status=status, max_partners=cap)
    return user, participant


def _pair(pair_id, mentor_id, mentee_id, status=PairStatus.ACTIVE):
    return SimpleNamespace(
        pair_id=pair_id, mentor_id=mentor_id, mentee_id=mentee_id, status=status
    )


def _request(reason="Reviewed every pair"):
    row = ApprovalRequestEntity(
        action="publish_matching",
        target_type="matching_run",
        target_id=RUN,
        payload={"round_id": ROUND},
        reason=reason,
        raised_by=RAISER,
        reviewer_id=REVIEWER,
    )
    row.request_id = 501
    return row


class PublishMatchingHandlerTestBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Mentee 21 goes to mentor 11, 22 to 12, nobody is found for 23, and
        # mentor 13 is given nobody. Mentor 11 takes two, the others one.
        self.results = {
            "21": _matched("11", "Both work in data"),
            "22": _matched("12", "Same timezone"),
            "23": _unmatched(),
        }
        self.draft = {}
        self.mentors = {
            "11": _mentor("11", 2),
            "12": _mentor("12", 1),
            "13": _mentor("13", 1),
        }
        self.storage = MagicMock()
        self.storage.current_run_id.return_value = RUN
        self.storage.read_run_result.return_value = SimpleNamespace(status="succeeded")
        self.storage.edit_lock.return_value = None
        self.storage.read_all_results.side_effect = lambda run_id: self.results
        self.storage.read_draft.side_effect = lambda run_id: self.draft
        self.storage.read_all_people.side_effect = lambda run_id, role: (
            self.mentors if role == "mentor" else {}
        )

        self.people = {
            11: _person(11, "Mia", "Ortiz", cap=2),
            12: _person(12, "Noor", "Haddad"),
            13: _person(13, "Owen", "Price"),
            21: _person(21, "Ann", "Lee"),
            22: _person(22, "Bo", "Ng"),
            23: _person(23, "Cy", "Fox"),
        }
        # Names come from the users table, which outlives a registration.
        self.names = {
            **{uid: (u.first_name, u.last_name) for uid, (u, _) in self.people.items()},
            RAISER: ("Ada", "Raiser"),
            REVIEWER: ("Rae", "Reviewer"),
        }
        self.participants = MagicMock()
        self.participants.list_round_registrations = AsyncMock(
            side_effect=lambda session, round_id: list(self.people.values())
        )

        self.existing = []
        self.pairs = MagicMock()
        self.pairs.list_pairs_by_round = AsyncMock(
            side_effect=lambda session, round_id: list(self.existing)
        )
        self.pairs.get_active_pairs_by_round = AsyncMock(
            side_effect=lambda session, round_id: [
                p for p in self.existing if p.status == PairStatus.ACTIVE
            ]
        )
        self.pairs.upsert_pairs_batch = AsyncMock(side_effect=self._insert_pairs)

        self.notes = MagicMock()
        self.notes.create = AsyncMock()
        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(
            side_effect=lambda session, ids: [
                SimpleNamespace(
                    user_id=uid,
                    first_name=first,
                    last_name=last,
                    preferred_name=None,
                )
                for uid, (first, last) in self.names.items()
                if uid in ids
            ]
        )
        self.rounds = MagicMock()
        self.rounds.get_by_round_id = AsyncMock(
            return_value=SimpleNamespace(name="Spring 2026")
        )
        self.rounds.get_all_rounds = AsyncMock(
            return_value=[
                SimpleNamespace(round_id=ROUND, name="Spring 2026"),
                SimpleNamespace(round_id=5, name="Fall 2025"),
            ]
        )
        self.eligibility = MagicMock()
        self.eligibility.assess = AsyncMock(return_value={})
        self.session = AsyncMock()
        self.handler = PublishMatchingHandler(
            matching_storage=self.storage,
            pairs_repository=self.pairs,
            participants_repository=self.participants,
            note_repository=self.notes,
            users_repository=self.users,
            rounds_repository=self.rounds,
            logger=MagicMock(),
            matching_eligibility_service=self.eligibility,
        )

    async def _insert_pairs(self, session, entities):
        for offset, entity in enumerate(entities):
            entity.pair_id = 700 + offset
        return entities


class TestRaise(PublishMatchingHandlerTestBase):
    async def _check(self, payload=None):
        await self.handler.check_raise(
            self.session,
            raised_by=RAISER,
            target_id=RUN,
            payload={"round_id": ROUND} if payload is None else payload,
        )

    async def test_a_finished_clean_current_run_may_be_put_up(self):
        await self._check()

    async def test_the_round_must_be_named(self):
        with self.assertRaises(ValueError):
            await self._check(payload={})

    async def test_a_run_the_round_has_moved_past_is_refused(self):
        self.storage.current_run_id.return_value = "r7-newer"

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertIn("no longer the round's latest", str(caught.exception))

    async def test_a_run_that_failed_or_is_still_going_is_refused(self):
        for reported in (SimpleNamespace(status="failed"), None):
            with self.subTest(reported=reported):
                self.storage.read_run_result.return_value = reported
                with self.assertRaises(ConflictError):
                    await self._check()

    async def test_a_result_being_edited_is_refused(self):
        self.storage.edit_lock.return_value = ("9", 600)

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertIn("being edited", str(caught.exception))

    async def test_a_result_with_problems_is_refused(self):
        # Mentor 12 takes one mentee; the draft gives him a second.
        self.draft = {
            "23": DraftEntry(
                mentor_id="12",
                recommendation_reason="Asked for him",
                edited_by="9",
                edited_at="2026-10-07T08:00:00+00:00",
            )
        }

        with self.assertRaises(ConflictError) as caught:
            await self._check()
        self.assertIn("problems", str(caught.exception))


class TestProblemsAtApproval(PublishMatchingHandlerTestBase):
    async def _problems(self):
        return await self.handler.problems_at_approval(self.session, _request())

    async def test_nothing_in_the_way(self):
        self.assertEqual(await self._problems(), [])

    async def test_a_run_no_longer_current_is_the_only_problem_reported(self):
        self.storage.current_run_id.return_value = "r7-newer"
        self.people[21][0].is_blocked = True

        problems = await self._problems()

        self.assertEqual(len(problems), 1)
        self.assertIn("no longer the round's latest", problems[0])

    async def test_a_result_that_now_has_problems_is_refused(self):
        self.mentors["11"] = _mentor("11", 1)
        self.results["23"] = _matched("11", "Another for Mia")

        problems = await self._problems()

        self.assertEqual(
            problems, ["The result has problems to fix before it can be published."]
        )

    async def test_someone_blocked_deactivated_or_gone_since_is_named(self):
        self.people[21][0].is_blocked = True
        self.people[12][0].is_active = False
        self.people[22] = _person(22, "Bo", "Ng", status=ApprovalStatus.REJECTED)
        del self.people[11]

        problems = await self._problems()

        self.assertIn("Ann Lee is blocked.", problems)
        self.assertIn("Noor Haddad's account is deactivated.", problems)
        self.assertIn("Bo Ng has left this round.", problems)
        self.assertIn("Mia Ortiz is not registered for this round.", problems)

    async def test_someone_withdrawn_since_has_left_this_round(self):
        self.people[22] = _person(22, "Bo", "Ng", status=ApprovalStatus.WITHDRAWN)

        problems = await self._problems()

        self.assertIn("Bo Ng has left this round.", problems)

    async def test_people_the_result_leaves_unpaired_are_not_checked(self):
        self.people[23][0].is_blocked = True
        self.people[13][0].is_active = False

        self.assertEqual(await self._problems(), [])

    async def test_a_mark_since_the_run_refuses_naming_who_and_why(self):
        self.eligibility.assess.return_value = {
            21: Assessment(
                reasons=[IneligibleReason.RED_FLAG],
                findings=[HistoryFinding(IneligibleReason.RED_FLAG, ROUND)],
            ),
            11: Assessment(
                reasons=[IneligibleReason.NO_SHOW],
                findings=[HistoryFinding(IneligibleReason.NO_SHOW, 5)],
            ),
            # Unfinished onboarding does not stop a publish.
            22: Assessment(reasons=[IneligibleReason.TRAINING_NOT_DONE], findings=[]),
        }

        problems = await self._problems()

        self.assertEqual(
            problems,
            [
                "Mia Ortiz was marked a no show in Fall 2025.",
                "Ann Lee has a red flag in this round.",
            ],
        )
        self.eligibility.assess.assert_awaited_once_with(self.session, ROUND)

    async def test_only_people_in_the_new_pairs_are_checked(self):
        # 13 is a mentor the result gives nobody; 14 and 31 are an existing
        # pair; 23 is a mentee left unmatched. All carry a red flag.
        self.existing = [_pair(600, 14, 31)]
        flagged = Assessment(
            reasons=[IneligibleReason.RED_FLAG],
            findings=[HistoryFinding(IneligibleReason.RED_FLAG, ROUND)],
        )
        self.eligibility.assess.return_value = {
            13: flagged,
            14: flagged,
            31: flagged,
            23: flagged,
        }

        self.assertEqual(await self._problems(), [])

    async def test_what_is_already_said_above_is_not_said_twice(self):
        self.people[21][0].is_blocked = True
        self.eligibility.assess.return_value = {
            21: Assessment(reasons=[IneligibleReason.BLOCKED], findings=[]),
        }

        self.assertEqual(await self._problems(), ["Ann Lee is blocked."])

    async def test_eligibility_is_not_read_once_the_run_is_refused(self):
        self.storage.current_run_id.return_value = "r7-newer"

        await self._problems()

        self.eligibility.assess.assert_not_awaited()

    async def test_a_mentee_already_in_an_active_pair_is_refused(self):
        self.existing = [_pair(600, 13, 21)]

        problems = await self._problems()

        self.assertIn("Ann Lee already has a pair in this round.", problems)

    async def test_a_pair_that_existed_before_in_this_round_is_refused(self):
        self.existing = [_pair(600, 12, 22, status=PairStatus.INACTIVE)]

        problems = await self._problems()

        self.assertIn("Bo Ng and Noor Haddad were already paired this round.", problems)

    async def test_a_mentor_s_existing_pairs_count_against_his_cap(self):
        # Mia takes two and already has two: the third from this run is over.
        self.existing = [_pair(600, 11, 31), _pair(601, 11, 32)]

        problems = await self._problems()

        self.assertIn("Mia Ortiz would have 3 mentees but takes 2.", problems)


class TestExecute(PublishMatchingHandlerTestBase):
    async def _execute(self):
        await self.handler.execute(self.session, _request(), actor_id=REVIEWER)

    def _status(self, user_id):
        return self.people[user_id][1].approval_status

    def _notes(self):
        return {
            call.kwargs["user_id"]: call.kwargs
            for call in self.notes.create.await_args_list
        }

    async def test_every_matched_mentee_gets_an_active_pair_to_confirm(self):
        self.draft = {
            "22": DraftEntry(
                mentor_id="13",
                recommendation_reason="Owen has done this switch",
                edited_by="9",
                edited_at="2026-10-07T08:00:00+00:00",
            )
        }

        await self._execute()

        written = self.pairs.upsert_pairs_batch.await_args.args[1]
        self.assertEqual(
            [
                (
                    p.round_id,
                    p.mentor_id,
                    p.mentee_id,
                    p.completed_count,
                    p.status,
                    p.mentor_action_status,
                    p.mentee_action_status,
                    p.recommendation_reason,
                )
                for p in written
            ],
            [
                (
                    7,
                    11,
                    21,
                    0,
                    PairStatus.ACTIVE,
                    MentorActionStatus.PENDING,
                    MenteeActionStatus.PENDING,
                    "Both work in data",
                ),
                (
                    7,
                    13,
                    22,
                    0,
                    PairStatus.ACTIVE,
                    MentorActionStatus.PENDING,
                    MenteeActionStatus.PENDING,
                    "Owen has done this switch",
                ),
            ],
        )

    async def test_the_paired_become_matched_and_the_rest_of_the_run_un_matched(self):
        await self._execute()

        for user_id in (11, 12, 21, 22):
            self.assertIs(self._status(user_id), ApprovalStatus.MATCHED, user_id)
        for user_id in (13, 23):
            self.assertIs(self._status(user_id), ApprovalStatus.UN_MATCHED, user_id)

    async def test_someone_already_in_an_active_pair_keeps_their_status(self):
        # Owen is given nobody by this run but already mentors someone.
        self.existing = [_pair(600, 13, 31)]
        self.people[13] = _person(13, "Owen", "Price", status=ApprovalStatus.MATCHED)

        await self._execute()

        self.assertIs(self._status(13), ApprovalStatus.MATCHED)
        self.assertNotIn(13, self._notes())

    async def test_someone_who_left_the_round_stays_left(self):
        self.people[23] = _person(23, "Cy", "Fox", status=ApprovalStatus.REJECTED)

        await self._execute()

        self.assertIs(self._status(23), ApprovalStatus.REJECTED)
        self.assertNotIn(23, self._notes())

    async def test_a_status_already_right_is_not_noted_again(self):
        self.people[23] = _person(23, "Cy", "Fox", status=ApprovalStatus.UN_MATCHED)

        await self._execute()

        self.assertNotIn(23, self._notes())

    async def test_a_new_pair_for_someone_already_matched_is_noted(self):
        # Mia already mentors 31 and is matched; this run gives her Ann too.
        self.existing = [_pair(600, 11, 31)]
        self.people[11] = _person(
            11, "Mia", "Ortiz", status=ApprovalStatus.MATCHED, cap=2
        )
        self.results["22"] = _unmatched()

        await self._execute()

        self.assertIs(self._status(11), ApprovalStatus.MATCHED)
        mia = [
            call.kwargs
            for call in self.notes.create.await_args_list
            if call.kwargs["user_id"] == 11
        ]
        self.assertEqual(len(mia), 1)
        self.assertEqual(mia[0]["pair_id"], 700)
        self.assertIs(mia[0]["tag"], ParticipantNoteTag.STATUS_CHANGE)
        self.assertEqual(mia[0]["author_user_id"], REVIEWER)
        self.assertEqual(
            mia[0]["body"],
            "Paired with Ann Lee when the matching result was published. "
            "Raised by Ada Raiser, reason: Reviewed every pair; approved by "
            "Rae Reviewer.",
        )

    async def test_each_change_is_noted_by_the_approver_with_who_asked_and_why(self):
        await self._execute()

        notes = self._notes()
        self.assertEqual(sorted(notes), [11, 12, 13, 21, 22, 23])
        ann = notes[21]
        self.assertEqual(ann["round_id"], 7)
        self.assertEqual(ann["author_user_id"], REVIEWER)
        self.assertIs(ann["tag"], ParticipantNoteTag.STATUS_CHANGE)
        self.assertEqual(ann["request_id"], 501)
        self.assertEqual(ann["pair_id"], 700)
        self.assertIn("signed_up -> matched", ann["body"])
        self.assertIn("Raised by Ada Raiser", ann["body"])
        self.assertIn("Reviewed every pair", ann["body"])
        self.assertIn("approved by Rae Reviewer", ann["body"])
        self.assertIsNone(notes[11]["pair_id"])
        self.assertIn("signed_up -> un_matched", notes[23]["body"])


class TestAroundTheRequest(PublishMatchingHandlerTestBase):
    def test_events_are_recorded_against_the_round(self):
        self.assertEqual(self.handler.subject_id(_request()), 7)

    async def test_events_snapshot_the_round_s_name(self):
        details = await self.handler.event_details(self.session, _request())

        self.assertEqual(details, {"roundName": "Spring 2026"})

    async def test_once_published_the_round_stops_pointing_at_the_run(self):
        await self.handler.after_commit(_request())

        self.storage.clear_round_pointer.assert_called_once_with(7, RUN)


if __name__ == "__main__":
    unittest.main()
