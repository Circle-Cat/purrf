"""Domain-agnostic Google Calendar meeting orchestration.

Holds **no** business rules and touches **no** domain tables: callers
(mentorship pairs today, recruiting interviews next) validate their own
permissions, decide who attends, and persist the result their own way. What
lives here is the part every caller would otherwise re-implement against the
Calendar API — resolving attendee addresses, minting the idempotency keys,
opening up the Meet space, and normalizing Google's response shape.

Storage deliberately stays with the callers: mentorship keeps its
``mentorship_pairs.meeting_log`` JSONB (read by ten other files and tangled
with mentorship-only credit tracking), recruiting gets its own table.
"""

import asyncio
import uuid


class MeetingSchedulingService:
    def __init__(self, logger, google_service, user_emails_repository):
        """
        Args:
            logger (Logger): Shared app logger.
            google_service (GoogleService): Calendar / Meet transport.
            user_emails_repository (UserEmailsRepository): Contact-address lookup.
        """
        self.logger = logger
        self.google_service = google_service
        self.user_emails_repository = user_emails_repository

    async def resolve_attendee_emails(self, session, attendee_user_ids):
        """Contact addresses for the given users, in the order supplied.

        A user with no address on file is **skipped with a warning** rather
        than failing the whole meeting — the same behaviour mentorship has
        always had. Callers for whom a missing address is fatal (e.g. the
        candidate on a recruiting interview) must check that themselves
        before calling.

        Duplicates are collapsed: Calendar rejects a repeated attendee, and
        two user rows can legitimately share one address.

        Args:
            session (AsyncSession): The active DB session.
            attendee_user_ids (list[int]): Users to invite.

        Returns:
            list[str]: Addresses, input order, deduplicated.
        """
        contact_by_user_id = (
            await self.user_emails_repository.get_contact_emails_by_user_ids(
                session, attendee_user_ids
            )
        )
        emails = []
        for user_id in attendee_user_ids:
            email = contact_by_user_id.get(user_id)
            if not email:
                self.logger.warning(
                    "[MeetingSchedulingService] user_id=%s has no contact email; "
                    "creating the calendar invite without them",
                    user_id,
                )
                continue
            if email not in emails:
                emails.append(email)
        return emails

    async def schedule(
        self, session, summary, start_utc, end_utc, attendee_user_ids, calendar_id
    ):
        """Create a Calendar event with a Meet link and invite the attendees.

        Google mails the invitations itself (``sendUpdates="all"`` inside
        ``insert_google_meeting``) — this service never sends email.

        The insert carries a client-minted ``event_id`` so a retried call
        cannot create a second event: a duplicate-id 409 is proof the first
        attempt landed, and GoogleService fetches that event back.

        Opening the Meet space is **best effort**. It matters for external
        guests (otherwise they must knock and wait to be admitted), but a
        failure there must not discard an event Google has already created
        and mailed out.

        Args:
            session (AsyncSession): The active DB session (attendee lookup only).
            summary (str): Event title, as attendees will see it.
            start_utc (datetime): Start, tz-aware UTC.
            end_utc (datetime): End, tz-aware UTC.
            attendee_user_ids (list[int]): Users to invite; ones without a
                contact address are skipped (see ``resolve_attendee_emails``).
            calendar_id (str): The calendar to act on. Passed straight
                through to GoogleService: this service is domain-agnostic and
                must not know which scenario owns which container, so it
                neither stores a calendar id nor has a default.

        Returns:
            dict: ``google_event_id`` / ``meet_link`` / ``entry_points`` /
                ``conference_id`` / ``created``.

        Raises:
            RateLimitedError / RuntimeError: Propagated from the Calendar insert.
        """
        attendees_emails = await self.resolve_attendee_emails(
            session, attendee_user_ids
        )
        event = await asyncio.to_thread(
            self.google_service.insert_google_meeting,
            summary=summary,
            start_time=start_utc,
            end_time=end_utc,
            attendees_emails=attendees_emails,
            request_id=str(uuid.uuid4()),
            calendar_id=calendar_id,
            event_id=uuid.uuid4().hex,
        )
        conference = event.get("conferenceData") or {}
        meeting_code = conference.get("conferenceId")
        if meeting_code:
            try:
                space_name = await self.google_service.get_meet_space_name(meeting_code)
                await self.google_service.update_meet_space_type_to_open(space_name)
            except Exception as e:
                self.logger.warning(
                    "[MeetingSchedulingService] Non-fatal: failed to set Meet "
                    "space %s to OPEN: %s",
                    meeting_code,
                    e,
                )
        return {
            "google_event_id": event.get("id", ""),
            "meet_link": event.get("hangoutLink", ""),
            "entry_points": conference.get("entryPoints", []),
            "conference_id": meeting_code,
            "created": event.get("created", ""),
        }

    async def update(
        self, session, event_id, start_utc, end_utc, attendee_user_ids, calendar_id
    ):
        """Move an existing meeting and/or replace who is invited.

        Does **not** re-open the Meet space: the conference already exists and
        was opened when the meeting was created, so re-doing it every edit
        would be two wasted API calls.

        Args:
            session (AsyncSession): The active DB session (attendee lookup only).
            event_id (str): The Calendar event to patch.
            start_utc (datetime): New start, tz-aware UTC.
            end_utc (datetime): New end, tz-aware UTC.
            attendee_user_ids (list[int]): The complete attendee list after the
                change (not a delta).
            calendar_id (str): The calendar to act on. Passed straight
                through to GoogleService: this service is domain-agnostic and
                must not know which scenario owns which container, so it
                neither stores a calendar id nor has a default.

        Returns:
            dict: Same shape as ``schedule``.

        Raises:
            MeetingGoneError: The event no longer exists on the calendar.
            RuntimeError: Any other Calendar failure.
        """
        attendees_emails = await self.resolve_attendee_emails(
            session, attendee_user_ids
        )
        event = await asyncio.to_thread(
            self.google_service.update_google_meeting,
            event_id=event_id,
            start_time=start_utc,
            end_time=end_utc,
            attendees_emails=attendees_emails,
            calendar_id=calendar_id,
        )
        conference = event.get("conferenceData") or {}
        return {
            "google_event_id": event.get("id", ""),
            "meet_link": event.get("hangoutLink", ""),
            "entry_points": conference.get("entryPoints", []),
            "conference_id": conference.get("conferenceId"),
            "created": event.get("created", ""),
        }

    async def cancel(self, event_ids, calendar_id):
        """Delete Calendar events; Google mails the cancellations.

        An event already absent from Calendar counts as succeeded — deletion
        is about the end state (see ``batch_delete_google_meetings``).

        Args:
            event_ids (list[str]): Calendar event ids to delete.
            calendar_id (str): The calendar to act on. Passed straight
                through to GoogleService: this service is domain-agnostic and
                must not know which scenario owns which container, so it
                neither stores a calendar id nor has a default.

        Returns:
            tuple[list[str], list[str]]: Succeeded ids, failed ids.
        """
        return await asyncio.to_thread(
            self.google_service.batch_delete_google_meetings,
            event_ids=event_ids,
            calendar_id=calendar_id,
        )
