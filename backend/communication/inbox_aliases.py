import os
from dataclasses import dataclass

from backend.common.communication_enums import InboxService
from backend.common.environment_constants import (
    GMAIL_INBOX_ENABLED,
    GMAIL_SENDER_INQUIRIES,
    GMAIL_SENDER_MENTORSHIP,
    GMAIL_SENDER_RECRUITING,
)


@dataclass(frozen=True)
class InboxAliases:
    """Each Inbox service's Send-As alias, and whether new mail to them is claimed.

    The alias is also the service's reply address, so it is set even where
    ``claims_new_mail`` is off.
    """

    mentorship: str | None = None
    recruiting: str | None = None
    inquiries: str | None = None
    claims_new_mail: bool = True

    def __post_init__(self) -> None:
        for name in ("mentorship", "recruiting", "inquiries"):
            value = getattr(self, name)
            normalized = value.strip().lower() if value else ""
            object.__setattr__(self, name, normalized or None)

    @classmethod
    def from_env(cls) -> "InboxAliases":
        return cls(
            mentorship=os.getenv(GMAIL_SENDER_MENTORSHIP),
            recruiting=os.getenv(GMAIL_SENDER_RECRUITING),
            inquiries=os.getenv(GMAIL_SENDER_INQUIRIES),
            claims_new_mail=(os.getenv(GMAIL_INBOX_ENABLED) or "").strip().lower()
            == "true",
        )

    def alias_of(self, service: InboxService) -> str | None:
        return {
            InboxService.MENTORSHIP: self.mentorship,
            InboxService.RECRUITING: self.recruiting,
            InboxService.INQUIRIES: self.inquiries,
        }[service]

    def addresses(self) -> list[str]:
        return [a for a in (self.mentorship, self.recruiting, self.inquiries) if a]

    def service_for(self, recipients: list[str]) -> InboxService | None:
        """The service of the first recipient that is a claimed alias."""
        if not self.claims_new_mail:
            return None
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
