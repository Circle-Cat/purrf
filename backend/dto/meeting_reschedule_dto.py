from backend.dto.meeting_slot_request_dto import MeetingSlotRequestDto


class MeetingRescheduleDto(MeetingSlotRequestDto):
    """Move one already-booked meeting to a new slot.

    The same wall-clock contract as creation -- a local date, an HH:MM local
    time and the zone they are meant in -- because the server, not the
    browser, owns the conversion to UTC.

    No `interval_weeks` / `count`: a reschedule moves exactly one meeting.
    Moving a whole series is a separate feature.
    """
