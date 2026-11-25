"""Hand-written ledger corrections, and the two things they are used for.

At launch this is how the balance carried in from the previous year gets into
purrf, and how leave already taken this year gets booked -- as negative rows,
since a request cannot be dated in the past. Both are the same entry type; the
note is what tells them apart to a reader.
"""

import datetime
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.leave_enums import (
    LEAVE_LEDGER_SUBJECT,
    LeaveEntryType,
    LeaveEvent,
)
from backend.leave.leave_adjustment_service import LeaveAdjustmentService

TODAY = datetime.date(2026, 8, 21)
LEDGER_ID = 4242


class LeaveAdjustmentServiceTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.ledger_repository = MagicMock()

        def _assign_id(_session, entries):
            entries[0].leave_ledger_id = LEDGER_ID

        self.ledger_repository.add_entries = AsyncMock(side_effect=_assign_id)
        self.ledger_repository.balance = AsyncMock(return_value=Decimal("40.00"))
        self.users_repository = MagicMock()
        self.users_repository.get_user_by_user_id = AsyncMock(return_value=MagicMock())
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.service = LeaveAdjustmentService(
            logger=self.logger,
            leave_ledger_repository=self.ledger_repository,
            users_repository=self.users_repository,
        )
        clock = patch("backend.leave.leave_adjustment_service.business_today")
        self.business_today = clock.start()
        self.business_today.return_value = TODAY
        self.addCleanup(clock.stop)
        self.record_event = AsyncMock()
        recorder = patch(
            "backend.leave.leave_adjustment_service.record_event",
            new=self.record_event,
        )
        recorder.start()
        self.addCleanup(recorder.stop)

    async def _adjust(self, **overrides):
        payload = {
            "user_id": 7,
            "hours": Decimal("40.00"),
            "effective_date": datetime.date(2025, 12, 31),
            "note": "Carried over from Lattice",
            "author_user_id": 2,
        }
        payload.update(overrides)
        return await self.service.adjust(self.session, **payload)

    def _written(self):
        return self.ledger_repository.add_entries.await_args.args[1][0]

    async def test_a_correction_is_written_as_a_manual_adjustment(self):
        await self._adjust()

        entry = self._written()
        self.assertEqual(entry.entry_type, LeaveEntryType.MANUAL_ADJUSTMENT)
        self.assertEqual(entry.user_id, 7)
        self.assertEqual(entry.hours, Decimal("40.00"))
        self.assertEqual(entry.effective_date, datetime.date(2025, 12, 31))
        self.assertEqual(entry.note, "Carried over from Lattice")

    async def test_the_admin_who_did_it_is_recorded(self):
        """created_by being NULL means "a job wrote this". A correction is a
        person's decision and has to stay distinguishable from that."""
        await self._adjust(author_user_id=2)

        self.assertEqual(self._written().created_by, 2)

    async def test_negative_hours_are_allowed(self):
        """This is how leave already taken this year is booked: a request
        cannot be dated in the past, so it arrives as a negative correction."""
        await self._adjust(hours=Decimal("-8.00"), note="Leave taken 2026-05-06")

        self.assertEqual(self._written().hours, Decimal("-8.00"))

    async def test_the_new_balance_is_read_back_after_writing(self):
        """The admin dialog shows it, and a second non-zero figure is the only
        signal that stops the same carry-over being keyed in twice."""
        self.ledger_repository.balance.return_value = Decimal("32.00")

        result = await self._adjust()

        self.assertEqual(result.balance_hours, "32.00")

    async def test_the_write_is_committed(self):
        """The session does not commit on its own: without this the request
        answers 200 and stores nothing, raising nothing."""
        await self._adjust()

        self.session.commit.assert_awaited_once()

    async def test_hours_reach_the_caller_as_a_fixed_two_decimal_string(self):
        """Never a float. jsonable_encoder turns Decimal into float, and 78.46
        comes back as 78.45999999999999."""
        result = await self._adjust(hours=Decimal("-8"))

        self.assertEqual(result.hours, "-8.00")

    async def test_a_blank_note_is_refused(self):
        """The note is the only record of why a number was changed by hand."""
        with self.assertRaises(ValueError):
            await self._adjust(note="   ")

        self.ledger_repository.add_entries.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_a_zero_correction_is_refused(self):
        """It would add a row that changes nothing, which reads later as a
        correction that was made and then lost."""
        with self.assertRaises(ValueError):
            await self._adjust(hours=Decimal("0.00"))

        self.ledger_repository.add_entries.assert_not_awaited()

    async def test_a_date_in_the_future_is_refused(self):
        """A balance is a plain sum with no date filter, so a future-dated row
        counts from the moment it is written -- it would show up as hours the
        person cannot explain and does not have yet."""
        with self.assertRaises(ValueError):
            await self._adjust(effective_date=datetime.date(2026, 8, 22))

        self.ledger_repository.add_entries.assert_not_awaited()

    async def test_today_is_not_in_the_future(self):
        await self._adjust(effective_date=TODAY)

        self.assertEqual(self._written().effective_date, TODAY)

    async def test_the_date_is_judged_against_the_beijing_day(self):
        """The server runs on UTC. Between 00:00 and 08:00 Beijing the two
        disagree, and judging by the UTC date would refuse a correction dated
        today."""
        await self._adjust(effective_date=TODAY)

        self.business_today.assert_called()

    async def test_a_correction_for_an_unknown_person_is_refused(self):
        """The foreign key would raise anyway, as a 500 with a Postgres message
        in it. This is the same refusal with a sentence an admin can read."""
        self.users_repository.get_user_by_user_id.return_value = None

        with self.assertRaises(ValueError):
            await self._adjust(user_id=999)

        self.ledger_repository.add_entries.assert_not_awaited()

    # -- telling the person whose balance it is ----------------------------

    async def test_the_person_is_told_what_changed_and_where_it_left_them(self):
        """The row is the subject, the admin the actor; the details are what
        the email and the bell say, so a late delivery still reads true."""
        await self._adjust(
            hours=Decimal("-16.00"),
            effective_date=datetime.date(2026, 3, 2),
            note="  Leave taken before launch  ",
        )

        self.record_event.assert_awaited_once()
        kwargs = self.record_event.await_args.kwargs
        self.assertEqual(kwargs["event_type"], LeaveEvent.BALANCE_ADJUSTED)
        self.assertEqual(kwargs["subject_type"], LEAVE_LEDGER_SUBJECT)
        self.assertEqual(kwargs["subject_id"], LEDGER_ID)
        self.assertEqual(kwargs["actor_id"], 2)
        self.assertEqual(
            kwargs["details"],
            {
                "hours": "-16.00",
                "effectiveDate": "2026-03-02",
                "note": "Leave taken before launch",
                "balanceHours": "40.00",
            },
        )

    async def test_an_opening_balance_is_announced_like_any_correction(self):
        """Opening balances arrive through the same path and are not
        exempt: the person checks their starting figure from it."""
        await self._adjust()

        self.assertEqual(
            self.record_event.await_args.kwargs["details"]["hours"], "40.00"
        )

    async def test_the_event_is_recorded_before_the_commit(self):
        """The row and its notification are stored together or not at all,
        and the balance it reports already counts the row."""
        order = []

        def _balance(*_args, **_kwargs):
            order.append("balance")
            return Decimal("40.00")

        self.ledger_repository.balance.side_effect = _balance
        self.record_event.side_effect = lambda *a, **kw: order.append("event")
        self.session.commit.side_effect = lambda: order.append("commit")

        await self._adjust()

        self.assertEqual(order, ["balance", "event", "commit"])

    async def test_a_refused_adjustment_tells_nobody(self):
        with self.assertRaises(ValueError):
            await self._adjust(note="   ")

        self.record_event.assert_not_awaited()


if __name__ == "__main__":
    main()
