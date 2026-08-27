"""Renders the mentorship admission event into (subject, HTML body).

Mirrors ``recruiting/notification_renderers.py``: the domain-neutral
``render_registry`` dispatches on ``EventEntity.event_type``, and this module
resolves the display fields and hands them to
``mentorship/notification_email_copy``.

Everything about the round is read from ``event.details`` -- the snapshot the
admission took -- never re-queried. A Pub/Sub redelivery can render hours
later, by which point a different round may be open, or none, and two
deliveries of one admission must not say different things.

Importing this module registers the renderer. ``fast_app_factory`` imports it
once at startup for that side effect, alongside ``recipient_resolvers``.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import MentorshipEvent
from backend.entity.application_entity import ApplicationEntity
from backend.entity.event_entity import EventEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship import notification_email_copy as copy
from backend.notification_management.render_registry import register_render

# Where a recipient with no usable timezone on file is assumed to be. Most
# mentors are in North America, and ``users.timezone`` is a free-form string
# column with no enum behind it, so "not a resolvable IANA zone" includes
# empty, misspelled and outright invented values.
#
# Getting this wrong costs the reader a conversion, not the deadline: the
# zone is always named, so a Shanghai mentor whose profile is blank reads
# "8:59 AM (America/Los_Angeles)" -- the same instant as their own 11:59 PM.
_FALLBACK_TIMEZONE = "America/Los_Angeles"


def _zone(timezone_name: str | None) -> ZoneInfo:
    """The recipient's timezone, or the fallback when it does not resolve.

    Args:
        timezone_name (str | None): ``users.timezone``, unvalidated.

    Returns:
        ZoneInfo: A usable zone. Never raises -- an unresolvable zone must
            not stop the email, only shift which clock it is stated on.
    """
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return ZoneInfo(_FALLBACK_TIMEZONE)


def _instant(raw: str | None) -> datetime | None:
    """Parse a snapshotted timestamp, or None if it is not an instant.

    Only an aware datetime is an instant. The one-off import wrote some of
    these fields as a bare ``YYYY-MM-DD``, which parses naive: there is no
    moment in time to convert, and assuming midnight would state a deadline
    nobody set. The caller degrades to the no-round variant instead.

    Args:
        raw (str | None): The value as stored in the event's details.

    Returns:
        datetime | None: An aware datetime, or None.
    """
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _format_deadline(instant: datetime, zone: ZoneInfo) -> str:
    """ "September 30, 2026, at 11:59 PM (Asia/Shanghai)".

    Rendered to the minute with the zone named, because being off by a few
    hours here makes someone miss the registration window.
    """
    local = instant.astimezone(zone)
    hour = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return (
        f"{local.strftime('%B')} {local.day}, {local.year}, "
        f"at {hour}:{local.strftime('%M')} {meridiem} ({zone.key})"
    )


def _format_matching_date(instant: datetime, zone: ZoneInfo) -> str:
    """ "October 15, 2026 (Asia/Shanghai)" -- converted first, truncated second.

    ``match_notification_at`` estimates which day results go out, so a time
    would be invented precision. The conversion still has to happen before
    the truncation: a value stored as 2026-10-15T20:00Z falls on October 16
    in Shanghai, and taking the stored date component would print the day
    before.
    """
    local = instant.astimezone(zone)
    return f"{local.strftime('%B')} {local.day}, {local.year} ({zone.key})"


async def _recipient(session: AsyncSession, application_id: int):
    """The admitted person's greeting name and timezone.

    First name, not the full name ``user_display_name`` resolves: this
    email greets the recipient directly, where "Dear Ada Lovelace," reads
    like a form letter. A preferred name still wins over the legal one --
    that is the whole point of the field -- so the rule is
    ``user_display_name``'s first half with ``first_name`` as the
    fallback instead of "first last".

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        application_id (int): The application the event is about.

    Returns:
        tuple[str, str | None]: Greeting name ("" when nothing resolves, which
            greets without a name) and the raw ``users.timezone``.
    """
    result = await session.execute(
        select(
            UsersEntity.first_name,
            UsersEntity.preferred_name,
            UsersEntity.timezone,
        )
        .join(ApplicationEntity, ApplicationEntity.user_id == UsersEntity.user_id)
        .where(ApplicationEntity.application_id == application_id)
    )
    row = result.first()
    if row is None:
        return "", None
    first_name, preferred_name, timezone_name = row
    if preferred_name and preferred_name.strip():
        return preferred_name.strip(), timezone_name
    return (first_name or "").strip(), timezone_name


@register_render(MentorshipEvent.MENTOR_ADMITTED)
async def _render_mentor_admitted(session: AsyncSession, event: EventEntity):
    """The admission email, with the round's dates when there are usable ones.

    The recipient is not passed in -- ``render_registry.render`` takes only
    (session, event) -- and does not need to be: this event's single
    recipient is by construction the application's own user, which is
    resolved from ``subject_id`` here.
    """
    display_name, timezone_name = await _recipient(session, event.subject_id)
    zone = _zone(timezone_name)

    deadline = _instant(event.details.get("registrationDeadlineAt"))
    matching = _instant(event.details.get("matchNotificationAt"))
    if deadline is None or matching is None:
        return copy.mentor_admitted_without_round(display_name)

    return copy.mentor_admitted_with_round(
        display_name,
        event.details.get("roundName"),
        _format_deadline(deadline, zone),
        _format_matching_date(matching, zone),
    )
