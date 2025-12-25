from dataclasses import dataclass, field
from datetime import datetime
from backend.common.mentorship_enums import CommunicationMethod, UserTimezone


@dataclass
class UserDto:
    id: int
    firstName: str
    lastName: str
    timezone: UserTimezone
    timezoneUpdatedAt: datetime
    communicationMethod: CommunicationMethod
    primaryEmail: str
    updatedTimestamp: datetime
    preferredName: str | None = None
    alternativeEmails: list[str] = field(default_factory=list)
    linkedinLink: str | None = None
