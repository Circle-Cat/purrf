from dataclasses import dataclass
from datetime import date


@dataclass
class WorkHistoryDto:
    id: str
    title: str
    companyOrOrganization: str
    startDate: date
    isCurrentJob: bool
    endDate: date | None = None
