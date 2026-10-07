import os
from dataclasses import dataclass

from backend.common.communication_enums import InboxService
from backend.common.environment_constants import (
    GMAIL_INBOX_INQUIRIES,
    GMAIL_INBOX_MENTORSHIP,
    GMAIL_INBOX_RECRUITING,
)


@dataclass(frozen=True)
class InboxAliases:
    """The Send-As aliases this environment claims, one optional per service."""

    mentorship: str | None = None
    recruiting: str | None = None
    inquiries: str | None = None

    def __post_init__(self) -> None:
        for name in ("mentorship", "recruiting", "inquiries"):
            value = getattr(self, name)
            normalized = value.strip().lower() if value else ""
            object.__setattr__(self, name, normalized or None)

    @classmethod
    def from_env(cls) -> "InboxAliases":
        return cls(
            mentorship=os.getenv(GMAIL_INBOX_MENTORSHIP),
            recruiting=os.getenv(GMAIL_INBOX_RECRUITING),
            inquiries=os.getenv(GMAIL_INBOX_INQUIRIES),
        )

    def alias_of(self, service: InboxService) -> str | None:
        return {
            InboxService.MENTORSHIP: self.mentorship,
            InboxService.RECRUITING: self.recruiting,
            InboxService.INQUIRIES: self.inquiries,
        }[service]

    def claimed(self) -> list[str]:
        return [a for a in (self.mentorship, self.recruiting, self.inquiries) if a]

    def service_for(self, recipients: list[str]) -> InboxService | None:
        """The service of the first recipient that is a claimed alias."""
        by_alias = {
            alias: service
            for service in InboxService
            if (alias := self.alias_of(service))
        }
        for recipient in recipients:
            service = by_alias.get(recipient.strip().lower())
            if service is not None:
                return service
        return None
